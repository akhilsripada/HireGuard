#!/usr/bin/env bash
# One command to build and deploy HireGuard to your AWS account.
#
#   ./deploy.sh                       # deploys stage "prod"
#   ./deploy.sh akhil                 # your own copy: HireGuardStack-akhil
#   AWS_PROFILE=hireguard ./deploy.sh # pick the AWS profile
#
# Needs: Python 3.12+, Node 20+, AWS CLI v2 signed in, AWS CDK v2 (npm i -g aws-cdk)
set -euo pipefail
cd "$(dirname "$0")"
STAGE="${1:-prod}"
if [ -z "${AWS_PROFILE:-}" ] && aws configure list-profiles 2>/dev/null | grep -qx hireguard; then
  export AWS_PROFILE=hireguard
fi
# Region: HG_REGION, else the profile's region, else us-east-2
REGION="${HG_REGION:-$(aws configure get region 2>/dev/null || true)}"
REGION="${REGION:-us-east-2}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" CDK_DEFAULT_REGION="$REGION"
echo "Deploying to region: $REGION"

echo "==> 0/4 Check AWS sign-in"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "Not signed in to AWS. Run:  aws login --profile hireguard   (then run this script again)"
  exit 1
fi
if ! aws cloudformation describe-stacks --stack-name CDKToolkit >/dev/null 2>&1; then
  echo "First deploy in this account: preparing it for CDK (one time)…"
  cdk bootstrap "aws://$(aws sts get-caller-identity --query Account --output text)/$REGION"
fi

echo "==> 1/4 Backend tests"
( cd backend
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-dev.txt
  .venv/bin/python tests/samples/make_samples.py >/dev/null
  .venv/bin/python -m pytest -q )

echo "==> 2/4 Build website"
( cd frontend && npm install --silent && npm run build )

echo "==> 3/4 CDK dependencies"
( cd infra
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt )

echo "==> 4/4 Deploy stage '$STAGE' (takes ~5-10 minutes the first time)"
( cd infra && source .venv/bin/activate && cdk deploy "HireGuardStack-$STAGE" -c stage="$STAGE" -c region="$REGION" --require-approval never --outputs-file ../cdk-outputs.json )

echo
echo "Done. Your site:"
python3 -c "import json; d=json.load(open('cdk-outputs.json')); print(list(d.values())[0]['WebsiteUrl'])"
