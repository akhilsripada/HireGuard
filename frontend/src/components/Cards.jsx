import Icon from './Icon'
import { severityOf } from '../copy'

// Flags whose evidence is a sentence copied from the message: shown in quotes
const QUOTED = new Set([
  'PAY_UPFRONT', 'GIFT_CARD_CRYPTO', 'FAKE_CHECK', 'ASKS_SENSITIVE_DATA', 'TASK_SCAM', 'RESHIPPING',
  'CHAT_APP_INTERVIEW', 'NO_INTERVIEW', 'TOO_GOOD_PAY', 'URGENCY',
])

export function FlagCard({ flag }) {
  const sev = severityOf(flag.points)
  return (
    <article className="flag">
      <div className="flag__side">
        <span className={`tag ${sev.className}`}>{sev.label}</span>
        <span className="flag__points">+{flag.points}</span>
      </div>
      <div className="flag__body">
        <h3>{flag.title}</h3>
        <p className="flag__why">{flag.why}</p>
        <p className="snippet snippet--lg">{QUOTED.has(flag.id) ? `"${flag.evidence}"` : flag.evidence}</p>
      </div>
    </article>
  )
}

export function CheckCard({ icon, tone, title, children }) {
  return (
    <div className="card check-card">
      <span className={`icon-tile tile--${tone}`}>
        <Icon name={icon} size={22} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}

export function TrendCard({ rank, name, trend, desc, sample, count, period }) {
  const rising = trend === 'RISING'
  return (
    <article className="card trend-card">
      <span className="rank">{rank}</span>
      <div className="trend-card__body">
        <div className="trend-card__top">
          <h3>{name}</h3>
          <span className={`tag ${rising ? 'tag--rising' : 'tag--common'}`}>{rising ? 'Rising' : 'Common'}</span>
        </div>
        <p>{desc}</p>
        <p className="snippet">{sample}</p>
        <p className="count">
          {count} message{count === 1 ? '' : 's'} flagged this {period}
        </p>
      </div>
    </article>
  )
}
