import { useState } from 'react'
import { Footer, Header } from './components/Layout'
import Home from './pages/Home'
import Result from './pages/Result'
import Report from './pages/Report'
import Library from './pages/Library'
import { AuthCallback, NotFound } from './pages/Misc'
import { usePath } from './lib/router'
import { authEnabled, currentUser, MOCK_USER, signIn, signOut } from './lib/auth'
import { getConfig } from './lib/config'

const VARIANTS = { '/': 'home', '/result': 'result', '/report': 'report', '/library': 'home' }

export default function App() {
  const path = usePath()
  const [, rerender] = useState(0)
  const user = currentUser() || (getConfig().mock && path === '/report' ? MOCK_USER : null)

  // No sign-in button when there is no login (local mode, mock mode)
  const onSignIn = authEnabled() ? () => signIn('/') : null
  const onSignOut = () => {
    signOut()
    rerender((n) => n + 1)
  }

  let page
  if (path === '/') page = <Home />
  else if (path === '/result') page = <Result />
  else if (path === '/report') page = <Report />
  else if (path === '/library') page = <Library />
  else if (path === '/auth/callback') page = <AuthCallback />
  else page = <NotFound />

  return (
    <div className="page">
      <Header variant={VARIANTS[path] || 'home'} user={user} onSignIn={onSignIn} onSignOut={onSignOut} />
      {page}
      {(path === '/' || path === '/library') && <Footer local={Boolean(getConfig().local)} />}
    </div>
  )
}
