"""Generates the sample JSON files. Run once: python tests/samples/make_samples.py

All samples are written by the team from public FTC/BBB scam descriptions.
No real people, emails or phone numbers; example.* domains for invented companies.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent

SCAM = [
    ("equipment-amazon", "Hi! Your resume was selected for a Remote Data Entry Associate role at Amazon ($42/hr). Interviews are conducted on Telegram - add @amzn_hr_team. Once hired, purchase your home-office kit ($450) through our approved vendor and you'll be reimbursed with your first check. Please respond within 2 hours to keep your spot.",
     "careers.amazon.hr@gmail.com", "https://amazon-remote-jobs.net/start", ["PAY_UPFRONT", "FREE_EMAIL_BIG_BRAND", "CHAT_APP_INTERVIEW"]),
    ("fake-check", "Congratulations, you have been hired as an Administrative Assistant. We will mail you a check for $2,800. Deposit the check using mobile deposit, keep $400 as your first week pay and send the remaining balance to our equipment supplier via Zelle.",
     "hr@brightpath-staffing.example", None, ["FAKE_CHECK"]),
    ("gift-card-assistant", "Hello, I am looking for a personal assistant to help with errands. First task: buy three $100 Apple gift cards and send me photos of the back of the cards. You will be paid $800 per week.",
     "david.m.hiring@outlook.com", None, ["GIFT_CARD_CRYPTO"]),
    ("task-scam", "Earn $300 a day from home! Complete 40 simple tasks rating hotels to unlock your commission. New members must top up their account with USDT to start the next set of tasks.",
     None, "https://hotel-boost-app.example/join", ["TASK_SCAM", "GIFT_CARD_CRYPTO"]),
    ("reshipping", "We are hiring a Package Inspector to work from home. You will receive parcels at your address, check them and reship them using the prepaid labels we email you. $2,500 per month, no experience needed.",
     "logistics.team.hiring@gmail.com", None, ["RESHIPPING"]),
    ("ssn-early", "Good news! You are selected for the Customer Support position at Walmart. To process payroll please reply with your SSN, bank account number and routing number today.",
     "walmart.careers.dept@yahoo.com", None, ["ASKS_SENSITIVE_DATA", "FREE_EMAIL_BIG_BRAND"]),
    ("no-interview-telegram", "You have been hired without an interview for our remote assistant role. Message our manager on WhatsApp to start immediately. Pay is $45/hr.",
     None, None, ["NO_INTERVIEW", "CHAT_APP_INTERVIEW"]),
    ("training-fee", "Thank you for applying. Before you start there is a $95 training fee for the certification course. Pay the fee to secure your position. Only 3 spots left, reply now.",
     "onboarding@careerfast-hr.example", None, ["PAY_UPFRONT", "URGENCY"]),
    ("lookalike-microsoft", "Dear candidate, Microsoft talent team would like to offer you a remote data analyst role. Download the onboarding app from our portal and buy the required laptop from our preferred vendor.",
     "talent@micr0soft-careers.com", "https://micr0soft-careers.com/onboard", ["LOOKALIKE_DOMAIN", "PAY_UPFRONT"]),
    ("crypto-salary", "We pay all remote staff in Bitcoin. To activate your employee wallet, send a $50 activation fee in crypto. Interview will be done over text chat.",
     None, None, ["GIFT_CARD_CRYPTO", "PAY_UPFRONT"]),
    ("mystery-shopper", "Mystery shopper job: we will send you a check for $1,950. Cash the check, evaluate a Walmart store, buy gift cards with the rest and send us the codes.",
     "shopper.program.us@gmail.com", None, ["FAKE_CHECK", "GIFT_CARD_CRYPTO"]),
    ("google-impersonation", "Hello, I am a recruiter for Google. You have been selected for a remote typing job, $38/hr, flexible hours. Interviews are done on Telegram. Please send a copy of your driver's license to proceed.",
     "google.recruit.team@gmail.com", None, ["FREE_EMAIL_BIG_BRAND", "CHAT_APP_INTERVIEW", "ASKS_SENSITIVE_DATA"]),
    ("text-message-task", "Hi, this is Lisa from the HR team. Part-time online job, earn $500 a day by liking videos for commission. Add me on WhatsApp to begin. Limited positions available.",
     None, None, ["TASK_SCAM", "CHAT_APP_INTERVIEW"]),
    ("equipment-check", "Welcome aboard! We will send you a check to purchase your work laptop and software from our approved vendor. Do not use any other store. Confirm within 24 hours.",
     "it.department.onboard@outlook.com", None, ["PAY_UPFRONT", "URGENCY"]),
    ("deloitte-lookalike", "Deloitte HR here. You are hired immediately for the remote auditor role. Fill the form at our site with your bank details for direct deposit.",
     "hr@deloitte-hiring.net", "https://deloitte-hiring.net/form", ["LOOKALIKE_DOMAIN", "NO_INTERVIEW", "ASKS_SENSITIVE_DATA"]),
    ("urgency-only", "We have an urgent opening for a remote coordinator. Please respond within 12 hours if interested, limited slots.",
     None, None, ["URGENCY"]),
]
# The urgency-only message should land Suspicious-or-Safe, not Likely scam.
SCAM_EXPECTED_LABEL = {"urgency-only": None}

GENUINE = [
    ("amazon-real", "Hi Priya, thanks for applying to the Software Development Engineer role at Amazon. We'd like to schedule a 45-minute phone screen with a member of the team. Please pick a time that works for you using the scheduling link. Best, Amazon Recruiting",
     "recruiting@amazon.com", "https://www.amazon.jobs/en/jobs/123456"),
    ("linkedin-inmail", "Hi Sam, I came across your profile on LinkedIn and think you'd be a great fit for a Data Analyst opening at Northwind Analytics. The role is hybrid in Austin and pays $85,000-$100,000. Would you be open to a 20-minute video call this week?",
     "jordan.lee@northwind.example", None),
    ("interview-schedule", "Thank you for your interest in the Marketing Coordinator position. We would like to invite you to a video interview on Zoom next Tuesday at 2 pm. Please confirm your availability by Friday.",
     "talent@contoso.example", None),
    ("offer-letter", "Congratulations! Attached is your formal offer letter for the Junior Accountant role. Your start date is March 3. Your laptop and equipment will be shipped to your home address at no cost to you. Please sign the offer in our HR portal.",
     "people-ops@fabrikam.example", None),
    ("recruiter-agency-gmail", "Hello, I'm an independent recruiter working with several healthcare clinics in Ohio. I have a Medical Billing Specialist opening, full time, $24/hr. Can we set up a quick phone call to discuss your experience?",
     "anna.recruits.ohio@gmail.com", None),
    ("referral-friend", "Hey! Saw your post that you're looking. My team is hiring a frontend engineer, I can refer you internally. Send me your resume and I'll submit it through our careers site.",
     "mike.chen@adatum.example", None),
    ("rejection", "Thank you for taking the time to interview with us for the Product Designer role. After careful consideration we have decided to move forward with another candidate. We wish you the best in your search.",
     "careers@woodgrove.example", None),
    ("background-check-official", "As the final step, our background check vendor, Sterling, will email you a secure link to complete the check. There is no cost to you. Please do not reply to this email with personal information.",
     "hr@tailspin.example", None),
    ("deadline-apply", "Applications for our summer internship close this Friday. Apply through our careers page and expect to hear back within two weeks. Interviews are held on Microsoft Teams.",
     "university@litware.example", "https://careers.litware.example/internships"),
    ("salary-discussion", "Thanks for the great conversation today. As discussed, the base salary for the Senior Engineer role is $165,000 plus equity. The next step is an onsite interview loop with four team members.",
     "recruiter@proseware.example", None),
    ("staffing-agency", "We have a temporary warehouse associate role in Columbus, 40 hours a week, $19/hr. Interviews are in person at our branch office on Main Street. Bring two forms of ID on your first day for I-9 verification.",
     "jobs@coho-staffing.example", None),
    ("internal-hr-onboarding", "Welcome to the team! Your first day is Monday. Please complete your direct deposit and tax forms in Workday before then. IT will ship your laptop this week; let us know if it hasn't arrived by Friday.",
     "onboarding@wingtip.example", None),
    ("networking-event", "Hi Alex, it was great meeting you at the career fair. Our engineering manager would love to chat about the Cloud Support Associate role. Are you free for a call on Thursday?",
     "recruiting@relecloud.example", None),
    ("teacher-job", "Thank you for applying to Lincoln Elementary. We would like to invite you for an interview with the principal and a short teaching demo next week. Please reply with two times that work for you.",
     "hr@lincoln-district.example", None),
    ("nurse-recruiter", "Hi Maria, I'm a nurse recruiter at Riverside Health. We have night-shift RN openings with a sign-on bonus. I'd love to schedule a phone screen to tell you more about the unit.",
     "maria.recruiting@riversidehealth.example", None),
    ("google-real", "Hi Dev, thanks for applying to the Associate Product Manager program at Google. Your application has moved to the next stage. You'll receive an email from our scheduling team to book your first interview.",
     "noreply@google.com", "https://careers.google.com/jobs/results/1234"),
]

EDGE = [
    ("empty-link", "Hi, we'd like to schedule an interview for the analyst role next week.", None, ""),
    ("emoji", "\U0001F680\U0001F680 Amazing remote job \U0001F4B0\U0001F4B0 message me \U0001F449\U0001F449", None, None),
    ("non-english", "Hola, gracias por postularte. Nos gustaría programar una entrevista por videollamada la próxima semana.", None, None),
    ("max-length", ("We are hiring for a role. " * 192)[:5000], None, None),
    ("lookalike-chars", "Amaz0n HR here, your job is ready.", "hr@amaz0n.com", None),
]


def write(folder, items, expected=None, must_fire=True):
    (HERE / folder).mkdir(exist_ok=True)
    for i, item in enumerate(items, 1):
        sid, message, sender, link = item[:4]
        doc = {
            "id": f"{folder}-{i:03d}-{sid}",
            "message": message,
            "senderEmail": sender,
            "link": link,
            "expectedLabel": expected(sid) if expected else None,
            "mustFire": item[4] if must_fire and len(item) > 4 else [],
            "mustNotFire": [],
            "source": "Written by the team from public FTC/BBB job-scam descriptions" if folder == "scam" else "Written by the team",
        }
        (HERE / folder / f"{doc['id']}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


write("scam", SCAM, lambda s: SCAM_EXPECTED_LABEL.get(s, "LIKELY_SCAM"))
write("genuine", GENUINE, lambda s: "SAFE")
write("edge", EDGE, lambda s: None, must_fire=False)
print("samples written")
