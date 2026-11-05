# HireGuard

**Is this job offer real?** Paste a job post, recruiter email or text message and HireGuard gives it a 0–100 scam-risk score, with every red flag explained and the exact sentence that triggered it.

Job scams are growing fast: US reports of job and employment-agency scams tripled from 2020 to 2024, and reported losses grew from **$90 million to $501 million** ([FTC data via Insurance Journal](https://www.insurancejournal.com/news/national/2025/03/10/815001.htm)).

The whole app is serverless on AWS and deploys with one command.

## How it works

```
Browser ──> CloudFront + S3 (React site)
   │
   └──> API Gateway (HTTP API, throttled, CORS locked to the site)
          ├── POST /scan    -> Scan Lambda   -> rules engine, RDAP, Safe Browsing, Reports lookup -> DynamoDB Scans
          ├── POST /report  -> Report Lambda (Cognito login) -> DynamoDB Reports (hashed contacts only)
          └── GET  /stats   -> Stats Lambda  -> DynamoDB Scans (byDay index)
CloudWatch dashboard + alarms · Secrets Manager for API keys · all in one CDK stack
```

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

Bands: **0–33 Safe · 34–66 Suspicious · 67–100 Likely scam.** Weights live in `backend/hireguard/config.py` and are tuned against the sample set in `backend/tests/samples` (15 scams, 16 genuine recruiter messages, 5 edge cases). Current result: every scam sample scores Likely scam and every genuine sample scores Safe.

External checks (RDAP domain age, Google Safe Browsing, optional Amazon Comprehend) have a 1.5 s timeout. If one fails, the scan still returns and lists it in `checksSkipped`.

**Privacy:** message text is never stored or logged. Reported emails, phones and domains are stored only as SHA-256 hashes.

## Features

- **Scan**: paste a job message, get a 0–100 score with every red flag explained.
- **AI second opinion**: Claude on Amazon Bedrock (`POST /analyze`) explains the scam type, the tactics used, questions a real recruiter could answer and how to verify. It never changes the rule-based score; the message is treated strictly as data, the answer is forced into a fixed JSON shape and clipped, and the route has its own tight rate limit.
- **Report**: signed-in users report an email, phone or website (stored only as a SHA-256 hash), and can choose to share the scanned message to the library.
- **Scam library** (`/library`): past scam messages with names, emails, phones and links removed; scam websites reported by 3+ people; and a one-at-a-time lookup for any email, phone or website. Emails and phone numbers are never listed publicly, since a spoofed address could wrongly brand a real person.
- **Trending scams**: most common scam types this week or month.

## Run it locally (no AWS needed)

```bash
# backend tests
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python tests/samples/make_samples.py && pytest -q

# website with sample data (mock mode)
cd ../frontend && npm install && npm run dev     # http://localhost:5173
```

## Deploy to AWS

Prerequisites: Python 3.12+, Node 20+, Docker not required, AWS CLI v2 signed in to your account, `npm install -g aws-cdk`, and `cdk bootstrap` (deploy.sh runs it for you). Region: your AWS profile's region, else `us-east-2`; override with `HG_REGION=us-east-1 ./deploy.sh`.

```bash
./deploy.sh            # stage "prod"
./deploy.sh akhil      # a separate copy for testing
```

It runs the tests, builds the site, deploys the stack and prints the website URL.

**AI feature:** the first time, open the Amazon Bedrock console in your region, go to **Model catalog**, open **Claude Haiku 4.5** and complete any one-time access step AWS asks for. Until then the AI card shows "AI analysis isn't available right now" and everything else works. To use another model: `-c bedrockModel=<inference profile id>`. Optional flags (pass to `cdk deploy` in `infra/`): `-c alertEmail=you@example.com` for alarm emails, `-c aiSignal=true` to turn on the Comprehend signal.

After the first deploy, put a [Google Safe Browsing](https://developers.google.com/safe-browsing/v4/get-started) API key into the secret named in the `SafeBrowsingSecretName` output (`{"apiKey": "..."}`). Until then the check is skipped.

**Tear down:** `cd infra && cdk destroy HireGuardStack-prod -c stage=prod` removes everything, including data.

## Cost

At demo traffic the stack stays within or near the AWS free tier: Lambda, API Gateway and DynamoDB on-demand charge per request, CloudFront and S3 cost cents, and Secrets Manager is about $0.40 per secret per month. Comprehend charges per request, so it is off by default. Check current prices on the AWS pricing pages, and set an AWS Budgets alert.

## Project layout

```
backend/   detection engine (hireguard/), Lambda handlers (handlers/), tests + samples
infra/     AWS CDK app (Python): the whole stack
frontend/  React + Vite website
docs/      design notes
deploy.sh  build + test + deploy
```

## Status

MVP. Next: Launch Stack button (CloudFormation template in S3), GitHub Actions deploy with OIDC, frontend tests, more genuine samples to keep false alarms low.
