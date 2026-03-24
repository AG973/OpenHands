import { useState, useEffect, useRef, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  MessageSquare, Plus, Send, Settings, Trash2, X,
  ChevronDown, ChevronRight, Terminal, FileEdit, Bot,
  User, Loader2, Zap, Menu, Code2, Rocket, Smartphone,
  Globe, Github, Cloud, Cpu, Sparkles, ArrowRight,
  Paperclip, BookOpen, Brain, FileText, Link2,
  Save, Edit3, Play, Trash, Search, RefreshCw,
  Server, MessageCircle, Box, Plug, ToggleLeft, ToggleRight,
  ScrollText, AlertTriangle, Info, XCircle, Pause,
  Download, Circle, Activity
} from 'lucide-react'
import './App.css'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || ''

interface ChatMessage { id: number; role: 'user' | 'assistant' | 'system'; content: string; timestamp: string }
interface AgentAction { id: number; type: 'command' | 'file_write' | 'file_edit' | 'browse' | 'think' | 'task' | 'other'; title: string; detail: string; status: 'running' | 'done' | 'error' }
interface ConversationMeta { conversation_id: string; title: string; created_at: string; status: string }
interface SkillItem { id: string; name: string; description: string; content: string; enabled: boolean }
interface KnowledgeItem { id: string; title: string; content: string; tags: string[]; updated_at: string }
interface PromptItem { id: string; name: string; content: string; active: boolean }
interface ConnectorItem { id: string; name: string; type: string; icon: string; status: 'connected' | 'disconnected' | 'error'; config: Record<string, string> }
interface LogEntry { id: number; timestamp: string; level: 'info' | 'warn' | 'error' | 'debug' | 'event'; source: string; message: string; detail?: string }

type SidebarView = 'chat' | 'skills' | 'knowledge' | 'prompts' | 'connectors' | 'deploy' | 'logs'

/* ── Global log store ── */
const logBuffer: LogEntry[] = []
const logListeners: Array<(entry: LogEntry) => void> = []
function emitLog(level: LogEntry['level'], source: string, message: string, detail?: string) {
  const entry: LogEntry = { id: Date.now() + Math.random(), timestamp: new Date().toISOString(), level, source, message, detail }
  logBuffer.push(entry)
  if (logBuffer.length > 1000) logBuffer.splice(0, logBuffer.length - 1000)
  logListeners.forEach(fn => fn(entry))
}

async function apiGet<T>(path: string): Promise<T> {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`)
    if (!res.ok) { emitLog('error', 'api', `GET ${path} failed: HTTP ${res.status}`); throw new Error(`API ${path}: ${res.status}`) }
    emitLog('debug', 'api', `GET ${path} → ${res.status}`)
    return res.json()
  } catch (err) { if (!(err instanceof Error && err.message.startsWith('API '))) emitLog('error', 'api', `GET ${path}: ${err instanceof Error ? err.message : String(err)}`); throw err }
}
async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
    if (!res.ok) { emitLog('error', 'api', `POST ${path} failed: HTTP ${res.status}`); throw new Error(`API ${path}: ${res.status}`) }
    emitLog('debug', 'api', `POST ${path} → ${res.status}`)
    return res.json()
  } catch (err) { if (!(err instanceof Error && err.message.startsWith('API '))) emitLog('error', 'api', `POST ${path}: ${err instanceof Error ? err.message : String(err)}`); throw err }
}
async function apiDelete(path: string): Promise<void> {
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, { method: 'DELETE' })
    if (!res.ok) { emitLog('error', 'api', `DELETE ${path} failed: HTTP ${res.status}`); throw new Error(`API ${path}: ${res.status}`) }
    emitLog('debug', 'api', `DELETE ${path} → ${res.status}`)
  } catch (err) { if (!(err instanceof Error && err.message.startsWith('API '))) emitLog('error', 'api', `DELETE ${path}: ${err instanceof Error ? err.message : String(err)}`); throw err }
}

function parseEvent(evt: Record<string, unknown>): { message?: ChatMessage; action?: AgentAction } {
  const id = Number(evt.id) || Date.now()
  const source = evt.source as string
  const timestamp = (evt.timestamp as string) || new Date().toISOString()
  if (source === 'user' && (evt.type === 'message' || evt.action === 'message')) {
    const args = evt.args as Record<string, string> | undefined
    return { message: { id, role: 'user', content: args?.content || evt.message as string || '', timestamp } }
  }
  if (source === 'agent' && (evt.type === 'message' || evt.action === 'message')) {
    const args = evt.args as Record<string, string> | undefined
    return { message: { id, role: 'assistant', content: args?.content || evt.message as string || '', timestamp } }
  }
  if (evt.action === 'run') {
    const args = evt.args as Record<string, string> | undefined
    return { action: { id, type: 'command', title: 'Run command', detail: args?.command || '', status: 'running' } }
  }
  if (evt.observation === 'run') {
    const content = evt.content as string || ''
    return { action: { id, type: 'command', title: 'Command output', detail: content.slice(0, 500), status: (evt.extras as Record<string, number>)?.exit_code === 0 ? 'done' : 'error' } }
  }
  if (evt.action === 'write') {
    const args = evt.args as Record<string, string> | undefined
    return { action: { id, type: 'file_write', title: `Create ${args?.path?.split('/').pop() || 'file'}`, detail: args?.path || '', status: 'running' } }
  }
  if (evt.action === 'edit') {
    const args = evt.args as Record<string, string> | undefined
    return { action: { id, type: 'file_edit', title: `Edit ${args?.path?.split('/').pop() || 'file'}`, detail: args?.path || '', status: 'running' } }
  }
  if (evt.observation === 'agent_state_changed') {
    const extras = evt.extras as Record<string, string> | undefined
    if (extras?.agent_state === 'error') return { message: { id, role: 'system', content: `Agent error: ${extras?.reason || 'Unknown'}`, timestamp } }
  }
  if (evt.type === 'status') return { action: { id, type: 'task', title: 'Status', detail: evt.message as string || '', status: 'done' } }
  return {}
}

/* ── 3D Background ── */
function OrbsBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="orb-1 absolute top-1/4 left-1/3 w-96 h-96 rounded-full opacity-20" style={{ background: 'radial-gradient(circle, #1e3a5f 0%, transparent 70%)' }} />
      <div className="orb-2 absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full opacity-15" style={{ background: 'radial-gradient(circle, #2d8cf0 0%, transparent 70%)' }} />
      <div className="orb-3 absolute top-1/2 right-1/3 w-64 h-64 rounded-full opacity-10" style={{ background: 'radial-gradient(circle, #4fc3f7 0%, transparent 70%)' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="ring-spin w-96 h-96 rounded-full border border-white/5" />
      </div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="ring-spin-reverse w-72 h-72 rounded-full border border-cyan-500/10" />
      </div>
      <div className="pulse-glow absolute top-1/3 left-1/2 -translate-x-1/2 w-64 h-64 rounded-full" style={{ background: 'radial-gradient(circle, rgba(30,58,95,0.6) 0%, transparent 60%)' }} />
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3 animate-msg">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-700 to-blue-900 flex items-center justify-center mr-2">
        <Bot className="w-4 h-4 text-cyan-300" />
      </div>
      <div className="bg-white/5 rounded-2xl px-4 py-3 flex items-center gap-1.5">
        <span className="typing-dot w-2 h-2 rounded-full bg-cyan-400 inline-block" />
        <span className="typing-dot w-2 h-2 rounded-full bg-cyan-400 inline-block" />
        <span className="typing-dot w-2 h-2 rounded-full bg-cyan-400 inline-block" />
      </div>
    </div>
  )
}

function ActionCard({ action }: { action: AgentAction }) {
  const [expanded, setExpanded] = useState(false)
  const icons: Record<string, React.ReactNode> = {
    command: <Terminal className="w-4 h-4" />, file_write: <FileEdit className="w-4 h-4" />,
    file_edit: <FileEdit className="w-4 h-4" />, task: <Zap className="w-4 h-4" />, other: <Bot className="w-4 h-4" />,
  }
  const statusColors: Record<string, string> = { running: 'text-amber-400', done: 'text-emerald-400', error: 'text-red-400' }
  return (
    <div className="animate-slide-in my-1 mx-4 max-w-4xl">
      <button onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-white/3 hover:bg-white/5 border border-white/5 transition-all text-sm text-gray-400">
        <span className={statusColors[action.status]}>
          {action.status === 'running' ? <Loader2 className="w-4 h-4 animate-spin" /> : icons[action.type] || icons.other}
        </span>
        <span className="flex-1 text-left truncate">{action.title}</span>
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      {expanded && action.detail && (
        <pre className="mt-1 mx-1 p-3 rounded-lg bg-black/40 border border-white/5 text-xs text-gray-500 overflow-x-auto max-h-48 overflow-y-auto font-mono">{action.detail}</pre>
      )}
    </div>
  )
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === 'system') {
    return (
      <div className="flex justify-center my-3">
        <div className="text-xs text-gray-500 bg-white/5 backdrop-blur-sm px-4 py-1.5 rounded-full border border-white/5">{msg.content}</div>
      </div>
    )
  }
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} my-3 mx-4 animate-msg`}>
      {!isUser && (
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-700 to-blue-900 flex items-center justify-center mr-3 mt-1 flex-shrink-0 shadow-lg shadow-cyan-900/20">
          <img src="/codeit-logo.png" alt="CODEIT" className="w-6 h-6 object-contain" />
        </div>
      )}
      <div className={`max-w-2xl rounded-2xl px-4 py-3 ${isUser
        ? 'bg-gradient-to-r from-cyan-800/60 to-blue-800/60 backdrop-blur-sm border border-cyan-500/20 text-white'
        : 'bg-white/5 backdrop-blur-sm border border-white/5 text-gray-200'}`}>
        <div className="markdown-body text-sm leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
        </div>
      </div>
      {isUser && (
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center ml-3 mt-1 flex-shrink-0">
          <User className="w-4 h-4 text-slate-300" />
        </div>
      )}
    </div>
  )
}

