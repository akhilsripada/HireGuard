"""HireGuard: the whole app in one CDK stack.

Website  : S3 (private) + CloudFront (HTTPS, SPA fallback)
API      : API Gateway HTTP API (throttled, CORS locked to the site) -> 5 Python Lambdas
           (scan, report, stats, analyze with Amazon Bedrock, library)
Data     : DynamoDB Scans / Reports / DomainCache / Library (on-demand, TTL)
Auth     : Cognito user pool + Hosted UI (only /report needs a login)
Ops      : CloudWatch dashboard + alarms, optional email alerts
"""
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    SecretValue,
    Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_authorizers as authorizers,
    aws_apigatewayv2_integrations as integrations,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
    aws_cognito as cognito,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_secretsmanager as secrets,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
)
from constructs import Construct

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
LOCAL_DEV_ORIGIN = "http://localhost:5173"


class HireGuardStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: str, alert_email: str | None = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------- Data ----------
        table_defaults = dict(billing_mode=ddb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.DESTROY)
        scans = ddb.Table(
            self, "Scans",
            partition_key=ddb.Attribute(name="scanId", type=ddb.AttributeType.STRING),
            time_to_live_attribute="expiresAt",
            **table_defaults,
        )
        scans.add_global_secondary_index(
            index_name="byDay",
            partition_key=ddb.Attribute(name="day", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="createdAt", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.INCLUDE,
            non_key_attributes=["flagIds", "label"],
        )
        reports = ddb.Table(
            self, "Reports",
            partition_key=ddb.Attribute(name="contactHash", type=ddb.AttributeType.STRING),
            **table_defaults,
        )
        domain_cache = ddb.Table(
            self, "DomainCache",
            partition_key=ddb.Attribute(name="domain", type=ddb.AttributeType.STRING),
            time_to_live_attribute="expiresAt",
            **table_defaults,
        )

        # Scam library: messages people chose to share, personal details removed
        library = ddb.Table(
            self, "Library",
            partition_key=ddb.Attribute(name="entryId", type=ddb.AttributeType.STRING),
            time_to_live_attribute="expiresAt",
            **table_defaults,
        )
        library.add_global_secondary_index(
            index_name="byNewest",
            partition_key=ddb.Attribute(name="kind", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="createdAt", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.ALL,
        )

        # Safe Browsing key: deploys with a placeholder; set the real key in the console afterwards.
        safe_browsing = secrets.Secret(
            self, "SafeBrowsingKey",
            secret_name=f"hireguard/{stage}/safe-browsing",
            secret_string_value=SecretValue.unsafe_plain_text('{"apiKey": "REPLACE_ME"}'),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---------- Website bucket + CDN ----------
        site_bucket = s3.Bucket(
            self, "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        spa_fallback = [
            cloudfront.ErrorResponse(http_status=code, response_http_status=200, response_page_path="/index.html", ttl=Duration.seconds(0))
            for code in (403, 404)
        ]
        distribution = cloudfront.Distribution(
            self, "Site",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(site_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            error_responses=spa_fallback,
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
        )
        site_url = f"https://{distribution.distribution_domain_name}"

        # ---------- Auth (only for /report) ----------
        user_pool = cognito.UserPool(
            self, "Users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(min_length=10, require_symbols=False),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )
        domain = user_pool.add_domain(
            "HostedUi",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=f"hireguard-{stage}-{self.account}"),
        )
        callback_urls = [f"{site_url}/auth/callback", f"{LOCAL_DEV_ORIGIN}/auth/callback"]
        client = user_pool.add_client(
            "WebClient",
            generate_secret=False,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
                callback_urls=callback_urls,
                logout_urls=[f"{site_url}/", f"{LOCAL_DEV_ORIGIN}/"],
            ),
            id_token_validity=Duration.hours(1),
            prevent_user_existence_errors=True,
        )

        # ---------- Lambdas ----------
        code = lambda_.Code.from_asset(
            str(BACKEND),
            exclude=["tests", "tests/**", "local_mode", "local_mode/**", ".venv", ".venv/**", "**/__pycache__", "*.toml", "requirements*.txt", ".pytest_cache", ".ruff_cache"],
        )
        common_env = {
            "SCANS_TABLE": scans.table_name,
            "REPORTS_TABLE": reports.table_name,
            "DOMAIN_CACHE_TABLE": domain_cache.table_name,
            "LIBRARY_TABLE": library.table_name,
            "SAFE_BROWSING_SECRET_ARN": safe_browsing.secret_arn,
            "AI_SIGNAL_ENABLED": str(self.node.try_get_context("aiSignal") or "false").lower(),
            "EXTERNAL_TIMEOUT_S": "1.5",
            "LOG_LEVEL": "INFO",
        }

        bedrock_model = str(self.node.try_get_context("bedrockModel") or "us.anthropic.claude-haiku-4-5-20251001-v1:0")

        def fn(name: str, handler: str, timeout: int = 10, memory: int = 256, extra_env: dict | None = None) -> lambda_.Function:
            return lambda_.Function(
                self, name,
                runtime=lambda_.Runtime.PYTHON_3_12,
                architecture=lambda_.Architecture.ARM_64,
                handler=handler,
                code=code,
                memory_size=memory,
                timeout=Duration.seconds(timeout),
                environment={**common_env, **(extra_env or {})},
                log_retention=logs.RetentionDays.TWO_WEEKS,
            )

        scan_fn = fn("ScanFn", "handlers.scan_handler.handler")
        report_fn = fn("ReportFn", "handlers.report_handler.handler")
        stats_fn = fn("StatsFn", "handlers.stats_handler.handler")
        library_fn = fn("LibraryFn", "handlers.library_handler.handler")
        analyze_fn = fn("AnalyzeFn", "handlers.analyze_handler.handler", timeout=29, memory=512,
                        extra_env={"BEDROCK_MODEL_ID": bedrock_model})

        # Least privilege: each function gets only what it touches
        scans.grant_write_data(scan_fn)
        reports.grant_read_data(scan_fn)
        domain_cache.grant_read_write_data(scan_fn)
        safe_browsing.grant_read(scan_fn)
        scan_fn.add_to_role_policy(iam.PolicyStatement(actions=["comprehend:DetectKeyPhrases"], resources=["*"]))
        reports.grant_read_write_data(report_fn)
        library.grant_write_data(report_fn)
        scans.grant_read_data(stats_fn)
        library.grant_read_data(library_fn)
        reports.grant_read_data(library_fn)
        # Bedrock: the US cross-region inference profile routes to the model in several US regions
        analyze_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:Converse"],
            resources=[
                f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
                "arn:aws:bedrock:*::foundation-model/*",
            ],
        ))
        # First call to a marketplace model may need to confirm the subscription
        analyze_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["aws-marketplace:ViewSubscriptions", "aws-marketplace:Subscribe"],
            resources=["*"],
        ))

        # ---------- API ----------
        api = apigw.HttpApi(
            self, "Api",
            create_default_stage=False,
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=[site_url, LOCAL_DEV_ORIGIN],
                allow_methods=[apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
                allow_headers=["content-type", "authorization"],
                max_age=Duration.hours(1),
            ),
        )
        stage_ = api.add_stage(
            "DefaultStage",
            stage_name="$default",
            auto_deploy=True,
            throttle=apigw.ThrottleSettings(rate_limit=10, burst_limit=20),
        )

        jwt_auth = authorizers.HttpUserPoolAuthorizer("UserPoolAuth", user_pool, user_pool_clients=[client])
        api.add_routes(path="/scan", methods=[apigw.HttpMethod.POST], integration=integrations.HttpLambdaIntegration("ScanInt", scan_fn))
        api.add_routes(path="/report", methods=[apigw.HttpMethod.POST], integration=integrations.HttpLambdaIntegration("ReportInt", report_fn), authorizer=jwt_auth)
        api.add_routes(path="/stats", methods=[apigw.HttpMethod.GET], integration=integrations.HttpLambdaIntegration("StatsInt", stats_fn))
        analyze_routes = api.add_routes(path="/analyze", methods=[apigw.HttpMethod.POST], integration=integrations.HttpLambdaIntegration("AnalyzeInt", analyze_fn))
        # AI calls cost money: tighter limit on that one route.
        # The stage must be updated after the route exists, so add an explicit dependency.
        cfn_stage = stage_.node.default_child
        cfn_stage.route_settings = {
            "POST /analyze": {"ThrottlingRateLimit": 2, "ThrottlingBurstLimit": 4},
        }
        for route in analyze_routes:
            cfn_stage.add_dependency(route.node.default_child)
        library_int = integrations.HttpLambdaIntegration("LibraryInt", library_fn)
        api.add_routes(path="/library", methods=[apigw.HttpMethod.GET], integration=library_int)
        api.add_routes(path="/library/sites", methods=[apigw.HttpMethod.GET], integration=library_int)
        api.add_routes(path="/lookup", methods=[apigw.HttpMethod.POST], integration=library_int)
        api_url = f"https://{api.api_id}.execute-api.{self.region}.amazonaws.com"

        # ---------- Deploy the built site + runtime config ----------
        if not (FRONTEND_DIST / "index.html").exists():
            raise SystemExit("frontend/dist is missing. Run `npm run build` in frontend/ first (or use ./deploy.sh).")
        s3deploy.BucketDeployment(
            self, "DeploySite",
            destination_bucket=site_bucket,
            sources=[
                s3deploy.Source.asset(str(FRONTEND_DIST)),
                s3deploy.Source.json_data("config.json", {
                    "apiUrl": api_url,
                    "cognitoDomain": domain.base_url(),
                    "cognitoClientId": client.user_pool_client_id,
                    "region": self.region,
                    "stage": stage,
                }),
            ],
            distribution=distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )

        # ---------- Monitoring ----------
        alarm_topic = sns.Topic(self, "Alerts")
        if alert_email:
            alarm_topic.add_subscription(subs.EmailSubscription(alert_email))
        alarm_action = cw_actions.SnsAction(alarm_topic)

        for f, label in ((scan_fn, "Scan"), (report_fn, "Report"), (stats_fn, "Stats"), (library_fn, "Library"), (analyze_fn, "Analyze")):
            alarm = cw.Alarm(
                self, f"{label}Errors",
                metric=f.metric_errors(period=Duration.minutes(5), statistic="Sum"),
                threshold=5, evaluation_periods=1,
                comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
                alarm_description=f"{label} Lambda: more than 5 errors in 5 minutes",
            )
            alarm.add_alarm_action(alarm_action)

        latency = cw.Alarm(
            self, "ScanLatency",
            metric=scan_fn.metric_duration(period=Duration.minutes(5), statistic="p95"),
            threshold=3000, evaluation_periods=2,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
            alarm_description="/scan p95 latency over 3 s for 10 minutes",
        )
        latency.add_alarm_action(alarm_action)

        api_5xx = cw.Metric(
            namespace="AWS/ApiGateway", metric_name="5xx", dimensions_map={"ApiId": api.api_id},
            period=Duration.minutes(5), statistic="Sum",
        )
        cw.Alarm(
            self, "Api5xx", metric=api_5xx, threshold=10, evaluation_periods=2,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
            alarm_description="API returned more than 10 server errors in 5 minutes, twice in a row",
        ).add_alarm_action(alarm_action)

        dashboard = cw.Dashboard(self, "Dashboard", dashboard_name=f"HireGuard-{stage}")
        dashboard.add_widgets(
            cw.GraphWidget(title="Scans per 5 min", left=[scan_fn.metric_invocations(period=Duration.minutes(5), statistic="Sum")]),
            cw.GraphWidget(title="Scan latency p95 (ms)", left=[scan_fn.metric_duration(period=Duration.minutes(5), statistic="p95")]),
            cw.GraphWidget(title="Lambda errors", left=[f.metric_errors(period=Duration.minutes(5), statistic="Sum") for f in (scan_fn, report_fn, stats_fn, library_fn, analyze_fn)]),
            cw.GraphWidget(title="API 4xx / 5xx", left=[
                cw.Metric(namespace="AWS/ApiGateway", metric_name="4xx", dimensions_map={"ApiId": api.api_id}, period=Duration.minutes(5), statistic="Sum"),
                api_5xx,
            ]),
        )

        # ---------- Outputs ----------
        CfnOutput(self, "WebsiteUrl", value=site_url)
        CfnOutput(self, "ApiUrl", value=api_url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "SafeBrowsingSecretName", value=safe_browsing.secret_name)
        CfnOutput(self, "DashboardUrl", value=f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name=HireGuard-{stage}")
