import { useState, useEffect, useRef, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'
import {
  MessageSquare, Plus, Send, Settings, Trash2, X,
  Loader2, Menu, Rocket, Paperclip,
  BookOpen, Brain, FileText, Plug, ScrollText,
} from 'lucide-react'
import './App.css'
import * as codeitApi from './services/codeitApi'
import { BACKEND_URL, apiGet, apiPost, apiDelete } from './utils/api'
import { emitLog } from './utils/logger'
import { parseEvent, type ChatMessage, type AgentAction, type ConversationMeta, type SidebarView } from './utils/eventParser'
import { TypingIndicator, ActionCard, MessageBubble } from './components/ChatComponents'
import { SettingsModal } from './components/SettingsModal'
import { WelcomeHero } from './components/WelcomeHero'
import { SkillsPanel } from './components/SkillsPanel'
import { KnowledgePanel } from './components/KnowledgePanel'
import { PromptsPanel } from './components/PromptsPanel'
import { ConnectorsPanel } from './components/ConnectorsPanel'
import { LogsPanel } from './components/LogsPanel'
import { DeployPanel } from './components/DeployPanel'
import { LoginScreen } from './components/LoginScreen'

/* ═══════════════ MAIN APP ═══════════════ */
function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)

  // Check auth on mount
  useEffect(() => {
    const token = codeitApi.getAuthToken()
    if (!token) { setIsAuthenticated(false); return }
    codeitApi.validateToken().then(res => setIsAuthenticated(res.valid)).catch(() => setIsAuthenticated(false))
  }, [])

  if (isAuthenticated === null) {
    return <div className="min-h-screen mesh-gradient flex items-center justify-center"><Loader2 className="w-10 h-10 text-cyan-400 animate-spin" /></div>
  }
  if (!isAuthenticated) {
    return <LoginScreen onAuth={() => setIsAuthenticated(true)} />
  }

  return <AuthenticatedApp />
}

