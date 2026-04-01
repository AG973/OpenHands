import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  ChevronDown, ChevronRight, Terminal, FileEdit, Bot,
  User, Loader2, Zap,
} from 'lucide-react'
import type { ChatMessage, AgentAction } from '../utils/eventParser'

export function TypingIndicator() {
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

export function ActionCard({ action }: { action: AgentAction }) {
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

export function MessageBubble({ msg }: { msg: ChatMessage }) {
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
