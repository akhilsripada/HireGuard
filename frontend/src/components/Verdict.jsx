import Icon from './Icon'
import { LABELS } from '../copy'

export function ScoreRing({ score }) {
  return (
    <div className="ring">
      <span className="ring__score">{score}</span>
      <span className="ring__of">out of 100</span>
    </div>
  )
}

export function RiskMeter({ score }) {
  const pct = Math.max(0, Math.min(100, score))
  return (
    <div>
      <div className="meter__labels" aria-hidden="true">
        <span>Safe</span>
        <span>Suspicious</span>
        <span>Likely scam</span>
      </div>
      <div className="meter__bar" role="img" aria-label={`Risk meter at ${score} out of 100`}>
        <div className="meter__marker" style={{ left: `${pct}%` }} />
      </div>
    </div>
  )
}

export function VerdictCard({ result }) {
  const copy = LABELS[result.label]
  const n = result.flags.length
  const heading =
    n === 0 ? 'We found no red flags in this message' : `We found ${n} red flag${n === 1 ? '' : 's'} in this message`
  return (
    <section aria-label="Overall result" className={`verdict ${copy.className}`}>
      <div className="verdict__top">
        <ScoreRing score={result.score} />
        <div className="verdict__text">
          <p className="pill">
            <Icon name={copy.icon} size={16} strokeWidth={2.4} />
            {copy.pill}
          </p>
          <h1>{heading}</h1>
          <p className="verdict__advice">{copy.advice}</p>
        </div>
      </div>
      <div className="verdict__meter">
        <RiskMeter score={result.score} />
      </div>
    </section>
  )
}
