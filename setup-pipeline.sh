#!/usr/bin/env bash
# Auto-deploy: every push to main is tested and deployed by AWS CodePipeline.
#
#   ./setup-pipeline.sh                  # repo akhilsripada/HireGuard, branch main, stage prod
#   ./setup-pipeline.sh owner/Repo       # another repo
#
# Run it twice:
#   1st run: creates the HireGuard-Pipeline stack. Its GitHub connection starts as PENDING.
#            Approve it once in the console (the script prints where).
#   2nd run: sees the connection is AVAILABLE and starts the first deploy.
# After that, pushes to main deploy by themselves.
set -euo pipefail
cd "$(dirname "$0")"
REPO="${1:-akhilsripada/HireGuard}"
if [ -z "${AWS_PROFILE:-}" ] && aws configure list-profiles 2>/dev/null | grep -qx hireguard; then
  export AWS_PROFILE=hireguard
fi
REGION="${HG_REGION:-$(aws configure get region 2>/dev/null || true)}"
REGION="${REGION:-us-east-2}"
export AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION" AWS_PAGER=""

echo "==> 1/3 Check AWS sign-in"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "Not signed in to AWS. Run:  aws login --profile hireguard   (then run this script again)"
  exit 1
fi

echo "==> 2/3 Create or update the pipeline for $REPO (region $REGION)"
aws cloudformation deploy \
  --stack-name HireGuard-Pipeline \
  --template-file infra/pipeline.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides GitHubRepo="$REPO" \
  --no-fail-on-empty-changeset
out() { aws cloudformation describe-stacks --stack-name HireGuard-Pipeline \
          --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
CONN_ARN=$(out ConnectionArn)
PIPELINE_URL=$(out PipelineUrl)

echo "==> 3/3 GitHub connection"
STATUS=$(aws codestar-connections get-connection --connection-arn "$CONN_ARN" \
           --query 'Connection.ConnectionStatus' --output text)
echo "Connection status: $STATUS"
if [ "$STATUS" != "AVAILABLE" ]; then
  echo
  echo "Approve the connection once (AWS needs your OK to read the GitHub repo):"
  echo "  https://$REGION.console.aws.amazon.com/codesuite/settings/connections?region=$REGION"
  echo "  -> click 'hireguard-github' -> 'Update pending connection' -> follow the GitHub steps."
  echo "Then run this script again to start the first deploy."
  exit 0
fi
aws codepipeline start-pipeline-execution --name HireGuard-Deploy --query pipelineExecutionId --output text >/dev/null
echo "Started a deploy. Watch it here:"
echo "  $PIPELINE_URL"
echo "From now on every push to main deploys automatically."
