import { useState, useEffect, useRef, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  MessageSquare, Plus, Send, Settings, Trash2, X,
  ChevronDown, ChevronRight, Terminal, FileEdit, Bot,
  User, Loader2, Zap, Menu, Code2, Rocket, Smartphone,
  Globe, Github, Cloud, Cpu, Sparkles, ArrowRight
} from 'lucide-react'
import './App.css'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || ''

interface ChatMessage { id: number; role: 'user' | 'assistant' | 'system'; content: string; timestamp: string }
interface AgentAction { id: number; type: 'command' | 'file_write' | 'file_edit' | 'browse' | 'think' | 'task' | 'other'; title: string; detail: string; status: 'running' | 'done' | 'error' }
interface ConversationMeta { conversation_id: string; title: string; created_at: string; status: string }

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`)
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`)
  return res.json()
}
async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`)
  return res.json()
}
async function apiDelete(path: string): Promise<void> { await fetch(`${BACKEND_URL}${path}`, { method: 'DELETE' }) }

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
  const socketRef = useRef<Socket | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
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
    sio.on('connect', () => setWsStatus('connected'))
    sio.on('oh_event', (evt: Record<string, unknown>) => {
      const evtId = Number(evt.id)
      if (seenIds.current.has(evtId)) return
      seenIds.current.add(evtId)
      const { message, action } = parseEvent(evt)
      if (message) { setMessages(prev => [...prev, message]); if (message.role === 'assistant') setIsAgentRunning(false) }
      if (action) { setActions(prev => [...prev, action]); if (action.status === 'running') setIsAgentRunning(true) }
      const extras = evt.extras as Record<string, string> | undefined
      if (evt.observation === 'agent_state_changed') {
        const state = extras?.agent_state
        if (state === 'awaiting_user_input' || state === 'finished' || state === 'error') setIsAgentRunning(false)
        else if (state === 'running') setIsAgentRunning(true)
      }
    })
    sio.on('disconnect', () => setWsStatus('disconnected'))
    sio.on('connect_error', () => setWsStatus('disconnected'))
    socketRef.current = sio
  }, [])

  async function createConversation(initialMsg?: string) {
    try {
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
    } catch (err) { console.error('Failed to create conversation:', err) }
  }

  async function openConversation(convId: string) {
    setActiveConvId(convId)
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
    if (!text) return
    if (!activeConvId) { createConversation(text); setInput(''); return }
    if (socketRef.current?.connected) {
      socketRef.current.emit('oh_user_action', { action: 'message', args: { content: text, image_urls: [], file_urls: [], timestamp: new Date().toISOString() } })
      setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: text, timestamp: new Date().toISOString() }])
      setIsAgentRunning(true)
      setInput('')
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }
  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }
  function handleExampleClick(text: string) { setInput(text); inputRef.current?.focus() }

  const showWelcome = !activeConvId && messages.length === 0

  return (
    <div className="flex h-screen mesh-gradient text-white overflow-hidden">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-72' : 'w-0'} flex-shrink-0 transition-all duration-300 overflow-hidden`}>
        <div className="w-72 h-full flex flex-col bg-black/30 backdrop-blur-xl border-r border-white/5">
          <div className="px-4 py-4 border-b border-white/5 flex items-center gap-3">
            <img src="/codeit-logo.png" alt="CODEIT" className="w-8 h-8 object-contain" />
            <div>
              <h1 className="text-base font-bold text-white tracking-tight">CODEIT</h1>
              <p className="text-xs text-gray-500 -mt-0.5">Digital Solutions</p>
            </div>
          </div>
          <div className="h-px shimmer-border" />
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
                  className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-all">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
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
          <div className="border-t border-white/5 px-3 py-3">
            <button onClick={() => setSettingsOpen(true)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-gray-400 hover:bg-white/5 hover:text-white text-sm transition-all">
              <Settings className="w-4 h-4" /> Settings
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-14 flex items-center px-4 border-b border-white/5 bg-black/20 backdrop-blur-xl flex-shrink-0">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-gray-400 hover:text-white mr-3 transition-colors">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1 flex items-center gap-3">
            {activeConvId ? (
              <>
                <span className="text-sm text-gray-300 truncate">
                  {conversations.find(c => c.conversation_id === activeConvId)?.title || 'New conversation'}
                </span>
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${wsStatus === 'connected' ? 'bg-emerald-400 status-ring-pulse' : wsStatus === 'connecting' ? 'bg-amber-400 animate-pulse' : 'bg-gray-600'}`} />
                <span className="text-xs text-gray-500">
                  {wsStatus === 'connected' ? 'Connected' : wsStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
                </span>
              </>
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

        <div className="flex-1 overflow-y-auto relative">
          {showWelcome ? (
            <WelcomeHero onExampleClick={handleExampleClick} />
          ) : (
            <div className="max-w-4xl mx-auto py-4">
              {messages.map((msg, i) => {
                const nextMsgId = messages[i + 1]?.id || Infinity
                const betweenActions = actions.filter(a => a.id > msg.id && a.id < nextMsgId)
                return (
                  <div key={msg.id}>
                    <MessageBubble msg={msg} />
                    {betweenActions.map(a => <ActionCard key={a.id} action={a} />)}
                  </div>
                )
              })}
              {actions.filter(a => a.id > (messages[messages.length - 1]?.id || 0)).map(a => (
                <ActionCard key={a.id} action={a} />
              ))}
              {isAgentRunning && <TypingIndicator />}
              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        <div className="border-t border-white/5 bg-black/30 backdrop-blur-xl px-4 py-3 flex-shrink-0">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-end gap-3 bg-white/5 border border-white/10 rounded-2xl px-4 py-2 focus-within:border-cyan-500/30 transition-all">
              <textarea ref={inputRef} value={input} onChange={handleInputChange} onKeyDown={handleKeyDown}
                placeholder={activeConvId ? "Type a message..." : "Describe what you want to build..."} rows={1}
                className="flex-1 bg-transparent text-white placeholder-gray-500 resize-none focus:outline-none text-sm py-1.5 max-h-48" />
              <button onClick={sendMessage} disabled={!input.trim() || isAgentRunning}
                className="p-2.5 rounded-xl bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white disabled:opacity-30 transition-all flex-shrink-0 shadow-lg shadow-cyan-900/20">
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-center text-xs text-gray-600 mt-2">Powered by CODEIT Digital Solutions</p>
          </div>
        </div>
      </main>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default App
