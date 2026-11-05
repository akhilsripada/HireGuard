// All user-facing text that depends on data lives here (UI spec sections 3–6).

export const LABELS = {
  LIKELY_SCAM: {
    className: 'v-scam',
    pill: 'Likely scam',
    icon: 'warning',
    advice: "Don't reply, don't pay anything, and don't share personal or bank details.",
    steps: [
      "Stop replying and don't click the link.",
      'Look the company up yourself and apply only through its official careers site.',
      'If you paid or shared details, contact your bank right away.',
      'FTC',
    ],
  },
  SUSPICIOUS: {
    className: 'v-suspicious',
    pill: 'Suspicious',
    icon: 'warning',
    advice: 'Some signs look wrong. Verify the company before you reply or share anything.',
    steps: [
      "Find the company's official careers page yourself.",
      'Ask for a video or phone interview.',
      'Never pay or share bank details before a written offer.',
      'FTC_UNSURE',
    ],
  },
  SAFE: {
    className: 'v-safe',
    pill: 'Looks safe',
    icon: 'checkCircle',
    advice: "We didn't find common scam signs. Still apply through the company's official site.",
    steps: [
      "Check the role on the company's own careers page.",
      'Never pay to get a job.',
      'Come back and scan any follow-up messages.',
    ],
  },
}

export function severityOf(points) {
  if (points >= 25) return { label: 'High', className: 'tag--high' }
  if (points >= 10) return { label: 'Medium', className: 'tag--medium' }
  return { label: 'Low', className: 'tag--low' }
}

export const SKIPPED_NAMES = {
  domain_age: 'domain age',
  safe_browsing: 'Safe Browsing',
  community_reports: 'community reports',
  ai_signal: 'AI signal',
  history: 'scan history',
}

// Trending scam types: copy for each type returned by GET /stats
export const TREND_TYPES = {
  TASK_SCAMS: {
    name: 'Task scams',
    desc: 'You "rate products" or "boost apps" for commission, then must deposit money (often crypto) to unlock your earnings.',
    sample: '"Complete 40 tasks to unlock your $800 commission"',
  },
  PAY_FOR_EQUIPMENT: {
    name: 'Pay-for-equipment offers',
    desc: 'A fake employer sends a check or asks you to buy a laptop from their "vendor" before you start.',
    sample: '"Purchase your home-office kit through our approved vendor"',
  },
  BRAND_IMPERSONATION: {
    name: 'Big-brand recruiter impersonation',
    desc: 'Messages claim to be from well-known companies but come from free email addresses or lookalike domains.',
    sample: 'hr.talent.team@gmail.com → "Recruiting at a Fortune 500 company"',
  },
  RESHIPPING: {
    name: 'Reshipping "logistics" jobs',
    desc: 'You receive packages at home and forward them, unknowingly moving goods bought with stolen cards.',
    sample: '"Quality inspector: receive, inspect and reship parcels from home"',
  },
  FAKE_CHECK: {
    name: 'Fake-check scams',
    desc: 'You deposit a check, send part of the money on, and the check bounces days later.',
    sample: '"Deposit the check and send the rest to our supplier"',
  },
  UNTRACEABLE_PAYMENT: {
    name: 'Gift card and crypto payments',
    desc: 'The "employer" wants money by gift card, crypto or instant transfer, which can\'t be traced or refunded.',
    sample: '"Buy three gift cards and send photos of the codes"',
  },
  SENSITIVE_DATA: {
    name: 'Early SSN or bank requests',
    desc: 'They ask for your SSN, bank login or ID photos before any real offer or onboarding system.',
    sample: '"Reply with your SSN and routing number to process payroll"',
  },
  CHAT_APP_INTERVIEW: {
    name: 'Chat-app-only interviews',
    desc: 'The whole "interview" happens over Telegram or WhatsApp text, so nobody can identify the scammer.',
    sample: '"Interviews are conducted on Telegram"',
  },
}

export const PLATFORM_OPTIONS = [
  ['EMAIL', 'Email'],
  ['TEXT', 'Text message'],
  ['LINKEDIN', 'LinkedIn'],
  ['JOB_SITE', 'Indeed or another job site'],
  ['CHAT_APP', 'WhatsApp / Telegram'],
]

export const CONTACT_TYPES = {
  EMAIL: { option: 'Email address', label: "Scammer's email address", type: 'email', placeholder: 'name@example.com' },
  PHONE: { option: 'Phone number', label: "Scammer's phone number", type: 'tel', placeholder: '+1 555 010 2000' },
  DOMAIN: { option: 'Website', label: "Scammer's website", type: 'url', placeholder: 'https://…' },
}

export function timeAgo(iso) {
  if (!iso) return ''
  const mins = Math.max(1, Math.round((Date.now() - Date.parse(iso)) / 60000))
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'} ago`
  const hours = Math.round(mins / 60)
  if (hours < 48) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.round(hours / 24)
  return `${days} days ago`
}

// Short names for flags, used as chips in the scam library
export const FLAG_NAMES = {
  PAY_UPFRONT: 'Pay before you start',
  GIFT_CARD_CRYPTO: 'Gift card / crypto',
  FAKE_CHECK: 'Fake check',
  ASKS_SENSITIVE_DATA: 'Asks for SSN / bank',
  TASK_SCAM: 'Task scam',
  RESHIPPING: 'Reshipping',
  CHAT_APP_INTERVIEW: 'Chat-app interview',
  NO_INTERVIEW: 'No interview',
  TOO_GOOD_PAY: 'Too-good pay',
  URGENCY: 'Urgency',
  FREE_EMAIL_BIG_BRAND: 'Free email, big brand',
  FREE_EMAIL_HR: 'HR on free email',
  LOOKALIKE_DOMAIN: 'Lookalike domain',
  NEW_DOMAIN: 'New domain',
  UNSAFE_LINK: 'Unsafe link',
  COMMUNITY_REPORTED: 'Reported before',
  MULTIPLE_SIGNS: 'Several signs',
  AI_SIGNAL: 'AI signal',
}

export const SCAM_TYPE_NAMES = {
  ...Object.fromEntries(Object.entries(TREND_TYPES).map(([k, v]) => [k, v.name])),
  OTHER: 'Other scams',
  OTHER_SCAM: 'Other scam',
  LIKELY_GENUINE: 'Looks genuine',
  UNCLEAR: 'Unclear',
}

export const PLATFORM_NAMES = Object.fromEntries(PLATFORM_OPTIONS)

export function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