function AuthenticatedApp() {
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
  const [backendAlive, setBackendAlive] = useState<boolean | null>(null)
  const socketRef = useRef<Socket | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const seenIds = useRef<Set<number>>(new Set())
  const pendingMessageRef = useRef<string | null>(null)

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, actions])

  const loadConversations = useCallback(async () => {
    try {
      const data = await apiGet<{ results: ConversationMeta[] }>('/api/conversations?limit=50')
      setConversations(data.results || [])
      setBackendAlive(true)
    } catch { setBackendAlive(false) }
  }, [])
  useEffect(() => { loadConversations() }, [loadConversations])

  // Backend health check on mount
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/options/models`, { headers: { 'Accept': 'application/json' } })
        setBackendAlive(res.ok)
        emitLog('info', 'startup', `Backend ${res.ok ? 'reachable' : 'unhealthy'}: ${BACKEND_URL || '(same origin)'}/api/options/models -> ${res.status}`)
      } catch (err) {
        setBackendAlive(false)
        emitLog('error', 'startup', `Backend unreachable at ${BACKEND_URL || '(same origin)'}: ${err instanceof Error ? err.message : String(err)}`)
      }
    }
    checkBackend()
  }, [])

  const connectToConversation = useCallback((convId: string, preserveMessages = false) => {
    if (socketRef.current) { socketRef.current.disconnect(); socketRef.current = null }
    // Clear messages by default (prevents cross-conversation mixing and reconnect duplication)
    // Only preserve messages when creating a NEW conversation (optimistic display)
    if (!preserveMessages) setMessages([])
    setActions([]); seenIds.current = new Set(); setWsStatus('connecting'); setIsAgentRunning(false)
    const wsUrl = BACKEND_URL || window.location.origin
    emitLog('info', 'websocket', `Connecting to ${wsUrl}/socket.io?conversation_id=${convId}`)
    const sio = io(wsUrl, { transports: ['websocket', 'polling'], path: '/socket.io', query: { conversation_id: convId, latest_event_id: -1 } })
    sio.on('connect', () => {
      setWsStatus('connected'); emitLog('info', 'websocket', `Connected to conversation ${convId}`)
      // Send any pending message that was queued while disconnected
      const pending = pendingMessageRef.current
      if (pending) {
        pendingMessageRef.current = null
        sio.emit('oh_user_action', { action: 'message', args: { content: pending, image_urls: [], file_urls: [], timestamp: new Date().toISOString() } })
        setIsAgentRunning(true)
        emitLog('info', 'chat', `Sent queued message after reconnect: "${pending.slice(0, 80)}${pending.length > 80 ? '...' : ''}"`)
      }
    })
    sio.on('oh_event', (evt: Record<string, unknown>) => {
      const evtId = Number(evt.id)
      if (seenIds.current.has(evtId)) return
      seenIds.current.add(evtId)
      const { message, action } = parseEvent(evt)
      if (message) {
        setMessages(prev => {
          // Deduplicate: only check last few messages to catch optimistic display echoes
          const recent = prev.slice(-3)
          const isDuplicate = recent.some(m => m.role === message.role && m.content === message.content)
          if (isDuplicate) return prev
          return [...prev, message]
        })
        if (message.role === 'assistant') setIsAgentRunning(false)
      }
      if (action) { setActions(prev => [...prev, action]); if (action.status === 'running') setIsAgentRunning(true) }
      emitLog('event', 'websocket', `${evt.action || evt.observation || evt.type || 'event'} from ${evt.source || '?'}`)
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
      emitLog('info', 'conversation', `Created conversation ${convId}`)
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        try {
          const conv = await apiGet<ConversationMeta>(`/api/conversations/${convId}`)
          if (conv.status === 'RUNNING' || attempts > 90) {
            clearInterval(poll)
            try { await apiPost(`/api/conversations/${convId}/start`, { providers_set: [] }) } catch { /* may already be started */ }
            connectToConversation(convId, true)  // preserve optimistic message
            loadConversations()
          }
        } catch { if (attempts > 90) clearInterval(poll) }
      }, 2000)
    } catch (err) {
      console.error('Failed to create conversation:', err)
      emitLog('error', 'conversation', `Failed to create conversation: ${err instanceof Error ? err.message : String(err)}`)
      setIsAgentRunning(false)
      setMessages(prev => [...prev, {
        id: Date.now(), role: 'system',
        content: `Failed to create conversation: ${err instanceof Error ? err.message : 'Unknown error'}. Is the backend running at ${BACKEND_URL || '(same origin)'}?`,
        timestamp: new Date().toISOString()
      }])
    }
  }

  async function openConversation(convId: string) {
    setActiveConvId(convId); setActiveView('chat'); setMessages([])
    try {
      const conv = await apiGet<ConversationMeta>(`/api/conversations/${convId}`)
      if (conv.status === 'RUNNING') { connectToConversation(convId) }
      else {
        try { await apiPost(`/api/conversations/${convId}/start`, { providers_set: [] }) } catch { /* */ }
        let attempts = 0
        const poll = setInterval(async () => {
          attempts++
          try {
            const c = await apiGet<ConversationMeta>(`/api/conversations/${convId}`)
            if (c.status === 'RUNNING' || attempts > 90) { clearInterval(poll); connectToConversation(convId) }
          } catch { if (attempts > 90) clearInterval(poll) }
        }, 2000)
      }
    } catch { connectToConversation(convId) }
  }

  async function deleteConversation(convId: string) {
    try {
      await apiDelete(`/api/conversations/${convId}`)
    } catch (err) {
      emitLog('error', 'conversation', `Failed to delete ${convId}: ${err instanceof Error ? err.message : String(err)}`)
      return
    }
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
      emitLog('info', 'chat', `Sent message: "${text.slice(0, 80)}${text.length > 80 ? '...' : ''}"`)
    } else {
      emitLog('warn', 'chat', 'WebSocket not connected, message queued for resend after reconnect')
      pendingMessageRef.current = text
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'system', content: 'WebSocket not connected. Reconnecting and will resend your message...', timestamp: new Date().toISOString() }])
      if (activeConvId) connectToConversation(activeConvId)
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
          <div className={`ml-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs ${backendAlive === true ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/20' : backendAlive === false ? 'bg-red-900/30 text-red-400 border border-red-500/20' : 'bg-gray-800/30 text-gray-500 border border-white/10'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${backendAlive === true ? 'bg-emerald-400' : backendAlive === false ? 'bg-red-400' : 'bg-gray-500'}`} />
            {backendAlive === true ? 'Backend' : backendAlive === false ? 'Offline' : 'Checking...'}
          </div>
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
          <DeployPanel onDeploy={(msg) => { setActiveView('chat'); setInput(msg); setTimeout(() => inputRef.current?.focus(), 100) }} />
        ) : activeView === 'logs' ? (
          <LogsPanel />
        ) : null}
      </main>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default App
