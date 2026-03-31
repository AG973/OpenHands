import { emitLog } from './logger'

// Backend URL configuration
// In production (static serve), VITE_BACKEND_URL must point to the backend host.
// In dev mode, vite.config.ts proxy handles /api and /socket.io automatically.
// We strip trailing slashes to avoid double-slash issues.
const RAW_BACKEND = import.meta.env.VITE_BACKEND_URL || ''
export const BACKEND_URL = RAW_BACKEND.replace(/\/+$/, '')

export async function parseError(res: Response): Promise<string> {
  try {
    const text = await res.text()
    try {
      const json = JSON.parse(text)
      return json.detail || json.error || json.message || text
    } catch {
      return text || `HTTP ${res.status}`
    }
  } catch {
    return `HTTP ${res.status}`
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const url = `${BACKEND_URL}${path}`
  try {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } })
    if (!res.ok) {
      const errMsg = await parseError(res)
      emitLog('error', 'api', `GET ${path} failed: ${res.status} - ${errMsg}`)
      throw new Error(`GET ${path}: ${res.status} - ${errMsg}`)
    }
    emitLog('debug', 'api', `GET ${path} -> ${res.status}`)
    return await res.json()
  } catch (err) {
    if (!(err instanceof Error && err.message.startsWith('GET '))) {
      emitLog('error', 'api', `GET ${path}: ${err instanceof Error ? err.message : String(err)}`)
    }
    throw err
  }
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const url = `${BACKEND_URL}${path}`
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) {
      const errMsg = await parseError(res)
      emitLog('error', 'api', `POST ${path} failed: ${res.status} - ${errMsg}`)
      throw new Error(`POST ${path}: ${res.status} - ${errMsg}`)
    }
    emitLog('debug', 'api', `POST ${path} -> ${res.status}`)
    return await res.json()
  } catch (err) {
    if (!(err instanceof Error && err.message.startsWith('POST '))) {
      emitLog('error', 'api', `POST ${path}: ${err instanceof Error ? err.message : String(err)}`)
    }
    throw err
  }
}

export async function apiDelete(path: string): Promise<void> {
  const url = `${BACKEND_URL}${path}`
  try {
    const res = await fetch(url, { method: 'DELETE', headers: { 'Accept': 'application/json' } })
    if (!res.ok) {
      const errMsg = await parseError(res)
      emitLog('error', 'api', `DELETE ${path} failed: ${res.status} - ${errMsg}`)
      throw new Error(`DELETE ${path}: ${res.status} - ${errMsg}`)
    }
    emitLog('debug', 'api', `DELETE ${path} -> ${res.status}`)
  } catch (err) {
    if (!(err instanceof Error && err.message.startsWith('DELETE '))) {
      emitLog('error', 'api', `DELETE ${path}: ${err instanceof Error ? err.message : String(err)}`)
    }
    throw err
  }
}
