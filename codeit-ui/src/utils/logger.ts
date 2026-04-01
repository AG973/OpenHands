export interface LogEntry {
  id: number
  timestamp: string
  level: 'info' | 'warn' | 'error' | 'debug' | 'event'
  source: string
  message: string
  detail?: string
}

// Global log buffer (persists even when LogsPanel unmounted)
export const logBuffer: LogEntry[] = []
export const logListeners: Array<(entry: LogEntry) => void> = []

export function emitLog(level: LogEntry['level'], source: string, message: string, detail?: string) {
  const entry: LogEntry = { id: Date.now() + Math.random(), timestamp: new Date().toISOString(), level, source, message, detail }
  logBuffer.push(entry)
  if (logBuffer.length > 2000) logBuffer.splice(0, logBuffer.length - 2000)
  logListeners.forEach(fn => fn(entry))
}
