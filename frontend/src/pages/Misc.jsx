import { useEffect, useState } from 'react'
import { completeSignIn } from '../lib/auth'
import { linkProps, navigate } from '../lib/router'

export function AuthCallback() {
  const [error, setError] = useState('')
  useEffect(() => {
    completeSignIn()
      .then((to) => navigate(to, { replace: true }))
      .catch((e) => setError(e.message))
  }, [])
  return (
    <main className="main">
      <div className="card center-card">
        <p>{error || 'Signing you in…'}</p>
        {error && (
          <p style={{ marginTop: 12 }}>
            <a {...linkProps('/report')}>Try again</a>
          </p>
        )}
      </div>
    </main>
  )
}

export function NotFound() {
  return (
    <main className="main">
      <div className="center-card">
        <h1 className="page-title">Page not found</h1>
        <p className="page-lead">That page doesn't exist.</p>
        <a className="btn btn--primary" {...linkProps('/')}>Go to HireGuard home</a>
      </div>
    </main>
  )
}
