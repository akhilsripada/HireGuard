#!/usr/bin/env python3
"""CDK entry point.

  cdk deploy                         -> stack HireGuardStack-prod
  cdk deploy -c stage=akhil          -> your own copy, HireGuardStack-akhil
  cdk deploy -c alertEmail=you@x.com -> alarm emails
  cdk deploy -c aiSignal=true        -> turn on the Comprehend signal
"""
import os
import re

import aws_cdk as cdk
from hireguard_stack import HireGuardStack

app = cdk.App()
stage = str(app.node.try_get_context("stage") or "prod").lower()
if not re.fullmatch(r"[a-z0-9-]{1,20}", stage):
    raise SystemExit("stage must be lowercase letters, numbers or dashes (max 20)")

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
)
cdk.Tags.of(app).add("project", "hireguard")
cdk.Tags.of(app).add("stage", stage)
app.synth()
