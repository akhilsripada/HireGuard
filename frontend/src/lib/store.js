// Holds the latest scan between pages.
// The scan result is kept in sessionStorage so a page refresh on /result still works.
// The original message text is kept in memory only and is never stored or sent back by the API.
const KEY = 'hg.lastScan'
let lastMessage = ''

export function saveScan(result, input) {
  lastMessage = input.message
  const safe = { result, senderEmail: input.senderEmail || '', link: input.link || '' }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(safe))
  } catch {
    // storage blocked: memory only
  }
  memory = safe
}

let memory = null

export function loadScan() {
  if (memory) return { ...memory, message: lastMessage }
  try {
    const raw = sessionStorage.getItem(KEY)
    if (raw) {
      memory = JSON.parse(raw)
      return { ...memory, message: lastMessage }
    }
  } catch {
    // ignore
  }
  return null
}
