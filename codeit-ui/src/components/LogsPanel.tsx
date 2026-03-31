import { useState, useEffect, useRef } from 'react'
import {
  ScrollText, Search, Play, Pause, Download, Trash,
  Info, AlertTriangle, XCircle, Circle, Activity,
} from 'lucide-react'
import { logBuffer, logListeners, emitLog, type LogEntry } from '../utils/logger'
import { BACKEND_URL } from '../utils/api'

export function LogsPanel() {
  const [logs, setLogs] = useState<LogEntry[]>([...logBuffer])
  const [filter, setFilter] = useState<'all' | LogEntry['level']>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [paused, setPaused] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (entry: LogEntry) => { if (!paused) setLogs(prev => [...prev, entry]) }
    logListeners.push(handler)
    // Backend health check
    const healthTimer = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/codeit/health`)
        if (res.ok) {
          const data = await res.json()
          emitLog('event', 'health', `Backend OK (${data.active_users || 0} users, ${data.total_conversations || 0} convs)`)
        } else {
          emitLog('warn', 'health', `Backend returned ${res.status}`)
        }
      } catch {
        emitLog('error', 'health', 'Backend unreachable')
      }
    }, 10000)
    return () => {
      const idx = logListeners.indexOf(handler)
      if (idx >= 0) logListeners.splice(idx, 1)
      clearInterval(healthTimer)
    }
  }, [paused])

  useEffect(() => {
    if (!paused && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [logs, paused])

  const filtered = logs.filter(l => {
    if (filter !== 'all' && l.level !== filter) return false
    if (searchTerm && !l.message.toLowerCase().includes(searchTerm.toLowerCase()) && !l.source.toLowerCase().includes(searchTerm.toLowerCase())) return false
    return true
  })

  const levelIcon: Record<string, React.ReactNode> = {
    info: <Info className="w-3.5 h-3.5 text-blue-400" />, warn: <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />,
    error: <XCircle className="w-3.5 h-3.5 text-red-400" />, debug: <Circle className="w-3.5 h-3.5 text-gray-500" />,
    event: <Activity className="w-3.5 h-3.5 text-cyan-400" />,
  }
  const levelBg: Record<string, string> = {
    info: 'border-l-blue-500/50', warn: 'border-l-amber-500/50', error: 'border-l-red-500/50',
    debug: 'border-l-gray-600/50', event: 'border-l-cyan-500/50',
  }

  function exportLogs() {
    const content = filtered.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] [${l.source}] ${l.message}`).join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `codeit-logs-${Date.now()}.txt`; a.click()
    URL.revokeObjectURL(url)
  }

  function clearLogs() { setLogs([]); logBuffer.length = 0 }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/5">
        <ScrollText className="w-5 h-5 text-cyan-400 flex-shrink-0" />
        <span className="text-sm font-medium text-white">Live Logs</span>
        <div className="flex-1" />
        <div className="flex items-center gap-1 bg-white/5 rounded-lg p-0.5">
          {(['all', 'info', 'warn', 'error', 'event', 'debug'] as const).map(lv => (
            <button key={lv} onClick={() => setFilter(lv)}
              className={`px-2.5 py-1 rounded-md text-xs transition-all ${filter === lv ? 'bg-cyan-800/50 text-cyan-400' : 'text-gray-500 hover:text-gray-300'}`}>
              {lv === 'all' ? 'All' : lv.charAt(0).toUpperCase() + lv.slice(1)}
            </button>
          ))}
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
          <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Filter..."
            className="bg-white/5 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/30 w-40" />
        </div>
        <button onClick={() => setPaused(!paused)} className={`p-1.5 rounded-lg transition-all ${paused ? 'bg-amber-900/30 text-amber-400' : 'text-gray-500 hover:text-white hover:bg-white/5'}`} title={paused ? 'Resume' : 'Pause'}>
          {paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
        </button>
        <button onClick={exportLogs} className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/5 transition-all" title="Export"><Download className="w-4 h-4" /></button>
        <button onClick={clearLogs} className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-white/5 transition-all" title="Clear"><Trash className="w-4 h-4" /></button>
        <span className="text-xs text-gray-600">{filtered.length} entries</span>
      </div>
      <div ref={listRef} className="flex-1 overflow-y-auto font-mono text-xs">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-600">
            <ScrollText className="w-8 h-8 mb-3 opacity-30" />
            <p>No log entries{filter !== 'all' ? ` matching "${filter}"` : ''}</p>
          </div>
        ) : (
          filtered.map(entry => (
            <div key={entry.id} className={`flex items-start gap-2 px-4 py-1.5 border-l-2 hover:bg-white/[0.03] transition-colors ${levelBg[entry.level] || 'border-l-gray-700'}`}>
              <span className="flex-shrink-0 mt-0.5">{levelIcon[entry.level]}</span>
              <span className="text-gray-600 flex-shrink-0 w-20 truncate">{new Date(entry.timestamp).toLocaleTimeString()}</span>
              <span className="text-cyan-600 flex-shrink-0 w-16 truncate">{entry.source}</span>
              <span className="text-gray-300 flex-1 break-all">{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