function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!open) return
    apiGet<Record<string, string>>('/api/settings').then(s => {
      setModel(s.llm_model || '')
      setBaseUrl(s.llm_base_url || '')
      setApiKey(s.llm_api_key || '')
    }).catch(() => {})
  }, [open])

  async function save() {
    setSaving(true)
    try {
      await apiPost('/api/settings', { llm_model: model, llm_base_url: baseUrl, llm_api_key: apiKey })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally { setSaving(false) }
  }

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md" onClick={onClose}>
      <div className="animate-scale-in bg-gray-900/95 border border-white/10 rounded-2xl p-6 w-full max-w-md shadow-2xl shadow-black/50" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-cyan-400" /> Settings
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors"><X className="w-5 h-5" /></button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">Model</label>
            <input value={model} onChange={e => setModel(e.target.value)} placeholder="openai/glm-4.7-flash"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 transition-colors" />
          </div>
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">Base URL</label>
            <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder="http://host.docker.internal:11434/v1"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 transition-colors" />
          </div>
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">API Key</label>
            <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="local-llm"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 transition-colors" />
          </div>
        </div>
        <button onClick={save} disabled={saving}
          className="mt-6 w-full bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white font-medium py-2.5 rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : saved ? 'Saved!' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}

function WelcomeHero({ onExampleClick }: { onExampleClick: (text: string) => void }) {
  const capabilities = [
    { icon: <Code2 className="w-5 h-5" />, label: 'Build Apps', desc: 'Web & mobile applications' },
    { icon: <Globe className="w-5 h-5" />, label: 'Deploy', desc: 'Cloud & server deployment' },
    { icon: <Github className="w-5 h-5" />, label: 'GitHub', desc: 'Repos, PRs & code review' },
    { icon: <Smartphone className="w-5 h-5" />, label: 'Mobile', desc: 'iOS & Android apps' },
    { icon: <Cloud className="w-5 h-5" />, label: 'Cloud', desc: 'AWS, RunPod, servers' },
    { icon: <Cpu className="w-5 h-5" />, label: 'AI Models', desc: 'Local Ollama integration' },
  ]
  const examples = [
    { text: 'Build a modern landing page for my startup', icon: <Rocket className="w-4 h-4" /> },
    { text: 'Create a REST API with authentication', icon: <Code2 className="w-4 h-4" /> },
    { text: 'Help me debug this Python script', icon: <Terminal className="w-4 h-4" /> },
    { text: 'Deploy my app to a cloud server', icon: <Cloud className="w-4 h-4" /> },
  ]
  return (
    <div className="relative flex flex-col items-center justify-center h-full px-6 py-12 overflow-y-auto">
      <OrbsBackground />
      <div className="relative z-10 animate-scale-in">
        <div className="relative">
          <img src="/codeit-logo.png" alt="CODEIT" className="w-24 h-24 object-contain mb-2 drop-shadow-2xl" />
          <div className="absolute inset-0 w-24 h-24 rounded-full pulse-glow" style={{ background: 'radial-gradient(circle, rgba(30,58,95,0.8) 0%, transparent 60%)' }} />
        </div>
      </div>
      <h1 className="relative z-10 text-4xl font-bold text-white mt-4 mb-1 tracking-tight animate-scale-in">CODEIT</h1>
      <p className="relative z-10 text-sm text-cyan-400/80 mb-2 tracking-widest uppercase font-medium animate-scale-in">Digital Solutions</p>
      <p className="relative z-10 text-gray-400 text-base mb-10 text-center max-w-lg animate-slide-in">
        Your AI-powered development platform. Describe what you need and I will build it, test it, and deploy it.
      </p>
      <div className="relative z-10 grid grid-cols-2 sm:grid-cols-3 gap-3 max-w-2xl w-full mb-10">
        {capabilities.map((cap, i) => (
          <div key={i} className="card-3d group flex flex-col items-center gap-2 p-4 rounded-2xl bg-white/3 border border-white/5 hover:border-cyan-500/20 hover:bg-white/5 transition-all cursor-default">
            <div className="text-cyan-400 group-hover:text-cyan-300 transition-colors">{cap.icon}</div>
            <span className="text-sm font-medium text-white">{cap.label}</span>
            <span className="text-xs text-gray-500">{cap.desc}</span>
          </div>
        ))}
      </div>
      <div className="relative z-10 w-full max-w-2xl space-y-2">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
          <Sparkles className="w-3 h-3" /> Try asking
        </p>
        {examples.map((ex, i) => (
          <button key={i} onClick={() => onExampleClick(ex.text)}
            className="card-3d w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-white/3 border border-white/5 hover:border-cyan-500/20 hover:bg-white/5 text-sm text-gray-300 hover:text-white transition-all group">
            <span className="text-cyan-500/60 group-hover:text-cyan-400 transition-colors">{ex.icon}</span>
            <span className="flex-1 text-left">{ex.text}</span>
            <ArrowRight className="w-4 h-4 text-gray-600 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
          </button>
        ))}
      </div>
    </div>
  )
}

/* ═══════════════ SKILLS PANEL ═══════════════ */
function SkillsPanel() {
  const [skills, setSkills] = useState<SkillItem[]>([
    { id: '1', name: 'Code Review', description: 'Reviews code for best practices, security, and bugs', content: 'You are an expert code reviewer. Analyze code for security vulnerabilities, performance issues, style violations, and potential bugs. Suggest improvements with code examples.', enabled: true },
    { id: '2', name: 'Debug Assistant', description: 'Identifies and fixes bugs in code', content: 'You are a debugging expert. Help reproduce issues, identify root causes using systematic analysis, and suggest targeted fixes with minimal side effects.', enabled: true },
    { id: '3', name: 'Project Setup', description: 'Sets up new projects with best practices', content: 'You are a project setup specialist. Use modern frameworks, configure linting, testing, CI/CD pipelines, and follow community best practices for project structure.', enabled: false },
    { id: '4', name: 'API Builder', description: 'Designs and builds REST/GraphQL APIs', content: 'You are an API design expert. Follow REST conventions, implement proper authentication, input validation, error handling, and generate API documentation.', enabled: true },
  ])
  const [editing, setEditing] = useState<SkillItem | null>(null)
  const [showForm, setShowForm] = useState(false)

  function toggle(id: string) { setSkills(p => p.map(s => s.id === id ? { ...s, enabled: !s.enabled } : s)) }
  function remove(id: string) { setSkills(p => p.filter(s => s.id !== id)) }
  function saveSkill(s: SkillItem) {
    if (s.id) { setSkills(p => p.map(x => x.id === s.id ? s : x)) } else { setSkills(p => [...p, { ...s, id: String(Date.now()) }]) }
    setShowForm(false); setEditing(null)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div><h2 className="text-lg font-semibold text-white flex items-center gap-2"><BookOpen className="w-5 h-5 text-cyan-400" /> Skills</h2>
          <p className="text-xs text-gray-500 mt-1">Teach the agent specialized capabilities</p></div>
        <button onClick={() => { setEditing({ id: '', name: '', description: '', content: '', enabled: true }); setShowForm(true) }}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gradient-to-r from-cyan-800/60 to-blue-800/60 hover:from-cyan-700/60 hover:to-blue-700/60 border border-cyan-500/20 text-white text-sm transition-all">
          <Plus className="w-4 h-4" /> New Skill</button>
      </div>
      {showForm && editing ? (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-4">
            <input value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })} placeholder="Skill name"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
            <input value={editing.description} onChange={e => setEditing({ ...editing, description: e.target.value })} placeholder="Short description"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
            <textarea value={editing.content} onChange={e => setEditing({ ...editing, content: e.target.value })} placeholder="Skill instructions (markdown supported)..." rows={12}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 resize-none font-mono" />
            <div className="flex gap-3">
              <button onClick={() => saveSkill(editing)} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white text-sm transition-all"><Save className="w-4 h-4" /> Save Skill</button>
              <button onClick={() => { setShowForm(false); setEditing(null) }} className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white text-sm transition-all">Cancel</button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-2xl mx-auto space-y-3">
            {skills.map(sk => (
              <div key={sk.id} className="card-3d bg-white/3 border border-white/5 rounded-2xl p-4 hover:border-cyan-500/20 transition-all">
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${sk.enabled ? 'bg-cyan-900/50 text-cyan-400' : 'bg-gray-800/50 text-gray-600'}`}><BookOpen className="w-5 h-5" /></div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2"><h3 className="text-sm font-medium text-white">{sk.name}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${sk.enabled ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-800/50 text-gray-500'}`}>{sk.enabled ? 'Active' : 'Inactive'}</span></div>
                    <p className="text-xs text-gray-500 mt-1">{sk.description}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => toggle(sk.id)} className="p-1.5 rounded-lg transition-all hover:bg-white/5" title={sk.enabled ? 'Disable' : 'Enable'}>{sk.enabled ? <ToggleRight className="w-5 h-5 text-cyan-400" /> : <ToggleLeft className="w-5 h-5 text-gray-600" />}</button>
                    <button onClick={() => { setEditing(sk); setShowForm(true) }} className="p-1.5 rounded-lg text-gray-500 hover:text-cyan-400 hover:bg-white/5 transition-all"><Edit3 className="w-3.5 h-3.5" /></button>
                    <button onClick={() => remove(sk.id)} className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-white/5 transition-all"><Trash className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ═══════════════ KNOWLEDGE PANEL ═══════════════ */
function KnowledgePanel() {
  const [items, setItems] = useState<KnowledgeItem[]>([
    { id: '1', title: 'Project Architecture', content: 'Frontend: React + Vite + Tailwind CSS. Backend: Python FastAPI with OpenHands agent framework. LLM: Local Ollama with GLM-4.7-flash. Deployment: Docker containers with Nginx reverse proxy.', tags: ['architecture', 'system'], updated_at: '2024-03-20' },
    { id: '2', title: 'Deployment Guide', content: '1. Build frontend with npm run build\n2. Deploy via Docker compose\n3. Configure Ollama endpoint\n4. Set environment variables\n5. Run docker-compose up -d', tags: ['deployment', 'ops'], updated_at: '2024-03-19' },
    { id: '3', title: 'Coding Standards', content: 'TypeScript strict mode enabled. ESLint + Prettier for formatting. Conventional commits required. PR reviews mandatory. Unit tests for all new features. Integration tests for API endpoints.', tags: ['standards', 'quality'], updated_at: '2024-03-18' },
  ])
  const [editing, setEditing] = useState<KnowledgeItem | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [query, setQuery] = useState('')

  const filtered = items.filter(i => i.title.toLowerCase().includes(query.toLowerCase()) || i.tags.some(t => t.toLowerCase().includes(query.toLowerCase())) || i.content.toLowerCase().includes(query.toLowerCase()))

  function saveItem(item: KnowledgeItem) {
    const now = new Date().toISOString().split('T')[0]
    if (item.id) { setItems(p => p.map(i => i.id === item.id ? { ...item, updated_at: now } : i)) } else { setItems(p => [...p, { ...item, id: String(Date.now()), updated_at: now }]) }
    setShowForm(false); setEditing(null)
  }
  function remove(id: string) { setItems(p => p.filter(i => i.id !== id)) }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div><h2 className="text-lg font-semibold text-white flex items-center gap-2"><Brain className="w-5 h-5 text-cyan-400" /> Knowledge Base</h2>
          <p className="text-xs text-gray-500 mt-1">Persistent memory the agent can reference</p></div>
        <button onClick={() => { setEditing({ id: '', title: '', content: '', tags: [], updated_at: '' }); setShowForm(true) }}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gradient-to-r from-cyan-800/60 to-blue-800/60 hover:from-cyan-700/60 hover:to-blue-700/60 border border-cyan-500/20 text-white text-sm transition-all">
          <Plus className="w-4 h-4" /> Add Knowledge</button>
      </div>
      {showForm && editing ? (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-4">
            <input value={editing.title} onChange={e => setEditing({ ...editing, title: e.target.value })} placeholder="Title"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
            <textarea value={editing.content} onChange={e => setEditing({ ...editing, content: e.target.value })} placeholder="Knowledge content (markdown supported)..." rows={10}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 resize-none font-mono" />
            <input value={editing.tags.join(', ')} onChange={e => setEditing({ ...editing, tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })} placeholder="Tags (comma separated)"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
            <div className="flex gap-3">
              <button onClick={() => saveItem(editing)} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white text-sm transition-all"><Save className="w-4 h-4" /> Save</button>
              <button onClick={() => { setShowForm(false); setEditing(null) }} className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white text-sm transition-all">Cancel</button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-2xl mx-auto">
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search knowledge by title, tags, or content..."
                className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
            </div>
            <div className="space-y-3">
              {filtered.map(item => (
                <div key={item.id} className="card-3d bg-white/3 border border-white/5 rounded-2xl p-4 hover:border-cyan-500/20 transition-all">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-white">{item.title}</h3>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{item.content}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        {item.tags.map(tag => (<span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-cyan-900/30 text-cyan-400">{tag}</span>))}
                        <span className="text-xs text-gray-600 ml-auto">{item.updated_at}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 ml-3">
                      <button onClick={() => { setEditing(item); setShowForm(true) }} className="p-1.5 rounded-lg text-gray-500 hover:text-cyan-400 hover:bg-white/5 transition-all"><Edit3 className="w-3.5 h-3.5" /></button>
                      <button onClick={() => remove(item.id)} className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-white/5 transition-all"><Trash className="w-3.5 h-3.5" /></button>
                    </div>
                  </div>
                </div>
              ))}
              {filtered.length === 0 && <p className="text-center text-gray-600 text-sm py-8">No knowledge items found</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ═══════════════ PROMPTS PANEL ═══════════════ */
function PromptsPanel() {
  const [prompts, setPrompts] = useState<PromptItem[]>([
    { id: '1', name: 'Default System Prompt', content: 'You are a helpful AI coding assistant powered by CODEIT. You can write code, create files, run commands, build applications, and deploy them to servers. Always explain your approach before acting.', active: true },
    { id: '2', name: 'Strict Code Quality', content: 'Follow strict coding standards: TypeScript strict mode, comprehensive error handling, unit tests for all functions, meaningful variable names, JSDoc comments, and SOLID principles.', active: false },
    { id: '3', name: 'Non-Developer Friendly', content: 'You are helping a non-technical user. Use simple language, avoid jargon, explain every concept in plain terms. Provide step-by-step instructions that anyone can follow without technical knowledge.', active: false },
  ])
  const [editing, setEditing] = useState<PromptItem | null>(null)
  const [showForm, setShowForm] = useState(false)

  function setActive(id: string) { setPrompts(p => p.map(x => ({ ...x, active: x.id === id }))) }
  function savePrompt(prompt: PromptItem) {
    if (prompt.id) { setPrompts(p => p.map(x => x.id === prompt.id ? prompt : x)) } else { setPrompts(p => [...p, { ...prompt, id: String(Date.now()) }]) }
    setShowForm(false); setEditing(null)
  }
  function remove(id: string) { setPrompts(p => p.filter(x => x.id !== id)) }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div><h2 className="text-lg font-semibold text-white flex items-center gap-2"><FileText className="w-5 h-5 text-cyan-400" /> Prompts</h2>
          <p className="text-xs text-gray-500 mt-1">Custom system prompts to guide agent behavior</p></div>
        <button onClick={() => { setEditing({ id: '', name: '', content: '', active: false }); setShowForm(true) }}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gradient-to-r from-cyan-800/60 to-blue-800/60 hover:from-cyan-700/60 hover:to-blue-700/60 border border-cyan-500/20 text-white text-sm transition-all">
          <Plus className="w-4 h-4" /> New Prompt</button>
      </div>
      {showForm && editing ? (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-4">
            <input value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })} placeholder="Prompt name"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
            <textarea value={editing.content} onChange={e => setEditing({ ...editing, content: e.target.value })} placeholder="System prompt content..." rows={12}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 resize-none font-mono" />
            <div className="flex gap-3">
              <button onClick={() => savePrompt(editing)} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white text-sm transition-all"><Save className="w-4 h-4" /> Save Prompt</button>
              <button onClick={() => { setShowForm(false); setEditing(null) }} className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white text-sm transition-all">Cancel</button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-2xl mx-auto space-y-3">
            {prompts.map(pr => (
              <div key={pr.id} className={`card-3d bg-white/3 border rounded-2xl p-4 transition-all ${pr.active ? 'border-cyan-500/30 bg-cyan-900/10' : 'border-white/5 hover:border-cyan-500/20'}`}>
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${pr.active ? 'bg-cyan-900/50 text-cyan-400' : 'bg-gray-800/50 text-gray-600'}`}><FileText className="w-5 h-5" /></div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2"><h3 className="text-sm font-medium text-white">{pr.name}</h3>
                      {pr.active && <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-900/50 text-cyan-400">Active</span>}</div>
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">{pr.content}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    {!pr.active && <button onClick={() => setActive(pr.id)} className="p-1.5 rounded-lg text-gray-600 hover:text-cyan-400 hover:bg-white/5 transition-all" title="Set as active"><Play className="w-3.5 h-3.5" /></button>}
                    <button onClick={() => { setEditing(pr); setShowForm(true) }} className="p-1.5 rounded-lg text-gray-500 hover:text-cyan-400 hover:bg-white/5 transition-all"><Edit3 className="w-3.5 h-3.5" /></button>
                    <button onClick={() => remove(pr.id)} className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-white/5 transition-all"><Trash className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ═══════════════ CONNECTORS PANEL ═══════════════ */
function ConnectorsPanel() {
  const [connectors, setConnectors] = useState<ConnectorItem[]>([
    { id: '1', name: 'GitHub', type: 'github', icon: 'github', status: 'disconnected', config: { token: '', org: '', default_branch: 'main' } },
    { id: '2', name: 'Discord', type: 'discord', icon: 'discord', status: 'disconnected', config: { bot_token: '', server_id: '', channel_id: '' } },
    { id: '3', name: 'AWS', type: 'aws', icon: 'aws', status: 'disconnected', config: { access_key: '', secret_key: '', region: 'us-east-1' } },
    { id: '4', name: 'RunPod', type: 'runpod', icon: 'runpod', status: 'disconnected', config: { api_key: '', gpu_type: 'RTX 4090' } },
    { id: '5', name: 'Custom Server', type: 'server', icon: 'server', status: 'disconnected', config: { host: '', port: '22', username: '', ssh_key: '' } },
  ])
  const [editing, setEditing] = useState<ConnectorItem | null>(null)

  const iconMap: Record<string, React.ReactNode> = {
    github: <Github className="w-5 h-5" />, discord: <MessageCircle className="w-5 h-5" />,
    aws: <Cloud className="w-5 h-5" />, runpod: <Cpu className="w-5 h-5" />, server: <Server className="w-5 h-5" />,
  }
  const descMap: Record<string, string> = {
    github: 'Repositories, PRs, Issues, Code Review', discord: 'Bot messaging, notifications, commands',
    aws: 'EC2, S3, Lambda, ECS deployment', runpod: 'GPU cloud computing for ML workloads', server: 'SSH access to remote servers',
  }
  const statusColors: Record<string, string> = { connected: 'bg-emerald-400', disconnected: 'bg-gray-600', error: 'bg-red-400' }

  function saveConnector(c: ConnectorItem) { setConnectors(p => p.map(x => x.id === c.id ? { ...c, status: 'connected' } : x)); setEditing(null) }
  function disconnect(id: string) { setConnectors(p => p.map(c => c.id === id ? { ...c, status: 'disconnected', config: Object.fromEntries(Object.keys(c.config).map(k => [k, ''])) } : c)) }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div><h2 className="text-lg font-semibold text-white flex items-center gap-2"><Plug className="w-5 h-5 text-cyan-400" /> Connectors</h2>
          <p className="text-xs text-gray-500 mt-1">Connect to external platforms and services</p></div>
      </div>
      {editing ? (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-12 h-12 rounded-xl bg-cyan-900/50 text-cyan-400 flex items-center justify-center">{iconMap[editing.icon]}</div>
              <div><h3 className="text-white font-medium">{editing.name}</h3><p className="text-xs text-gray-500">Configure connection settings</p></div>
            </div>
            {Object.entries(editing.config).map(([key, value]) => (
              <div key={key}>
                <label className="text-sm text-gray-400 mb-1.5 block capitalize">{key.replace(/_/g, ' ')}</label>
                <input type={key.includes('key') || key.includes('token') || key.includes('secret') ? 'password' : 'text'} value={value}
                  onChange={e => setEditing({ ...editing, config: { ...editing.config, [key]: e.target.value } })}
                  placeholder={`Enter ${key.replace(/_/g, ' ')}`}
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
              </div>
            ))}
            <div className="flex gap-3 pt-2">
              <button onClick={() => saveConnector(editing)} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white text-sm transition-all"><Link2 className="w-4 h-4" /> Connect</button>
              <button onClick={() => setEditing(null)} className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white text-sm transition-all">Cancel</button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-2xl mx-auto space-y-3">
            {connectors.map(c => (
              <div key={c.id} className="card-3d bg-white/3 border border-white/5 rounded-2xl p-4 hover:border-cyan-500/20 transition-all">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${c.status === 'connected' ? 'bg-cyan-900/50 text-cyan-400' : 'bg-gray-800/50 text-gray-500'}`}>{iconMap[c.icon] || <Plug className="w-5 h-5" />}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2"><h3 className="text-sm font-medium text-white">{c.name}</h3>
                      <div className={`w-2 h-2 rounded-full ${statusColors[c.status]}`} /><span className="text-xs text-gray-500 capitalize">{c.status}</span></div>
                    <p className="text-xs text-gray-600 mt-0.5">{descMap[c.type] || 'External service'}</p>
                  </div>
                  {c.status === 'connected' ? (
                    <button onClick={() => disconnect(c.id)} className="px-3 py-1.5 rounded-lg text-xs text-red-400 border border-red-500/20 hover:bg-red-900/20 transition-all">Disconnect</button>
                  ) : (
                    <button onClick={() => setEditing(c)} className="px-3 py-1.5 rounded-lg text-xs text-cyan-400 border border-cyan-500/20 hover:bg-cyan-900/20 transition-all">Configure</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ═══════════════ DEPLOY PANEL ═══════════════ */
/* ═══════════════ LOGS / ACTIVITY MONITOR PANEL ═══════════════ */
function LogsPanel() {
  const [logs, setLogs] = useState<LogEntry[]>(() => [...logBuffer])
  const [autoScroll, setAutoScroll] = useState(true)
  const [paused, setPaused] = useState(false)
  const [filterLevel, setFilterLevel] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const pausedRef = useRef(false)
  pausedRef.current = paused

  useEffect(() => {
    const handler = (entry: LogEntry) => {
      if (!pausedRef.current) setLogs(prev => [...prev.slice(-999), entry])
    }
    logListeners.push(handler)
    return () => { const idx = logListeners.indexOf(handler); if (idx >= 0) logListeners.splice(idx, 1) }
  }, [])

  useEffect(() => {
    if (autoScroll && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [logs, autoScroll])

  // Poll backend health every 10s
  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch(`${BACKEND_URL}/api/conversations?limit=1`)
        if (res.ok) emitLog('info', 'health', `Backend healthy (HTTP ${res.status})`)
        else emitLog('warn', 'health', `Backend returned HTTP ${res.status}`)
      } catch (err) {
        emitLog('error', 'health', `Backend unreachable: ${err instanceof Error ? err.message : String(err)}`)
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  const filtered = logs.filter(l => {
    if (filterLevel !== 'all' && l.level !== filterLevel) return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      return l.message.toLowerCase().includes(q) || l.source.toLowerCase().includes(q) || (l.detail?.toLowerCase().includes(q) ?? false)
    }
    return true
  })

  const levelIcon = (level: string) => {
    switch (level) {
      case 'error': return <XCircle className="w-3.5 h-3.5 text-red-400" />
      case 'warn': return <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
      case 'event': return <Activity className="w-3.5 h-3.5 text-cyan-400" />
      case 'debug': return <Circle className="w-3.5 h-3.5 text-gray-500" />
      default: return <Info className="w-3.5 h-3.5 text-emerald-400" />
    }
  }
  const levelBg = (level: string) => {
    switch (level) {
      case 'error': return 'border-red-500/20 bg-red-950/20'
      case 'warn': return 'border-amber-500/20 bg-amber-950/20'
      case 'event': return 'border-cyan-500/10 bg-cyan-950/10'
      default: return 'border-white/5 bg-white/5'
    }
  }

  const errorCount = logs.filter(l => l.level === 'error').length
  const warnCount = logs.filter(l => l.level === 'warn').length

  function exportLogs() {
    const text = filtered.map(l => `[${l.timestamp}] [${l.level.toUpperCase()}] [${l.source}] ${l.message}${l.detail ? '\n  ' + l.detail : ''}`).join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `codeit-logs-${new Date().toISOString().slice(0, 19)}.txt`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <ScrollText className="w-5 h-5 text-cyan-400" /> Live Activity Monitor
          </h2>
          <p className="text-xs text-gray-500 mt-1">Real-time system logs, events, and error tracking</p>
        </div>
        <div className="flex items-center gap-2">
          {errorCount > 0 && <span className="text-xs px-2 py-1 rounded-full bg-red-900/40 text-red-400 border border-red-500/20">{errorCount} errors</span>}
          {warnCount > 0 && <span className="text-xs px-2 py-1 rounded-full bg-amber-900/40 text-amber-400 border border-amber-500/20">{warnCount} warnings</span>}
          <span className="text-xs px-2 py-1 rounded-full bg-white/5 text-gray-400">{logs.length} entries</span>
        </div>
      </div>
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-white/5 bg-black/10">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
          <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Filter logs..."
            className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
        </div>
        <select value={filterLevel} onChange={e => setFilterLevel(e.target.value)}
          className="bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-cyan-500/50 appearance-none cursor-pointer">
          <option value="all">All Levels</option>
          <option value="error">Errors</option>
          <option value="warn">Warnings</option>
          <option value="info">Info</option>
          <option value="event">Events</option>
          <option value="debug">Debug</option>
        </select>
        <button onClick={() => setPaused(!paused)} title={paused ? 'Resume' : 'Pause'}
          className={`p-1.5 rounded-lg transition-all ${paused ? 'bg-amber-900/40 text-amber-400 border border-amber-500/20' : 'text-gray-500 hover:text-white hover:bg-white/5'}`}>
          {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
        </button>
        <button onClick={() => setAutoScroll(!autoScroll)} title={autoScroll ? 'Auto-scroll on' : 'Auto-scroll off'}
          className={`p-1.5 rounded-lg transition-all ${autoScroll ? 'text-cyan-400 bg-cyan-900/20' : 'text-gray-500 hover:text-white hover:bg-white/5'}`}>
          <ChevronDown className="w-3.5 h-3.5" />
        </button>
        <button onClick={exportLogs} title="Export logs" className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/5 transition-all">
          <Download className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => setLogs([])} title="Clear logs" className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-white/5 transition-all">
          <Trash className="w-3.5 h-3.5" />
        </button>
      </div>
      {/* Log entries */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto font-mono text-xs">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-600">
            <ScrollText className="w-10 h-10 mb-3 text-gray-700" />
            <p className="text-sm">No log entries{filterLevel !== 'all' || searchQuery ? ' matching filter' : ' yet'}</p>
            <p className="text-xs mt-1 text-gray-700">Activity will appear here in real-time</p>
          </div>
        ) : (
          <div className="divide-y divide-white/3">
            {filtered.map(entry => (
              <div key={entry.id}
                onClick={() => entry.detail ? setExpandedId(expandedId === entry.id ? null : entry.id) : undefined}
                className={`px-4 py-2 ${levelBg(entry.level)} ${entry.detail ? 'cursor-pointer' : ''} hover:bg-white/3 transition-colors`}>
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 flex-shrink-0">{levelIcon(entry.level)}</span>
                  <span className="text-gray-600 flex-shrink-0 w-20 truncate">{entry.timestamp.split('T')[1]?.slice(0, 12) || entry.timestamp}</span>
                  <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-xs ${entry.source === 'error' ? 'bg-red-900/30 text-red-400' : entry.source === 'websocket' ? 'bg-cyan-900/30 text-cyan-400' : entry.source === 'health' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-white/5 text-gray-400'}`}>{entry.source}</span>
                  <span className="text-gray-300 flex-1 break-all">{entry.message}</span>
                  {entry.detail && <ChevronRight className={`w-3 h-3 text-gray-600 flex-shrink-0 mt-0.5 transition-transform ${expandedId === entry.id ? 'rotate-90' : ''}`} />}
                </div>
                {expandedId === entry.id && entry.detail && (
                  <pre className="mt-2 ml-6 p-2 rounded-lg bg-black/40 border border-white/5 text-gray-500 overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap">{entry.detail}</pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-1.5 border-t border-white/5 bg-black/20 text-xs text-gray-600">
        <div className="flex items-center gap-3">
          {paused ? <span className="flex items-center gap-1 text-amber-400"><Pause className="w-3 h-3" /> Paused</span>
            : <span className="flex items-center gap-1 text-emerald-400"><Activity className="w-3 h-3" /> Live</span>}
          <span>{filtered.length} / {logs.length} entries</span>
        </div>
        <span>Max 1000 entries (auto-pruning oldest)</span>
      </div>
    </div>
  )
}

function DeployPanel() {
  const targets = [
    { id: 'local', name: 'Local Server', desc: 'Deploy to your local machine or network', icon: <Server className="w-5 h-5" />, status: 'ready' as const },
    { id: 'docker', name: 'Docker Container', desc: 'Build and run inside Docker container', icon: <Box className="w-5 h-5" />, status: 'ready' as const },
    { id: 'aws', name: 'AWS (EC2 / ECS)', desc: 'Deploy to Amazon Web Services cloud', icon: <Cloud className="w-5 h-5" />, status: 'needs_config' as const },
    { id: 'runpod', name: 'RunPod GPU', desc: 'Deploy to GPU cloud for ML workloads', icon: <Cpu className="w-5 h-5" />, status: 'needs_config' as const },
    { id: 'custom', name: 'Custom Server', desc: 'Deploy via SSH to any remote server', icon: <Globe className="w-5 h-5" />, status: 'needs_config' as const },
  ]
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div><h2 className="text-lg font-semibold text-white flex items-center gap-2"><Rocket className="w-5 h-5 text-cyan-400" /> Deploy</h2>
          <p className="text-xs text-gray-500 mt-1">Deploy your applications to any platform</p></div>
        <button className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white text-sm transition-all"><RefreshCw className="w-4 h-4" /> Refresh</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-2xl mx-auto space-y-3">
          {targets.map(t => (
            <div key={t.id} className="card-3d bg-white/3 border border-white/5 rounded-2xl p-5 hover:border-cyan-500/20 transition-all">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-cyan-900/30 text-cyan-400 flex items-center justify-center flex-shrink-0">{t.icon}</div>
                <div className="flex-1"><h3 className="text-sm font-medium text-white">{t.name}</h3><p className="text-xs text-gray-500 mt-0.5">{t.desc}</p></div>
                {t.status === 'ready' ? (
                  <button className="px-4 py-2 rounded-xl text-sm bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white transition-all flex items-center gap-2"><Rocket className="w-3.5 h-3.5" /> Deploy</button>
                ) : (
                  <button className="px-4 py-2 rounded-xl text-sm border border-white/10 text-gray-400 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2"><Settings className="w-3.5 h-3.5" /> Configure</button>
                )}
              </div>
            </div>
          ))}
          <div className="mt-6 p-4 rounded-2xl bg-white/3 border border-white/5">
            <h3 className="text-sm font-medium text-white mb-2 flex items-center gap-2"><Sparkles className="w-4 h-4 text-cyan-400" /> Quick Deploy via Chat</h3>
            <p className="text-xs text-gray-500">You can also deploy by chatting with the agent. Try saying:</p>
            <div className="mt-3 space-y-1.5">
              <p className="text-xs text-cyan-400/70 font-mono bg-white/3 rounded-lg px-3 py-1.5">"Deploy my app to Docker"</p>
              <p className="text-xs text-cyan-400/70 font-mono bg-white/3 rounded-lg px-3 py-1.5">"Deploy to my AWS EC2 instance"</p>
              <p className="text-xs text-cyan-400/70 font-mono bg-white/3 rounded-lg px-3 py-1.5">"Push to my server at 192.168.1.100"</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ═══════════════ MAIN APP ═══════════════ */
function App() {
  const [conversations, setConversations] = useState<ConversationMeta[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [actions, setActions] = useState<AgentAction[]>([])
  const [input, setInput] = useState('')
  const [isAgentRunning, setIsAgentRunning] = useState(false)
  const [wsStatus, setWsStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeView, setActiveView] = useState<SidebarView>('chat')
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([])
  const socketRef = useRef<Socket | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const seenIds = useRef<Set<number>>(new Set())

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, actions])

  const loadConversations = useCallback(async () => {
    try {
      const data = await apiGet<{ results: ConversationMeta[] }>('/api/conversations?limit=50')
      setConversations(data.results || [])
    } catch { /* backend may not be ready */ }
  }, [])
  useEffect(() => { loadConversations() }, [loadConversations])

  const connectToConversation = useCallback((convId: string) => {
    if (socketRef.current) { socketRef.current.disconnect(); socketRef.current = null }
    setMessages([]); setActions([]); seenIds.current = new Set(); setWsStatus('connecting'); setIsAgentRunning(false)
    const baseUrl = BACKEND_URL || window.location.origin
    const sio = io(baseUrl, { transports: ['websocket'], path: '/socket.io', query: { conversation_id: convId, latest_event_id: -1 } })
    sio.on('connect', () => { setWsStatus('connected'); emitLog('info', 'websocket', `Connected to conversation ${convId}`) })
    sio.on('oh_event', (evt: Record<string, unknown>) => {
      const evtId = Number(evt.id)
      if (seenIds.current.has(evtId)) return
      seenIds.current.add(evtId)
      const { message, action } = parseEvent(evt)
      if (message) { setMessages(prev => [...prev, message]); if (message.role === 'assistant') setIsAgentRunning(false) }
      if (action) { setActions(prev => [...prev, action]); if (action.status === 'running') setIsAgentRunning(true) }
      emitLog('event', 'websocket', `${evt.action || evt.observation || evt.type || 'event'} from ${evt.source || '?'}`, JSON.stringify(evt, null, 2))
      const extras = evt.extras as Record<string, string> | undefined
      if (evt.observation === 'agent_state_changed') {
        const state = extras?.agent_state
        if (state === 'awaiting_user_input' || state === 'finished' || state === 'error') setIsAgentRunning(false)
        else if (state === 'running') setIsAgentRunning(true)
      }
    })
    sio.on('disconnect', (reason) => { setWsStatus('disconnected'); emitLog('warn', 'websocket', `Disconnected: ${reason}`) })
    sio.on('connect_error', (err) => { setWsStatus('disconnected'); emitLog('error', 'websocket', `Connection error: ${err.message}`) })
    socketRef.current = sio
  }, [])

  async function createConversation(initialMsg?: string) {
    try {
      if (initialMsg) {
        setMessages([{ id: Date.now(), role: 'user', content: initialMsg, timestamp: new Date().toISOString() }])
        setIsAgentRunning(true)
      }
      const data = await apiPost<ConversationMeta>('/api/conversations', { initial_user_msg: initialMsg })
      const convId = data.conversation_id
      setActiveConvId(convId)
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        try {
          const conv = await apiGet<ConversationMeta>(`/api/conversations/${convId}`)
          if (conv.status === 'RUNNING' || attempts > 30) { clearInterval(poll); connectToConversation(convId); loadConversations() }
        } catch { if (attempts > 30) clearInterval(poll) }
      }, 2000)
    } catch (err) {
      console.error('Failed to create conversation:', err)
      emitLog('error', 'conversation', `Failed to create conversation: ${err instanceof Error ? err.message : String(err)}`)
      setIsAgentRunning(false)
      setMessages(prev => [...prev, { id: Date.now(), role: 'system', content: 'Failed to create conversation. Is the backend running?', timestamp: new Date().toISOString() }])
    }
  }

  async function openConversation(convId: string) {
    setActiveConvId(convId); setActiveView('chat')
    try {
      const conv = await apiGet<ConversationMeta>(`/api/conversations/${convId}`)
      if (conv.status === 'RUNNING') { connectToConversation(convId) }
      else {
        try { await apiPost(`/api/conversations/${convId}/start`) } catch { /* */ }
        let attempts = 0
        const poll = setInterval(async () => {
          attempts++
          try {
            const c = await apiGet<ConversationMeta>(`/api/conversations/${convId}`)
            if (c.status === 'RUNNING' || attempts > 30) { clearInterval(poll); connectToConversation(convId) }
          } catch { if (attempts > 30) clearInterval(poll) }
        }, 2000)
      }
    } catch { connectToConversation(convId) }
  }

  async function deleteConversation(convId: string) {
    await apiDelete(`/api/conversations/${convId}`)
    if (activeConvId === convId) { setActiveConvId(null); setMessages([]); setActions([]); socketRef.current?.disconnect() }
    loadConversations()
  }

  function sendMessage() {
    const text = input.trim()
    if (!text && uploadedFiles.length === 0) return
    if (!activeConvId) { createConversation(text); setInput(''); setUploadedFiles([]); return }
    const fileNote = uploadedFiles.length > 0 ? ('\n\n' + String.fromCodePoint(0x1F4CE) + ' ' + uploadedFiles.map(f => f.name).join(', ')) : ''
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: text + fileNote, timestamp: new Date().toISOString() }])
    setInput(''); setUploadedFiles([])
    if (socketRef.current?.connected) {
      socketRef.current.emit('oh_user_action', { action: 'message', args: { content: text, image_urls: [], file_urls: [], timestamp: new Date().toISOString() } })
      setIsAgentRunning(true)
    } else {
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'system', content: 'Waiting for connection... Your message will be sent when connected.', timestamp: new Date().toISOString() }])
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }
  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) { setInput(e.target.value); const el = e.target; el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 200) + 'px' }
  function handleExampleClick(text: string) { setActiveView('chat'); setInput(text); inputRef.current?.focus() }
  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) { if (e.target.files) { const files = Array.from(e.target.files); setUploadedFiles(prev => [...prev, ...files]) }; e.target.value = '' }
  function removeFile(idx: number) { setUploadedFiles(prev => prev.filter((_, i) => i !== idx)) }

  const showWelcome = !activeConvId && messages.length === 0 && activeView === 'chat'

  const navItems: { view: SidebarView; icon: React.ReactNode; label: string }[] = [
    { view: 'chat', icon: <MessageSquare className="w-4 h-4" />, label: 'Chat' },
    { view: 'skills', icon: <BookOpen className="w-4 h-4" />, label: 'Skills' },
    { view: 'knowledge', icon: <Brain className="w-4 h-4" />, label: 'Knowledge' },
    { view: 'prompts', icon: <FileText className="w-4 h-4" />, label: 'Prompts' },
    { view: 'connectors', icon: <Plug className="w-4 h-4" />, label: 'Connectors' },
    { view: 'deploy', icon: <Rocket className="w-4 h-4" />, label: 'Deploy' },
    { view: 'logs', icon: <ScrollText className="w-4 h-4" />, label: 'Logs' },
  ]

  return (
    <div className="flex h-screen mesh-gradient text-white overflow-hidden">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-72' : 'w-0'} flex-shrink-0 transition-all duration-300 overflow-hidden`}>
        <div className="w-72 h-full flex flex-col bg-black/30 backdrop-blur-xl border-r border-white/5">
          {/* Logo */}
          <div className="px-4 py-4 border-b border-white/5 flex items-center gap-3">
            <img src="/codeit-logo.png" alt="CODEIT" className="w-8 h-8 object-contain" />
            <div><h1 className="text-base font-bold text-white tracking-tight">CODEIT</h1><p className="text-xs text-gray-500 -mt-0.5">Digital Solutions</p></div>
          </div>
          <div className="h-px shimmer-border" />
          {/* Nav tabs */}
          <div className="px-2 py-2 border-b border-white/5">
            <div className="grid grid-cols-3 gap-1">
              {navItems.map(nav => (
                <button key={nav.view} onClick={() => setActiveView(nav.view)}
                  className={`flex flex-col items-center gap-1 px-2 py-2 rounded-xl text-xs transition-all ${activeView === nav.view ? 'bg-cyan-900/40 text-cyan-400 border border-cyan-500/20' : 'text-gray-500 hover:bg-white/5 hover:text-gray-300 border border-transparent'}`}>
                  {nav.icon}<span>{nav.label}</span>
                </button>
              ))}
            </div>
          </div>
          {/* Chat conversations list (only in chat view) */}
          {activeView === 'chat' && (
            <>
              <div className="px-3 py-3">
                <button onClick={() => { setActiveConvId(null); setMessages([]); setActions([]); socketRef.current?.disconnect() }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-800/60 to-blue-800/60 hover:from-cyan-700/60 hover:to-blue-700/60 border border-cyan-500/20 text-white text-sm font-medium transition-all">
                  <Plus className="w-4 h-4" /> New Chat
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-2 py-1">
                {conversations.map(c => (
                  <div key={c.conversation_id}
                    className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer mb-0.5 transition-all ${activeConvId === c.conversation_id ? 'bg-white/10 border border-white/10 text-white' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200 border border-transparent'}`}
                    onClick={() => openConversation(c.conversation_id)}>
                    <MessageSquare className="w-4 h-4 flex-shrink-0" />
                    <span className="flex-1 truncate text-sm">{c.title || 'Untitled'}</span>
                    <button onClick={e => { e.stopPropagation(); deleteConversation(c.conversation_id) }}
                      className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-all"><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                ))}
                {conversations.length === 0 && (
                  <div className="flex flex-col items-center mt-12 px-4">
                    <MessageSquare className="w-8 h-8 text-gray-700 mb-3" />
                    <p className="text-center text-gray-600 text-xs">No conversations yet</p>
                    <p className="text-center text-gray-700 text-xs mt-1">Start chatting below</p>
                  </div>
                )}
              </div>
            </>
          )}
          {activeView !== 'chat' && <div className="flex-1" />}
          {/* Settings button */}
          <div className="border-t border-white/5 px-3 py-3">
            <button onClick={() => setSettingsOpen(true)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-gray-400 hover:bg-white/5 hover:text-white text-sm transition-all">
              <Settings className="w-4 h-4" /> Settings
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-14 flex items-center px-4 border-b border-white/5 bg-black/20 backdrop-blur-xl flex-shrink-0">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-gray-400 hover:text-white mr-3 transition-colors"><Menu className="w-5 h-5" /></button>
          <div className="flex-1 flex items-center gap-3">
            {activeView === 'chat' && activeConvId ? (
              <>
                <span className="text-sm text-gray-300 truncate">{conversations.find(c => c.conversation_id === activeConvId)?.title || 'New conversation'}</span>
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${wsStatus === 'connected' ? 'bg-emerald-400 status-ring-pulse' : wsStatus === 'connecting' ? 'bg-amber-400 animate-pulse' : 'bg-gray-600'}`} />
                <span className="text-xs text-gray-500">{wsStatus === 'connected' ? 'Connected' : wsStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}</span>
              </>
            ) : activeView !== 'chat' ? (
              <span className="text-sm text-gray-300 capitalize font-medium">{activeView}</span>
            ) : (
              <span className="text-sm text-gray-500">Start a new conversation</span>
            )}
          </div>
          {!sidebarOpen && (
            <div className="flex items-center gap-2 mr-4">
              <img src="/codeit-logo.png" alt="CODEIT" className="w-6 h-6 object-contain" />
              <span className="text-sm font-bold text-white">CODEIT</span>
            </div>
          )}
        </header>

        {/* View router */}
        {activeView === 'chat' ? (
          <>
            <div className="flex-1 overflow-y-auto relative">
              {showWelcome ? (
                <WelcomeHero onExampleClick={handleExampleClick} />
              ) : (
                <div className="max-w-4xl mx-auto py-4">
                  {messages.map((msg, i) => {
                    const nextMsgId = messages[i + 1]?.id || Infinity
                    const betweenActions = actions.filter(a => a.id > msg.id && a.id < nextMsgId)
                    return (<div key={msg.id}><MessageBubble msg={msg} />{betweenActions.map(a => <ActionCard key={a.id} action={a} />)}</div>)
                  })}
                  {actions.filter(a => a.id > (messages[messages.length - 1]?.id || 0)).map(a => (<ActionCard key={a.id} action={a} />))}
                  {isAgentRunning && <TypingIndicator />}
                  <div ref={chatEndRef} />
                </div>
              )}
            </div>
            {/* File upload preview */}
            {uploadedFiles.length > 0 && (
              <div className="border-t border-white/5 bg-black/20 px-4 py-2">
                <div className="max-w-4xl mx-auto flex flex-wrap gap-2">
                  {uploadedFiles.map((file, idx) => (
                    <div key={idx} className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-gray-300">
                      <Paperclip className="w-3 h-3 text-cyan-400" />
                      <span className="truncate max-w-32">{file.name}</span>
                      <span className="text-gray-600">({(file.size / 1024).toFixed(0)}KB)</span>
                      <button onClick={() => removeFile(idx)} className="text-gray-500 hover:text-red-400 transition-colors"><X className="w-3 h-3" /></button>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* Chat input */}
            <div className="border-t border-white/5 bg-black/30 backdrop-blur-xl px-4 py-3 flex-shrink-0">
              <div className="max-w-4xl mx-auto">
                <div className="flex items-end gap-3 bg-white/5 border border-white/10 rounded-2xl px-4 py-2 focus-within:border-cyan-500/30 transition-all">
                  <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileSelect}
                    accept="image/*,.pdf,.doc,.docx,.txt,.md,.json,.csv,.zip,.tar,.gz,.py,.js,.ts,.tsx,.jsx,.html,.css,.java,.go,.rs,.cpp,.c,.h,.rb,.php,.swift,.kt" />
                  <button onClick={() => fileInputRef.current?.click()} className="p-2 rounded-lg text-gray-500 hover:text-cyan-400 hover:bg-white/5 transition-all flex-shrink-0" title="Upload files">
                    <Paperclip className="w-4 h-4" />
                  </button>
                  <textarea ref={inputRef} value={input} onChange={handleInputChange} onKeyDown={handleKeyDown}
                    placeholder={activeConvId ? "Type a message..." : "Describe what you want to build..."} rows={1}
                    className="flex-1 bg-transparent text-white placeholder-gray-500 resize-none focus:outline-none text-sm py-1.5 max-h-48" />
                  <button onClick={sendMessage} disabled={(!input.trim() && uploadedFiles.length === 0) || isAgentRunning}
                    className="p-2.5 rounded-xl bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white disabled:opacity-30 transition-all flex-shrink-0 shadow-lg shadow-cyan-900/20">
                    <Send className="w-4 h-4" />
                  </button>
                </div>
                <p className="text-center text-xs text-gray-600 mt-2">Powered by CODEIT Digital Solutions</p>
              </div>
            </div>
          </>
        ) : activeView === 'skills' ? (
          <SkillsPanel />
        ) : activeView === 'knowledge' ? (
          <KnowledgePanel />
        ) : activeView === 'prompts' ? (
          <PromptsPanel />
        ) : activeView === 'connectors' ? (
          <ConnectorsPanel />
        ) : activeView === 'deploy' ? (
          <DeployPanel />
        ) : activeView === 'logs' ? (
          <LogsPanel />
        ) : null}
      </main>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default App
