# HireGuard

**Is this job offer real?** Paste a job post, recruiter email or text message and HireGuard gives it a 0–100 scam-risk score, with every red flag explained and the exact sentence that triggered it.

Job scams are growing fast: US reports of job and employment-agency scams tripled from 2020 to 2024, and reported losses grew from **$90 million to $501 million** ([FTC data via Insurance Journal](https://www.insurancejournal.com/news/national/2025/03/10/815001.htm)).

The whole app is serverless on AWS and deploys with one click, or runs on your own computer with one command.

## Try it

| Way | What you need | How |
| --- | --- | --- |
| **Use the live site** | A browser | https://d8qt3baqmwr93.cloudfront.net |
| **Run it on your computer** | Python 3.10+ (nothing to install) | `git clone https://github.com/akhilsripada/HireGuard.git && cd HireGuard && python3 run.py` |
| **Deploy your own copy to AWS** | An AWS account | Click **Launch Stack** below, then **Create stack** |

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-east-2#/stacks/create/review?templateURL=https%3A%2F%2Fhireguard-launch-705160055248.s3.us-east-2.amazonaws.com%2Fhireguard.template.json&stackName=HireGuard)

## How it works

```
Browser ──> CloudFront + S3 (React site)
   │
   └──> API Gateway (HTTP API, throttled, CORS locked to the site)
          ├── POST /scan          -> Scan Lambda    -> rules engine, RDAP, Safe Browsing, Reports lookup -> DynamoDB Scans
          ├── POST /analyze       -> Analyze Lambda -> Claude on Amazon Bedrock (nothing stored, own rate limit)
          ├── POST /report        -> Report Lambda (Cognito login) -> DynamoDB Reports (hashed contacts) + Library (opt-in, redacted)
          ├── GET  /library       -> Library Lambda -> DynamoDB Library (byNewest index)
          ├── GET  /library/sites -> Library Lambda -> DynamoDB Reports (websites with 3+ reports)
          ├── POST /lookup        -> Library Lambda -> DynamoDB Reports (one contact, by hash)
          └── GET  /stats         -> Stats Lambda   -> DynamoDB Scans (byDay index)
CloudWatch dashboard + alarms · Secrets Manager for API keys · all in one CDK stack
```

`python3 run.py` runs these same handlers on your computer, with SQLite in place of DynamoDB (see [Run it on your computer](#run-it-on-your-computer)).

**Detection** (`backend/hireguard/`) adds up points from independent checks, capped at 100:

| Group | Rules | Points |
| --- | --- | --- |
| Money leaves the job seeker | Pay before you start, fake check, reshipping, unsafe link | 60 each |
| | Gift card / crypto / instant transfer, task scam | 50 each |
| Identity doesn't add up | Free email claiming a big brand, lookalike domain, early SSN/bank request | 35 each |
| Behaviour | New domain (< 30 days), chat-app-only interview, no interview, too-good pay | 20 each |
| | "HR" on a free email service | 15 |
| | Urgency, several signs together | 10 each |
| Community | Contact reported by other users | 15 + 3 per extra report (max 30) |
| Optional | Scam phrases found by Amazon Comprehend (off by default) | up to 10 |

Bands: **0–33 Safe · 34–66 Suspicious · 67–100 Likely scam.** Weights live in `backend/hireguard/config.py` and are tuned against the sample set in `backend/tests/samples`: 16 scam messages (15 full scams plus one with urgency only, which should stay low), 16 genuine recruiter messages and 5 edge cases. Current result: all 15 full scams score Likely scam and all 16 genuine messages score Safe.

External checks (RDAP domain age, Google Safe Browsing, optional Amazon Comprehend) have a 1.5 s timeout. If one fails, the scan still returns and lists it in `checksSkipped`.

**Privacy:** message text is never logged and is not stored, unless a reporter chooses to share it to the scam library; then only a copy with names, emails, phone numbers and links removed is kept. Reported emails, phones and domains are stored only as SHA-256 hashes.

## Features

- **Scan**: paste a job message, get a 0–100 score with every red flag explained.
- **AI second opinion**: Claude on Amazon Bedrock (`POST /analyze`) explains the scam type, the tactics used, questions a real recruiter could answer and how to verify. It never changes the rule-based score; the message is treated strictly as data, the answer is forced into a fixed JSON shape and clipped, and the route has its own tight rate limit.
- **Report**: signed-in users (no sign-in in local mode) report an email, phone or website (stored only as a SHA-256 hash), and can choose to share the scanned message to the library.
- **Scam library** (`/library`): past scam messages with names, emails, phones and links removed; scam websites reported by 3+ people; and a one-at-a-time lookup for any email, phone or website. Emails and phone numbers are never listed publicly, since a spoofed address could wrongly brand a real person.
- **Trending scams**: most common scam types this week or month.

## Run it on your computer

Needs only Python 3.10+. No AWS account, no `pip install`, no Node.

```bash
git clone https://github.com/akhilsripada/HireGuard.git
cd HireGuard
python3 run.py            # opens http://127.0.0.1:8080
python3 run.py --share    # also prints a temporary public https:// link you can send to anyone
```

It runs the same detection engine and API handlers as the AWS version, on a small local web server (`backend/local_mode/`). Scans, reports and the scam library are saved in `.local-data/hireguard.db`. Press Ctrl+C to stop.

Differences from the AWS version:

- **No sign-in.** Reports count as one local user.
- **AI second opinion is off** unless you start with `--ai`, which calls Amazon Bedrock with your own AWS sign-in (needs `pip install "boto3[crt]"` and access to Claude Haiku 4.5; uses the `hireguard` AWS profile if you have one).
- **Safe Browsing** runs only if you set `SAFE_BROWSING_API_KEY`. Domain age (RDAP) works as usual.

`--share` opens a Cloudflare quick tunnel if `cloudflared` is installed (`brew install cloudflared`), otherwise a localhost.run tunnel over `ssh`. Neither needs an account. The link works only while `run.py` is running, and a new one is printed if it drops. On a Mac, `caffeinate -i python3 run.py --share` keeps the computer awake. Anyone with the link can use your copy, so don't combine `--share` with `--ai` unless you're happy to pay for their AI checks.

Other options: `--port 9000`, `--no-browser`, `--db path/to/file.db`, `--quiet`.

The website files come from `frontend/prebuilt/`, which is committed so you don't need Node. After changing the frontend, refresh it with `cd frontend && npm run build:prebuilt`. If `frontend/dist/` is newer (after `npm run build`), `run.py` uses that instead.

## Development

```bash
# backend tests
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python tests/samples/make_samples.py && pytest -q

# website with sample data (mock mode, for UI work)
cd ../frontend && npm install && npm run dev     # http://localhost:5173
```

## Deploy to AWS

### One click (no tools needed)

1. Sign in to your AWS account and click **Launch Stack** above. It opens CloudFormation in **us-east-2 (Ohio)** with the template filled in.
2. Tick **I acknowledge that AWS CloudFormation might create IAM resources** and click **Create stack**.
3. Wait about 5–10 minutes for **CREATE_COMPLETE**, then open the **Outputs** tab and click **WebsiteUrl**.

To remove it, delete the **HireGuard** stack in CloudFormation. The button deploys to us-east-2 only, because Lambda code has to come from a bucket in the same region.

Maintainers: `./publish-launch.sh` builds the stack and uploads the template and code to the public read-only bucket behind the button (`hireguard-launch-<account id>`). Run it again to ship new code through the button.

### One command (from source)

Prerequisites: Python 3.12+, Node 20+, Docker not required, AWS CLI v2 signed in to your account, `npm install -g aws-cdk`, and `cdk bootstrap` (deploy.sh runs it for you). Region: your AWS profile's region, else `us-east-2`; override with `HG_REGION=us-east-1 ./deploy.sh`.

```bash
./deploy.sh            # stage "prod"
./deploy.sh akhil      # a separate copy for testing
```

It runs the tests, builds the site, deploys the stack and prints the website URL.

**AI feature:** the first time, open the Amazon Bedrock console in your region, go to **Model catalog**, open **Claude Haiku 4.5** and complete any one-time access step AWS asks for. Until then the AI card shows "AI analysis isn't available right now" and everything else works. To use another model: `-c bedrockModel=<inference profile id>`. Optional flags (pass to `cdk deploy` in `infra/`): `-c alertEmail=you@example.com` for alarm emails, `-c aiSignal=true` to turn on the Comprehend signal.

After the first deploy, put a [Google Safe Browsing](https://developers.google.com/safe-browsing/v4/get-started) API key into the secret named in the `SafeBrowsingSecretName` output (`{"apiKey": "..."}`). Until then the check is skipped.

### Auto-deploy from GitHub

Every push to `main` is tested and deployed by **AWS CodePipeline** (`infra/pipeline.yaml`): an AWS CodeConnections connection watches the repo, and CodeBuild runs `buildspec.yml` (ruff, pytest, site build, `cdk deploy HireGuardStack-prod`). No AWS keys are stored in GitHub, and the build role can only assume the CDK bootstrap roles. GitHub Actions (`.github/workflows/ci.yml`) still runs the same checks on every push and pull request.

One-time setup (AWS CLI signed in, `cdk bootstrap` done):

```bash
./setup-pipeline.sh     # creates the HireGuard-Pipeline stack; the GitHub connection starts as PENDING
# approve it once: CodePipeline console -> Settings -> Connections -> hireguard-github -> Update pending connection
./setup-pipeline.sh     # connection AVAILABLE: starts the first deploy
```

Cost at this traffic: CodeBuild includes a monthly free allowance of build minutes and CodePipeline V2 charges per action-minute, so a few deploys a month cost cents. Check current prices on the AWS pricing pages.

**Tear down:** `cd infra && cdk destroy HireGuardStack-prod -c stage=prod` removes the app, including its data. Delete the `HireGuard-Pipeline` stack in CloudFormation to remove auto-deploy, and the `hireguard-launch-<account id>` bucket to retire the Launch Stack button.

## Cost

At demo traffic the stack stays within or near the AWS free tier: Lambda, API Gateway and DynamoDB on-demand charge per request, CloudFront and S3 cost cents, and Secrets Manager is about $0.40 per secret per month. The AI second opinion is billed per token by Amazon Bedrock (Claude Haiku 4.5 is the low-cost Claude model, and each check is one short request). Comprehend charges per request, so it is off by default. Check current prices on the AWS pricing pages, and set an AWS Budgets alert.

## Project layout

```
backend/   detection engine (hireguard/), Lambda handlers (handlers/), local server (local_mode/), tests + samples
infra/     AWS CDK app (Python): the whole stack, plus pipeline.yaml for auto-deploy
frontend/  React + Vite website; prebuilt/ is the built copy run.py serves
run.py     run HireGuard on your computer (python3 run.py --share)
deploy.sh  build + test + deploy
publish-launch.sh  publish the template and code for the Launch Stack button
setup-pipeline.sh  one-time setup for auto-deploy (CodePipeline)
buildspec.yml      test + deploy steps the pipeline runs
```

## Status

MVP. Next: frontend tests, more genuine samples to keep false alarms low.
