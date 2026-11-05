import { useEffect, useState } from 'react'
import Icon from '../components/Icon'
import { Field } from '../components/Field'
import { ApiError, getLibrary, getReportedSites, lookupContact } from '../lib/api'
import { linkProps } from '../lib/router'
import { CONTACT_TYPES, FLAG_NAMES, PLATFORM_NAMES, SCAM_TYPE_NAMES, formatDate, timeAgo } from '../copy'

const FILTERS = [
  ['', 'All'],
  ['TASK_SCAMS', 'Task scams'],
  ['PAY_FOR_EQUIPMENT', 'Pay for equipment'],
  ['FAKE_CHECK', 'Fake checks'],
  ['BRAND_IMPERSONATION', 'Brand impersonation'],
  ['RESHIPPING', 'Reshipping'],
  ['UNTRACEABLE_PAYMENT', 'Gift card / crypto'],
  ['SENSITIVE_DATA', 'SSN / bank requests'],
]

function Lookup() {
  const [form, setForm] = useState({ contactType: 'EMAIL', contact: '' })
  const [state, setState] = useState({ status: 'idle' })
  const ct = CONTACT_TYPES[form.contactType]

  async function submit(e) {
    e.preventDefault()
    if (!form.contact.trim()) return setState({ status: 'error', error: 'Enter something to check.' })
    setState({ status: 'loading' })
    try {
      setState({ status: 'done', data: await lookupContact({ ...form, contact: form.contact.trim() }), checked: form.contact.trim() })
    } catch (err) {
      setState({ status: 'error', error: err instanceof ApiError ? err.message : 'Something went wrong. Please try again.' })
    }
  }

  const d = state.data
  return (
    <section className="panel" aria-labelledby="lookup-title">
      <h2 id="lookup-title">Has this contact been reported?</h2>
      <form className="stack" onSubmit={submit} noValidate>
        <div className="segmented segmented--fit" role="group" aria-label="Contact type">
          {Object.entries(CONTACT_TYPES).map(([key, t]) => (
            <button key={key} type="button" aria-pressed={form.contactType === key} onClick={() => { setForm({ contactType: key, contact: '' }); setState({ status: 'idle' }) }}>
              {t.option}
            </button>
          ))}
        </div>
        <div className="lookup-row">
          <Field id="lookup" label={ct.label.replace("Scammer's", 'The')} error={state.status === 'error' ? state.error : ''}>
            <input id="lookup" type={ct.type} className="input input--mono" placeholder={ct.placeholder} value={form.contact} onChange={(e) => setForm((f) => ({ ...f, contact: e.target.value }))} />
          </Field>
          <button type="submit" className="btn btn--primary" disabled={state.status === 'loading'}>
            {state.status === 'loading' ? <span className="spinner" aria-hidden="true" /> : <Icon name="search" />}
            Check
          </button>
        </div>
      </form>
      {state.status === 'done' && (
        d.reportCount > 0 ? (
          <div className="lookup-result lookup-result--hit" aria-live="polite">
            <Icon name="warning" size={22} color="var(--red)" />
            <div>
              <p className="lookup-result__title">Reported {d.reportCount} time{d.reportCount === 1 ? '' : 's'} as a scam</p>
              <p>
                Last report {timeAgo(d.lastReportedAt)}
                {d.platforms?.length ? ` · seen on ${d.platforms.map((p) => PLATFORM_NAMES[p] || p).join(', ')}` : ''}
                {d.claimedCompanies?.length ? ` · claimed to be ${d.claimedCompanies.join(', ')}` : ''}
                {d.lostMoneyCount ? ` · ${d.lostMoneyCount} people lost money or details` : ''}
              </p>
            </div>
          </div>
        ) : (
          <div className="lookup-result lookup-result--miss" aria-live="polite">
            <Icon name="checkCircle" size={22} color="var(--green)" />
            <div>
              <p className="lookup-result__title">No reports yet</p>
              <p>Nobody has reported this contact on HireGuard. That isn't a guarantee it's safe, so still scan the message.</p>
            </div>
          </div>
        )
      )}
      <p className="note">
        <Icon name="lock" size={16} />
        We only store a one-way hash of reported emails and phone numbers, so they can be checked one at a time but are never listed.
      </p>
    </section>
  )
}

