#!/usr/bin/env bash
# Publish HireGuard for the "Launch Stack" button in the README.
#
#   ./publish-launch.sh
#
# Builds the site, synthesizes the stack in launch mode and uploads the template and
# code to a public, read-only S3 bucket in your account (hireguard-launch-<account id>).
# Anyone can then deploy HireGuard to their own AWS account from the CloudFormation
# console. The bucket holds only the template, Lambda code and the built website:
# no data and no secrets. Run it again whenever you want the button to ship new code.
#
# Lambda code must live in the same region as the stack, so the button deploys to
# this region only (default us-east-2).
set -euo pipefail
cd "$(dirname "$0")"
STACK="HireGuardStack-launch"
if [ -z "${AWS_PROFILE:-}" ] && aws configure list-profiles 2>/dev/null | grep -qx hireguard; then
  export AWS_PROFILE=hireguard
fi
REGION="${HG_REGION:-$(aws configure get region 2>/dev/null || true)}"
REGION="${REGION:-us-east-2}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" CDK_DEFAULT_REGION="$REGION" AWS_PAGER=""

echo "==> 0/5 Check AWS sign-in"
if ! ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null); then
  echo "Not signed in to AWS. Run:  aws login --profile hireguard   (then run this script again)"
  exit 1
fi
BUCKET="hireguard-launch-$ACCOUNT"
echo "Account $ACCOUNT, region $REGION, bucket $BUCKET"

echo "==> 1/5 Public read-only bucket for the template and code"
if ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  fi
  echo "Created $BUCKET"
fi
# Allow a public bucket policy on this bucket only; public ACLs stay blocked.
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false
POLICY=$(printf '{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadForLaunchStack","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::%s/*"}]}' "$BUCKET")
if ! aws s3api put-bucket-policy --bucket "$BUCKET" --policy "$POLICY"; then
  echo
  echo "AWS refused the public read policy. Your account blocks public bucket policies"
  echo "(S3 console -> 'Block Public Access settings for this account'). Turn off only"
  echo "'Block public access ... through new public bucket or access point policies' and"
  echo "'... through any public bucket or access point policies', then run this again."
  exit 1
fi

echo "==> 2/5 Backend tests"
( cd backend
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-dev.txt
  .venv/bin/python tests/samples/make_samples.py >/dev/null
  .venv/bin/python -m pytest -q )

echo "==> 3/5 Build website"
( cd frontend && npm install --silent && npm run build )

echo "==> 4/5 Synthesize the Launch Stack template"
( cd infra
  [ -d .venv ] || python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
  source .venv/bin/activate
  rm -rf cdk.out.launch
  cdk synth "$STACK" -c stage=launch -c launchBucket="$BUCKET" -c region="$REGION" --output cdk.out.launch --quiet )

echo "==> 5/5 Upload template and code"
python3 infra/publish_launch.py infra/cdk.out.launch "$STACK" "$BUCKET" "$REGION" | tee launch-url.txt
echo
echo "Put the URL above behind the Launch Stack button in README.md."
