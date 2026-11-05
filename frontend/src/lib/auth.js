// Cognito Hosted UI sign-in (authorization code + PKCE). Only /report needs it.
import { getConfig } from './config'

const TOKEN_KEY = 'hg.idToken'
const VERIFIER_KEY = 'hg.pkceVerifier'
const RETURN_KEY = 'hg.returnTo'

const b64url = (bytes) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

function randomVerifier() {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  return b64url(bytes)
}

async function challengeFor(verifier) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return b64url(digest)
}

function decodeJwt(token) {
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(decodeURIComponent(escape(atob(part))))
  } catch {
    return null
  }
}

export function authEnabled() {
  const c = getConfig()
  return !c.mock && Boolean(c.cognitoDomain && c.cognitoClientId)
}

// Local mock mode has no login; the Report page shows this demo user.
export const MOCK_USER = { email: 'demo@hireguard.local', token: 'mock' }

export function currentUser() {
  if (getConfig().mock) return null
  const token = sessionStorage.getItem(TOKEN_KEY)
  if (!token) return null
  const claims = decodeJwt(token)
  if (!claims || claims.exp * 1000 < Date.now() + 30_000) {
    sessionStorage.removeItem(TOKEN_KEY)
    return null
  }
  return { email: claims.email || '', token }
}

export async function signIn(returnTo = '/report') {
  const { cognitoDomain, cognitoClientId } = getConfig()
  const verifier = randomVerifier()
  sessionStorage.setItem(VERIFIER_KEY, verifier)
  sessionStorage.setItem(RETURN_KEY, returnTo)
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: cognitoClientId,
    redirect_uri: `${window.location.origin}/auth/callback`,
    scope: 'openid email',
    code_challenge_method: 'S256',
    code_challenge: await challengeFor(verifier),
  })
  window.location.assign(`${cognitoDomain}/oauth2/authorize?${params}`)
}

export async function completeSignIn() {
  const { cognitoDomain, cognitoClientId } = getConfig()
  const code = new URLSearchParams(window.location.search).get('code')
  const verifier = sessionStorage.getItem(VERIFIER_KEY)
  if (!code || !verifier) throw new Error('Sign-in was cancelled or expired.')
  const res = await fetch(`${cognitoDomain}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: cognitoClientId,
      code,
      redirect_uri: `${window.location.origin}/auth/callback`,
      code_verifier: verifier,
    }),
  })
  if (!res.ok) throw new Error('Sign-in failed. Please try again.')
  const data = await res.json()
  sessionStorage.setItem(TOKEN_KEY, data.id_token)
  sessionStorage.removeItem(VERIFIER_KEY)
  const returnTo = sessionStorage.getItem(RETURN_KEY) || '/'
  sessionStorage.removeItem(RETURN_KEY)
  return returnTo
}

export function signOut() {
  sessionStorage.removeItem(TOKEN_KEY)
  const { cognitoDomain, cognitoClientId } = getConfig()
  if (authEnabled()) {
    const params = new URLSearchParams({ client_id: cognitoClientId, logout_uri: `${window.location.origin}/` })
    window.location.assign(`${cognitoDomain}/logout?${params}`)
  }
}
