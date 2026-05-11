/**
 * The fetch wrapper every backend call goes through.
 *
 * It exists for one reason: to make failures distinguishable. A CORS misconfiguration and a
 * 500 both surface as "it didn't work" without this, and they need completely different
 * fixes — so `ApiError.kind` separates them.
 */

import { env } from '@/lib/env'
import { accessToken } from '@/lib/supabase'

export type ApiErrorKind = 'network' | 'timeout' | 'unauthorized' | 'http'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null

  constructor(kind: ApiErrorKind, message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
  }
}

const TIMEOUT_MS = 30_000

export interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
  /** Streaming responses are read by the caller, so skip JSON parsing. */
  raw?: boolean
  timeoutMs?: number
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, raw = false, timeoutMs = TIMEOUT_MS } = options

  // Read the token per request rather than caching it: it refreshes mid-session, and a
  // stale copy produces 401s that look like the user was signed out.
  const token = await accessToken()

  const timeout = new AbortController()
  const timer = setTimeout(() => timeout.abort(), timeoutMs)
  signal?.addEventListener('abort', () => timeout.abort(), { once: true })

  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method,
      headers: {
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: timeout.signal,
    })
  } catch {
    clearTimeout(timer)
    if (timeout.signal.aborted && !signal?.aborted) {
      throw new ApiError('timeout', `Request to ${path} timed out.`)
    }
    // fetch only rejects for network-level failures — DNS, refused connection, or a CORS
    // preflight the browser blocked. The backend was never reached.
    throw new ApiError(
      'network',
      `Could not reach the API at ${env.apiBaseUrl}. Is the backend running, and does its ALLOWED_ORIGINS include this origin?`,
    )
  }
  clearTimeout(timer)

  if (response.status === 401) {
    throw new ApiError('unauthorized', 'Session expired or not signed in.', 401)
  }

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) detail = payload.detail
    } catch {
      // Non-JSON error body; the status text is all we have.
    }
    throw new ApiError('http', detail, response.status)
  }

  if (raw) return response as unknown as T
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
