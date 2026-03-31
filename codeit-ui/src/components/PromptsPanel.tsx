import { useState, useEffect } from 'react'
import { FileText, Plus, Save, Edit3, Trash, Play, Loader2 } from 'lucide-react'
import * as codeitApi from '../services/codeitApi'
import { emitLog } from '../utils/logger'

interface PromptItem { id: string; name: string; content: string; active: boolean }

export function PromptsPanel() {
  const [prompts, setPrompts] = useState<PromptItem[]>([])
  const [editing, setEditing] = useState<PromptItem | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    codeitApi.listPrompts().then(data => { setPrompts(data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  function setActive(id: string) {
    codeitApi.updatePrompt(id, { active: true }).then(() => {
      setPrompts(p => p.map(x => ({ ...x, active: x.id === id })))
    }).catch(err => emitLog('error', 'prompts', `Set active failed: ${err.message}`))
  }
  function savePrompt(prompt: PromptItem) {
    if (prompt.id) {
      codeitApi.updatePrompt(prompt.id, { name: prompt.name, content: prompt.content, active: prompt.active }).then(updated => {
        setPrompts(p => p.map(x => x.id === prompt.id ? { ...x, ...updated } : x))
      }).catch(err => emitLog('error', 'prompts', `Update failed: ${err.message}`))
    } else {
      codeitApi.createPrompt({ name: prompt.name, content: prompt.content, active: prompt.active }).then(created => {
        setPrompts(p => [...p, created])
      }).catch(err => emitLog('error', 'prompts', `Create failed: ${err.message}`))
    }
    setShowForm(false); setEditing(null)
  }
  function remove(id: string) {
    codeitApi.deletePrompt(id).then(() => setPrompts(p => p.filter(x => x.id !== id)))
      .catch(err => emitLog('error', 'prompts', `Delete failed: ${err.message}`))
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div><h2 className="text-lg font-semibold text-white flex items-center gap-2"><FileText className="w-5 h-5 text-cyan-400" /> Prompts</h2>
          <p className="text-xs text-gray-500 mt-1">Custom system prompts to guide agent behavior</p></div>
        <button onClick={() => { setEditing({ id: '', name: '', content: '', active: false }); setShowForm(true) }}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gradient-to-r from-cyan-800/60 to-blue-800/60 hover:from-cyan-700/60 hover:to-blue-700/60 border border-cyan-500/20 text-white text-sm transition-all">
          <Plus className="w-4 h-4" /> New Prompt</button>
      </div>
      {loading ? (
        <div className="flex-1 flex items-center justify-center"><Loader2 className="w-8 h-8 text-cyan-400 animate-spin" /></div>
      ) : showForm && editing ? (
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