function Sites() {
  const [state, setState] = useState({ loading: true, sites: [], min: 3 })
  useEffect(() => {
    getReportedSites()
      .then((d) => setState({ loading: false, sites: d.sites, min: d.minReports }))
      .catch(() => setState({ loading: false, sites: [], min: 3, error: true }))
  }, [])
  return (
    <section className="section" aria-labelledby="sites-title">
      <h2 id="sites-title">Reported scam websites</h2>
      <p className="section__lead">Websites reported by at least {state.min} different people. Don't enter any details on these sites.</p>
      {!state.loading && state.sites.length === 0 ? (
        <div className="card"><p>{state.error ? "This list couldn't load right now." : 'No websites have enough reports yet.'}</p></div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Website</th>
                <th scope="col">Pretends to be</th>
                <th scope="col" className="num">Reports</th>
                <th scope="col">Last reported</th>
              </tr>
            </thead>
            <tbody>
              {state.sites.map((s) => (
                <tr key={s.domain}>
                  <td className="mono">{s.domain}</td>
                  <td>{s.claimedCompanies.join(', ') || '—'}</td>
                  <td className="num">{s.reportCount}</td>
                  <td>{formatDate(s.lastReportedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Entry({ e }) {
  const scam = e.label === 'LIKELY_SCAM'
  return (
    <article className="card entry">
      <div className="entry__top">
        <span className={`tag ${scam ? 'tag--high' : 'tag--medium'}`}>{scam ? 'Likely scam' : 'Suspicious'} · {e.score}</span>
        <h3>{SCAM_TYPE_NAMES[e.scamType] || 'Other scams'}</h3>
        <span className="entry__meta">
          {e.claimedCompany && <>Pretended to be <strong>{e.claimedCompany}</strong> · </>}
          {PLATFORM_NAMES[e.platform] || 'Message'} · {formatDate(e.createdAt)}
        </span>
      </div>
      <p className="entry__text">{e.text}</p>
      <ul className="chips" aria-label="Red flags">
        {e.flagIds.filter((f) => FLAG_NAMES[f]).slice(0, 6).map((f) => (
          <li key={f} className="chip">{FLAG_NAMES[f]}</li>
        ))}
      </ul>
    </article>
  )
}

function PastScams() {
  const [type, setType] = useState('')
  const [state, setState] = useState({ loading: true, items: [], cursor: null })

  async function load(nextType, cursor) {
    setState((s) => ({ ...s, loading: true }))
    try {
      const d = await getLibrary({ type: nextType, cursor })
      setState((s) => ({ loading: false, items: cursor ? [...s.items, ...d.items] : d.items, cursor: d.cursor }))
    } catch {
      setState({ loading: false, items: [], cursor: null, error: true })
    }
  }

  useEffect(() => {
    load(type, '')
  }, [type])

  return (
    <section className="section" aria-labelledby="past-title">
      <div className="section-head">
        <div>
          <h2 id="past-title">Past scam messages</h2>
          <p className="section__lead">Real messages people received and chose to share. Names, emails, phone numbers and links are removed.</p>
        </div>
      </div>
      <div className="filters" role="group" aria-label="Filter by scam type">
        {FILTERS.map(([key, label]) => (
          <button key={key || 'all'} type="button" className="filter" aria-pressed={type === key} onClick={() => setType(key)}>
            {label}
          </button>
        ))}
      </div>
      {!state.loading && state.items.length === 0 ? (
        <div className="card"><p>{state.error ? "The library couldn't load right now." : 'No shared messages of this type yet.'}</p></div>
      ) : (
        <div className="entries" aria-busy={state.loading}>
          {state.items.map((e) => <Entry key={e.id} e={e} />)}
        </div>
      )}
      {state.cursor && (
        <button type="button" className="btn btn--secondary" style={{ marginTop: 20 }} onClick={() => load(type, state.cursor)} disabled={state.loading}>
          Load more
        </button>
      )}
    </section>
  )
}

export default function Library() {
  return (
    <main className="main">
      <div className="hero hero--library">
        <section className="hero__text">
          <p className="badge">Scam library</p>
          <h1 className="h1-lib">Learn from scams others received</h1>
          <p className="lead">
            Browse past scam messages, see which websites people have reported, and check whether an email, phone number or website has been reported before.
          </p>
          <a className="btn btn--secondary" {...linkProps('/report')}>Report a scam you received</a>
        </section>
        <Lookup />
      </div>
      <Sites />
      <PastScams />
    </main>
  )
}
