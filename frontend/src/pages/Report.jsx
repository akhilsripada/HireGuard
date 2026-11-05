import { useState } from 'react'
import Icon from '../components/Icon'
import { Field } from '../components/Field'
import { ApiError, reportContact } from '../lib/api'
import { authEnabled, currentUser, signIn } from '../lib/auth'
import { linkProps } from '../lib/router'
import { loadScan } from '../lib/store'
import { CONTACT_TYPES, PLATFORM_OPTIONS } from '../copy'

function prefill() {
  const scan = loadScan()
  if (!scan) return { contactType: 'EMAIL', contact: '', claimedCompany: '' }
  const brandFlag = scan.result.flags.find((f) => f.id === 'FREE_EMAIL_BIG_BRAND')
  const company = brandFlag ? (brandFlag.evidence.match(/claims "([^"]+)"/) || [])[1] || '' : ''
  if (scan.senderEmail) return { contactType: 'EMAIL', contact: scan.senderEmail, claimedCompany: company }
  if (scan.link) return { contactType: 'DOMAIN', contact: scan.link, claimedCompany: company }
  return { contactType: 'EMAIL', contact: '', claimedCompany: company }
}

function validate(form) {
  const v = form.contact.trim()
  if (!v) return 'Enter the scammer\'s contact.'
  if (form.contactType === 'EMAIL' && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) return 'Enter a valid email address.'
  if (form.contactType === 'PHONE' && v.replace(/\D/g, '').length < 7) return 'Enter a valid phone number.'
  if (form.contactType === 'DOMAIN' && !/\.\w{2,}/.test(v)) return 'Enter a valid website.'
  return ''
}

function Sidebar() {
  return (
    <aside className="columns__side">
      <section className="card">
        <h2 className="side-title">
          <Icon name="lock" color="var(--green)" />
          How we store reports
        </h2>
        <p className="side-text">
          The contact you report is turned into a one-way hash before it's saved. We can match future scans against it, but nobody can read the original back.
        </p>
        <p className="snippet snippet--lg" style={{ fontSize: 12 }}>sha256 → 9f2c…a71e</p>
      </section>
      <section className="card">
        <h2 className="side-title">Why sign in?</h2>
        <p className="side-text">Scanning is anonymous. Reporting needs an account so one person can't flood the list with fake reports.</p>
      </section>
      <section className="ftc">
        <h2>Also tell the FTC</h2>
        <p>
          Official reports help investigators. File one at <a href="https://reportfraud.ftc.gov" target="_blank" rel="noreferrer">reportfraud.ftc.gov</a>.
        </p>
      </section>
    </aside>
  )
}

export default function Report() {
  const user = currentUser()
  const needsLogin = authEnabled() && !user
  const [form, setForm] = useState(() => ({ ...prefill(), platform: 'EMAIL', details: '', lostMoney: false }))
  const [error, setError] = useState('')
  const [apiError, setApiError] = useState('')
  const [sending, setSending] = useState(false)
  const [done, setDone] = useState(null)
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))
  const backTo = loadScan() ? '/result' : '/'
  const ct = CONTACT_TYPES[form.contactType]

  async function submit(e) {
    e.preventDefault()
    const err = validate(form)
    setError(err)
    setApiError('')
    if (err) return
    setSending(true)
    try {
      const out = await reportContact({
        contactType: form.contactType,
        contact: form.contact.trim(),
        platform: form.platform,
        claimedCompany: form.claimedCompany.trim(),
        lostMoney: form.lostMoney,
      })
      setDone(out.reportCount)
    } catch (ex) {
      setApiError(ex instanceof ApiError ? ex.message : 'Something went wrong on our side. Please try again in a minute.')
    } finally {
      setSending(false)
    }
  }

  return (
    <main className="main main--result">
      <a className="back" {...linkProps(backTo)}>
        <Icon name="chevronLeft" size={18} />
        {backTo === '/result' ? 'Back to result' : 'Back to home'}
      </a>
      <h1 className="page-title">Report a scammer</h1>
      <p className="page-lead">Your report warns the next person who gets a message from the same sender. It takes about a minute.</p>

      <div className="columns" style={{ marginTop: 0 }}>
        {done !== null ? (
          <section className="form-card success" aria-live="polite">
            <span className="icon-tile tile--green">
              <Icon name="check" size={22} strokeWidth={2.4} />
            </span>
            <h2>Thanks — your report was saved</h2>
            <p>
              {done} {done === 1 ? 'person has' : 'people have'} now reported this contact.
            </p>
            <a className="btn btn--primary" {...linkProps('/')}>Scan another message</a>
          </section>
        ) : needsLogin ? (
          <section className="form-card">
            <h2 style={{ margin: 0, fontSize: 22 }}>Sign in to report</h2>
            <p style={{ margin: 0, fontSize: 16, color: 'var(--text-muted)' }}>
              Reporting needs a free account so the community list stays trustworthy. You'll come straight back here afterwards.
            </p>
            <button type="button" className="btn btn--primary" onClick={() => signIn('/report')}>Sign in or create an account</button>
          </section>
        ) : (
          <form className="form-card" onSubmit={submit} noValidate>
            <fieldset className="fieldset">
              <legend>What are you reporting?</legend>
              <div className="radios">
                {Object.entries(CONTACT_TYPES).map(([key, t]) => (
                  <label key={key} className={`radio-card${form.contactType === key ? ' radio-card--on' : ''}`}>
                    <input type="radio" name="kind" value={key} checked={form.contactType === key} onChange={() => setForm((f) => ({ ...f, contactType: key, contact: '' }))} />
                    {t.option}
                  </label>
                ))}
              </div>
            </fieldset>

            <Field id="contact" label={ct.label} error={error}>
              <input id="contact" type={ct.type} className="input input--mono" placeholder={ct.placeholder} value={form.contact} onChange={set('contact')} aria-invalid={Boolean(error)} />
            </Field>

            <div className="row row--wide">
              <Field id="where" label="Where did they contact you?">
                <select id="where" className="select" value={form.platform} onChange={set('platform')}>
                  {PLATFORM_OPTIONS.map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </Field>
              <Field id="company" label="Company they claimed to be">
                <input id="company" type="text" className="input" value={form.claimedCompany} onChange={set('claimedCompany')} maxLength={80} />
              </Field>
            </div>

            <Field id="what" label="What happened?" optional>
              <textarea id="what" className="textarea" rows={4} placeholder="e.g. They asked me to buy a laptop from their vendor before starting." value={form.details} onChange={set('details')} />
            </Field>

            <label className="checkbox">
              <input type="checkbox" checked={form.lostMoney} onChange={set('lostMoney')} /> I lost money or shared personal details
            </label>

            {apiError && <p className="alert" role="alert">{apiError}</p>}

            <div className="actions">
              <button type="submit" className="btn btn--primary" disabled={sending}>
                {sending ? (
                  <>
                    <span className="spinner" aria-hidden="true" />
                    Sending…
                  </>
                ) : (
                  'Submit report'
                )}
              </button>
              <a className="btn btn--secondary" {...linkProps(backTo)}>Cancel</a>
            </div>
          </form>
        )}
        <Sidebar />
      </div>
    </main>
  )
}
