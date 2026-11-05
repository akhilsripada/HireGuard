import { useEffect, useState } from 'react'
import Icon from '../components/Icon'
import { Field } from '../components/Field'
import { CheckCard, TrendCard } from '../components/Cards'
import { ApiError, getStats, scanMessage } from '../lib/api'
import { navigate, linkProps } from '../lib/router'
import { saveScan } from '../lib/store'
import { TREND_TYPES } from '../copy'

const MIN = 20
const MAX = 5000
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

function validate({ message, senderEmail, link }) {
  const errors = {}
  if (message.trim().length < MIN) errors.message = 'Paste at least 20 characters.'
  else if (message.length > MAX) errors.message = 'Messages can be up to 5,000 characters.'
  if (senderEmail && !EMAIL_RE.test(senderEmail.trim())) errors.senderEmail = 'Enter a valid email address.'
  if (link && !/^https?:\/\/\S+\.\S+/i.test(link.trim())) errors.link = 'Enter a full link starting with https://'
  return errors
}

function ScanPanel() {
  const [form, setForm] = useState({ message: '', senderEmail: '', link: '' })
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [loading, setLoading] = useState(false)
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    const errs = validate(form)
    setErrors(errs)
    setApiError('')
    if (Object.keys(errs).length) return
    const input = {
      message: form.message,
      senderEmail: form.senderEmail.trim() || undefined,
      link: form.link.trim() || undefined,
    }
    setLoading(true)
    try {
      const result = await scanMessage(input)
      saveScan(result, input)
      navigate('/result')
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : 'Something went wrong on our side. Please try again in a minute.')
      setLoading(false)
    }
  }

  const tooShort = form.message.trim().length < MIN
  return (
    <section aria-label="Scan a message" className="panel">
      <h2>Check a message</h2>
      <form className="stack" onSubmit={submit} noValidate>
        <Field id="msg" label="Job post or message" error={errors.message}>
          <textarea
            id="msg"
            className="textarea"
            rows={7}
            placeholder="Paste the full job post, email or text here…"
            value={form.message}
            onChange={set('message')}
            readOnly={loading}
            maxLength={MAX + 100}
            aria-invalid={Boolean(errors.message)}
            aria-describedby={errors.message ? 'msg-error' : undefined}
          />
        </Field>
        <div className="row">
          <Field id="sender" label="Sender email" optional error={errors.senderEmail}>
            <input id="sender" type="email" className="input" placeholder="recruiter@company.com" value={form.senderEmail} onChange={set('senderEmail')} readOnly={loading} aria-invalid={Boolean(errors.senderEmail)} />
          </Field>
          <Field id="link" label="Link in the message" optional error={errors.link}>
            <input id="link" type="url" className="input" placeholder="https://…" value={form.link} onChange={set('link')} readOnly={loading} aria-invalid={Boolean(errors.link)} />
          </Field>
        </div>
        {apiError && <p className="alert" role="alert">{apiError}</p>}
        <button type="submit" className="btn btn--primary btn--block" disabled={tooShort || loading}>
          {loading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Checking…
            </>
          ) : (
            <>
              <Icon name="search" />
              Check for scam
            </>
          )}
        </button>
        <p className="note">
          <Icon name="lock" size={16} />
          We only keep the score and red-flag types. Emails, phone numbers and domains are hashed before saving.
        </p>
      </form>
    </section>
  )
}

function Trending() {
  const [range, setRange] = useState('week')
  const [state, setState] = useState({ loading: true, types: [], error: false })

  useEffect(() => {
    let live = true
    setState((s) => ({ ...s, loading: true }))
    getStats(range)
      .then((d) => live && setState({ loading: false, types: d.types || [], error: false }))
      .catch(() => live && setState({ loading: false, types: [], error: true }))
    return () => {
      live = false
    }
  }, [range])

  const items = state.types.filter((t) => TREND_TYPES[t.type])
  return (
    <section id="trending" className="section">
      <div className="section-head">
        <div>
          <h2>Trending scams</h2>
          <p className="section__lead">The scam types people report most on HireGuard. Know the pattern before it reaches you. <a {...linkProps('/library')}>Browse the scam library</a></p>
        </div>
        <div className="segmented" role="group" aria-label="Time range">
          <button type="button" aria-pressed={range === 'week'} onClick={() => setRange('week')}>This week</button>
          <button type="button" aria-pressed={range === 'month'} onClick={() => setRange('month')}>This month</button>
        </div>
      </div>
      {!state.loading && items.length === 0 ? (
        <div className="card">
          <p>{state.error ? "Trending scams couldn't load right now." : 'No reports yet this ' + range + '. Be the first to report a scam.'}</p>
        </div>
      ) : (
        <div className="grid-trend" aria-busy={state.loading}>
          {items.map((t, i) => (
            <TrendCard key={t.type} rank={i + 1} trend={t.trend} count={t.count} period={range} {...TREND_TYPES[t.type]} />
          ))}
        </div>
      )}
    </section>
  )
}

export default function Home() {
  return (
    <main className="main">
      <div className="hero">
        <section className="hero__text">
          <p className="badge">Free · No account needed</p>
          <h1>Is this job offer real?</h1>
          <p className="lead">
            Paste a job post, recruiter email or text message. HireGuard checks it against known scam patterns, the sender's domain and community reports, and shows you exactly what looks wrong.
          </p>
          <ul className="checks">
            {['Clear score from 0 to 100', 'Every red flag explained in plain words', 'Your message is never stored'].map((t) => (
              <li key={t}>
                <Icon name="check" color="var(--green)" strokeWidth={2.2} />
                {t}
              </li>
            ))}
          </ul>
        </section>
        <ScanPanel />
      </div>

      <section id="how" className="section">
        <h2>What HireGuard checks</h2>
        <p className="section__lead">Four independent signals add up to one score. You see every point and where it came from.</p>
        <div className="grid-checks">
          <CheckCard icon="card" tone="red" title="Payment requests">
            Gift cards, crypto, "buy your equipment first," check-deposit tricks.
          </CheckCard>
          <CheckCard icon="chat" tone="amber" title="How they contact you">
            Moving you to WhatsApp or Telegram, text-only "interviews," pressure to reply fast.
          </CheckCard>
          <CheckCard icon="globe" tone="blue" title="Sender & domain">
            Free email posing as a company, lookalike domains, sites registered days ago.
          </CheckCard>
          <CheckCard icon="people" tone="green" title="Community reports">
            If other job seekers reported the same sender, you'll see it instantly.
          </CheckCard>
        </div>
      </section>

      <Trending />

      <section className="banner">
        <div>
          <p className="eyebrow">Why this matters</p>
          <p className="banner__text">
            Reported losses to job scams in the US grew from <strong>$90 million</strong> in 2020 to <strong>$501 million</strong> in 2024.
          </p>
          <p className="banner__src">Source: FTC Consumer Sentinel data</p>
        </div>
        <a className="btn btn--light" {...linkProps('/report')}>Report a scam you received</a>
      </section>
    </main>
  )
}
