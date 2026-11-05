#!/usr/bin/env python3
"""CDK entry point.

  cdk deploy                         -> stack HireGuardStack-prod
  cdk deploy -c stage=akhil          -> your own copy, HireGuardStack-akhil
  cdk deploy -c alertEmail=you@x.com -> alarm emails
  cdk deploy -c aiSignal=true        -> turn on the Comprehend signal
  cdk synth -c launchBucket=<bucket> -> template for the Launch Stack button (see publish-launch.sh)
"""
import os
import re

import aws_cdk as cdk
from hireguard_stack import HireGuardStack

app = cdk.App()
stage = str(app.node.try_get_context("stage") or "prod").lower()
if not re.fullmatch(r"[a-z0-9-]{1,20}", stage):
    raise SystemExit("stage must be lowercase letters, numbers or dashes (max 20)")

# Launch Stack mode: the template points at code in one public bucket instead of the
# CDK bootstrap bucket, so any AWS account can deploy it from the CloudFormation console
# without installing anything or running `cdk bootstrap`.
launch_bucket = app.node.try_get_context("launchBucket")
synth_args = {}
if launch_bucket:
    synth_args["synthesizer"] = cdk.DefaultStackSynthesizer(
        file_assets_bucket_name=launch_bucket,
        bucket_prefix="assets/",
        generate_bootstrap_version_rule=False,
    )

HireGuardStack(
    app,
    f"HireGuardStack-{stage}",
    stage=stage,
    alert_email=app.node.try_get_context("alertEmail"),
    # Region: -c region=..., else the AWS profile's region, else us-east-2 (AWS "projects" accounts in the Americas)
    env=cdk.Environment(
        region=app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION") or "us-east-2",
    ),
    description="HireGuard job-scam checker (serverless)",
    **synth_args,
)
cdk.Tags.of(app).add("project", "hireguard")
cdk.Tags.of(app).add("stage", stage)
app.synth()
