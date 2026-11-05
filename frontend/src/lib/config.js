// Runtime config. On AWS, CDK writes /config.json on every deploy; run.py serves its own
// /config.json (local: true). With `npm run dev` there is none, so we fall back to
// /config.local.json (mock mode, sample data).
let cached

export async function loadConfig() {
  if (cached) return cached
  for (const path of ['/config.json', '/config.local.json']) {
    try {
      const res = await fetch(path, { cache: 'no-store' })
      if (res.ok && (res.headers.get('content-type') || '').includes('json')) {
        cached = await res.json()
        return cached
      }
    } catch {
      // try the next one
    }
  }
  cached = { mock: true, apiUrl: '' }
  return cached
}

export function getConfig() {
  if (!cached) throw new Error('config not loaded')
  return cached
}
