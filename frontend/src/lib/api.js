// API client. In mock mode (local, no AWS) it returns the sample responses in src/mocks.
import { getConfig } from './config'
import { currentUser } from './auth'
import scamMock from '../mocks/scan-likely-scam.json'
import suspiciousMock from '../mocks/scan-suspicious.json'
import safeMock from '../mocks/scan-safe.json'
import statsMock from '../mocks/stats-week.json'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

const MESSAGES = {
  429: 'Too many checks in a short time. Please wait a minute and try again.',
  401: 'Please sign in to report a scammer.',
  500: 'Something went wrong on our side. Please try again in a minute.',
}

async function call(path, { method = 'GET', body, auth = false } = {}) {
  const { apiUrl } = getConfig()
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const user = currentUser()
    if (user) headers.Authorization = `Bearer ${user.token}`
  }
  let res
  try {
    res = await fetch(`${apiUrl}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined })
  } catch {
    throw new ApiError(MESSAGES[500], 0)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = res.status === 400 && data.error ? data.error : MESSAGES[res.status] || MESSAGES[500]
    throw new ApiError(msg, res.status)
  }
  return data
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function mockScan({ message }) {
  const m = message.toLowerCase()
  if (/(vendor|gift card|telegram|whatsapp|check|crypto|ssn)/.test(m)) return scamMock
  if (/(urgent|within \d+ hours|limited)/.test(m)) return suspiciousMock
  return safeMock
}

let mockReports = 14

export async function scanMessage(input) {
  if (getConfig().mock) {
    await wait(600)
    return structuredClone(mockScan(input))
  }
  return call('/scan', { method: 'POST', body: input })
}

export async function reportContact(report) {
  if (getConfig().mock) {
    await wait(500)
    mockReports += 1
    return { reportCount: mockReports }
  }
  return call('/report', { method: 'POST', body: report, auth: true })
}

export async function getStats(range) {
  if (getConfig().mock) {
    await wait(200)
    return { ...statsMock, range }
  }
  return call(`/stats?range=${encodeURIComponent(range)}`)
}
