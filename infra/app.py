#!/usr/bin/env python3
"""CDK entry point.

  cdk deploy                         -> stack HireGuardStack-prod
  cdk deploy -c stage=akhil          -> your own copy, HireGuardStack-akhil
  cdk deploy -c alertEmail=you@x.com -> alarm emails
  cdk deploy -c aiSignal=true        -> turn on the Comprehend signal
"""
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
    env=cdk.Environment(region="us-east-1"),
    description="HireGuard job-scam checker (serverless)",
)
cdk.Tags.of(app).add("project", "hireguard")
cdk.Tags.of(app).add("stage", stage)
app.synth()
