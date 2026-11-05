import Icon from './Icon'
import { linkProps } from '../lib/router'

export function Logo() {
  return (
    <a className="logo" {...linkProps('/')}>
      <span className="logo__tile">
        <Icon name="shield" size={22} />
      </span>
      <span className="logo__name">HireGuard</span>
    </a>
  )
}

function scrollTo(id) {
  return (e) => {
    const el = document.getElementById(id)
    if (el) {
      e.preventDefault()
      el.scrollIntoView({ behavior: 'smooth' })
    }
  }
}

// variant: 'home' | 'result' | 'report'
export function Header({ variant = 'home', user, onSignIn, onSignOut }) {
  return (
    <header className="header">
      <nav className="header__inner" aria-label="Main">
        <Logo />
        {variant === 'home' && (
          <div className="nav">
            <a className="nav__link" href="/#how" onClick={scrollTo('how')}>How it works</a>
            <a className="nav__link" href="/#trending" onClick={scrollTo('trending')}>Trending scams</a>
            <a className="nav__link" {...linkProps('/library')}>Scam library</a>
            <a className="nav__link" {...linkProps('/report')}>Report a scammer</a>
            {user ? (
              <button type="button" className="btn btn--secondary btn--nav" onClick={onSignOut}>Sign out</button>
            ) : onSignIn ? (
              <button type="button" className="btn btn--secondary btn--nav" onClick={onSignIn}>Sign in</button>
            ) : null}
          </div>
        )}
        {variant === 'result' && (
          <a className="btn btn--secondary btn--nav" {...linkProps('/')}>
            <Icon name="chevronLeft" size={18} />
            Scan another message
          </a>
        )}
        {variant === 'report' && user && (
          <div className="user">
            <span className="avatar" aria-hidden="true">{(user.email || '?').charAt(0).toUpperCase()}</span>
            <span>Signed in</span>
            <button type="button" className="linklike" onClick={onSignOut}>Sign out</button>
          </div>
        )}
      </nav>
    </header>
  )
}

export function Footer({ local = false }) {
  return (
    <footer className="footer">
      <div className="footer__inner">
        <span>HireGuard · A student project · {local ? 'Running locally' : 'Deployed on AWS'}</span>
        <span>
          Not legal advice. When in doubt, report to <a href="https://reportfraud.ftc.gov" target="_blank" rel="noreferrer">reportfraud.ftc.gov</a>
        </span>
      </div>
    </footer>
  )
}
