import { useEffect } from 'react'
import Icon from '../components/Icon'
import { VerdictCard } from '../components/Verdict'
import { FlagCard } from '../components/Cards'
import AiOpinion from '../components/AiOpinion'
import { loadScan } from '../lib/store'
import { linkProps, navigate } from '../lib/router'
import { LABELS, SKIPPED_NAMES } from '../copy'

function Step({ text }) {
  if (text === 'FTC')
    return (
      <li>
        Report it to the FTC at <a href="https://reportfraud.ftc.gov" target="_blank" rel="noreferrer">reportfraud.ftc.gov</a>.
      </li>
    )
  if (text === 'FTC_UNSURE')
    return (
      <li>
        If unsure, report it at <a href="https://reportfraud.ftc.gov" target="_blank" rel="noreferrer">reportfraud.ftc.gov</a>.
      </li>
    )
  return <li>{text}</li>
}

export default function Result() {
  const scan = loadScan()

  useEffect(() => {
    if (!scan) navigate('/', { replace: true })
  }, [scan])
  if (!scan) return null

  const { result, message } = scan
  const copy = LABELS[result.label]
  const skipped = (result.checksSkipped || []).map((s) => SKIPPED_NAMES[s] || s)
  const reported = result.flags.find((f) => f.id === 'COMMUNITY_REPORTED')

  return (
    <main className="main main--result">
      <VerdictCard result={result} />

      <div className="columns">
        <section className="columns__main">
          <h2>{result.flags.length ? 'Red flags found' : 'No red flags found'}</h2>
          {result.flags.length > 0 ? (
            <div className="flags">
              {result.flags.map((f) => (
                <FlagCard key={f.id} flag={f} />
              ))}
            </div>
          ) : (
            <div className="card">
              <p>None of our checks matched this message. That's a good sign, but always apply through the company's own website.</p>
            </div>
          )}
          {skipped.length > 0 && (
            <p className="skipped">Some checks were skipped: {skipped.join(', ')}. The score uses the remaining checks.</p>
          )}
          <AiOpinion message={message} flagIds={result.flags.map((f) => f.id)} />
          {message && (
            <details className="details">
              <summary>Show the message you scanned</summary>
              <p>{message}</p>
            </details>
          )}
        </section>

        <aside className="columns__side">
          <section className="card">
            <h2>What to do next</h2>
            <ol className="steps">
              {copy.steps.map((s) => (
                <Step key={s} text={s} />
              ))}
            </ol>
          </section>

          {result.communityReports > 0 && (
            <section className="community">
              <span className="icon-tile tile--white">
                <Icon name="people" size={22} />
              </span>
              <div>
                <h2>
                  Reported by {result.communityReports} other {result.communityReports === 1 ? 'person' : 'people'}
                </h2>
                <p>This sender was reported as a scam by other job seekers.{reported ? '' : ''}</p>
              </div>
            </section>
          )}

          <section className="card help">
            <h2>Help protect others</h2>
            <p>Reporting adds this sender to the community list so the next person gets warned.</p>
            <a className="btn btn--primary btn--block btn--sm" {...linkProps('/report?from=result')}>Report this scammer</a>
            <a className="btn btn--secondary btn--block" {...linkProps('/')}>Scan another message</a>
          </section>

          <p className="footnote">Score = sum of red-flag points, capped at 100. 0–33 safe, 34–66 suspicious, 67–100 likely scam.</p>
        </aside>
      </div>
    </main>
  )
}
