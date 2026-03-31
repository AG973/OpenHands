import { useState, useEffect } from 'react'

// Keys that contain secrets and must NOT be persisted to localStorage
const SECRET_KEYS = ['token', 'key', 'secret', 'ssh_key', 'bot_token', 'api_key', 'access_key', 'secret_key']
function isSensitiveKey(k: string): boolean { return SECRET_KEYS.some(s => k.toLowerCase().includes(s.toLowerCase())) }

function sanitizeForStorage<T>(data: T): T {
  if (Array.isArray(data)) return data.map(item => sanitizeForStorage(item)) as T
  if (data && typeof data === 'object' && 'config' in data) {
    const obj = data as Record<string, unknown>
    const config = obj.config as Record<string, string> | undefined
    if (config) {
      const cleaned = Object.fromEntries(Object.entries(config).map(([k, v]) => [k, isSensitiveKey(k) ? '' : v]))
      return { ...obj, config: cleaned, status: obj.status === 'connected' ? 'disconnected' : obj.status } as T
    }
  }
  return data
}

// In-memory cache to preserve full unsanitized state across component unmounts
const memoryCache = new Map<string, unknown>()

export function useLocalStorage<T>(key: string, initialValue: T, stripSecrets = false): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [stored, setStored] = useState<T>(() => {
    if (memoryCache.has(key)) return memoryCache.get(key) as T
    try {
      const item = localStorage.getItem(key)
      return item ? (JSON.parse(item) as T) : initialValue
    } catch { return initialValue }
  })
  useEffect(() => {
    memoryCache.set(key, stored)
    try {
      const toStore = stripSecrets ? sanitizeForStorage(stored) : stored
      localStorage.setItem(key, JSON.stringify(toStore))
    } catch { /* quota exceeded */ }
  }, [key, stored, stripSecrets])
  return [stored, setStored]
}
