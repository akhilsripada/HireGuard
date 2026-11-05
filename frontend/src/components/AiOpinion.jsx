import { useEffect, useState } from 'react'
import Icon from './Icon'
import { analyzeMessage } from '../lib/api'
import { getConfig } from '../lib/config'
import { SCAM_TYPE_NAMES } from '../copy'

// Runs after the score is shown, so a slow or failed AI call never blocks the result.
export default function AiOpinion({ message, flagIds }) {
  // A local copy (python3 run.py) has AI off unless it was started with --ai
  const off = Boolean(getConfig().local) && !getConfig().ai
  const [state, setState] = useState({ status: off ? 'off' : 'idle' })

  async function run() {
    setState({ status: 'loading' })
    try {
      setState({ status: 'done', data: await analyzeMessage({ message, flagIds }) })
    } catch (e) {
      setState({ status: 'error', error: e.message || "AI analysis isn't available right now." })
    }
  }

  useEffect(() => {
    if (message && !off) run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [message])

  if (!message) return null
  const d = state.data

  return (
    <section className="ai" aria-live="polite" aria-busy={state.status === 'loading'}>
      <div className="ai__head">
        <span className="icon-tile tile--purple">
          <Icon name="sparkle" size={22} />
        </span>
        <div>
          <h2>AI second opinion</h2>
          <p className="ai__sub">Claude on Amazon Bedrock · doesn't change the score</p>
        </div>
        {state.status === 'done' && (
          <span className="tag tag--ai">{d.confidence === 'HIGH' ? 'High' : d.confidence === 'MEDIUM' ? 'Medium' : 'Low'} confidence</span>
        )}
      </div>

      {state.status === 'loading' && (
        <div className="ai__loading">
          <span className="spinner spinner--dark" aria-hidden="true" />
          Reading the message…
        </div>
      )}

      {state.status === 'off' && (
        <div className="ai__error">
          <p>The AI second opinion is off in this local copy. Start it with <code>python3 run.py --ai</code> (needs AWS credentials with Amazon Bedrock access).</p>
        </div>
      )}

      {state.status === 'error' && (
        <div className="ai__error">
          <p>{state.error}</p>
          <button type="button" className="btn btn--secondary btn--nav" onClick={run}>Try again</button>
        </div>
      )}

      {state.status === 'done' && (
        <div className="ai__body">
          <p className="ai__type">
            Looks like: <strong>{SCAM_TYPE_NAMES[d.scamType] || 'Unclear'}</strong>
          </p>
          <p className="ai__summary">{d.summary}</p>
          {d.tactics.length > 0 && (
            <ul className="chips" aria-label="Tactics used">
              {d.tactics.map((t) => (
                <li key={t} className="chip">{t}</li>
              ))}
            </ul>
          )}
          <div className="ai__grid">
            {d.questionsToAsk.length > 0 && (
              <div>
                <h3>Questions a real recruiter can answer</h3>
                <ul className="ai__list">
                  {d.questionsToAsk.map((q) => <li key={q}>{q}</li>)}
                </ul>
              </div>
            )}
            {d.howToVerify.length > 0 && (
              <div>
                <h3>How to verify</h3>
                <ul className="ai__list">
                  {d.howToVerify.map((q) => <li key={q}>{q}</li>)}
                </ul>
              </div>
            )}
          </div>
          <p className="ai__note">AI can make mistakes. Your message was sent to Amazon Bedrock for this check only and isn't stored.</p>
        </div>
      )}
    </section>
  )
}
