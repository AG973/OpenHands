import { useState, useEffect } from 'react'
import { Brain, Plus, Save, Edit3, Trash, Search, Loader2 } from 'lucide-react'
import * as codeitApi from '../services/codeitApi'
import { emitLog } from '../utils/logger'
import type { KnowledgeItem } from '../types/codeit'

export function KnowledgePanel() {
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [editing, setEditing] = useState<KnowledgeItem | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    codeitApi.listKnowledge().then(data => { setItems(data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const filtered = query
    ? items.filter(i => i.title.toLowerCase().includes(query.toLowerCase()) || i.tags.some(t => t.toLowerCase().includes(query.toLowerCase())) || i.content.toLowerCase().includes(query.toLowerCase()))
    : items

  function saveItem(item: KnowledgeItem) {
    if (item.id) {
      codeitApi.updateKnowledge(item.id, { title: item.title, content: item.content, tags: item.tags }).then(updated => {
        setItems(p => p.map(i => i.id === item.id ? { ...i, ...updated } : i))
      }).catch(err => emitLog('error', 'knowledge', `Update failed: ${err.message}`))
    } else {
      codeitApi.createKnowledge({ title: item.title, content: item.content, tags: item.tags }).then(created => {
        setItems(p => [...p, created])
      }).catch(err => emitLog('error', 'knowledge', `Create failed: ${err.message}`))
    }
    setShowForm(false); setEditing(null)
  }
  function remove(id: string) {
    codeitApi.deleteKnowledge(id).then(() => setItems(p => p.filter(i => i.id !== id)))
      .catch(err => emitLog('error', 'knowledge', `Delete failed: ${err.message}`))
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div><h2 className="text-lg font-semibold text-white flex items-center gap-2"><Brain className="w-5 h-5 text-cyan-400" /> Knowledge Base</h2>
          <p className="text-xs text-gray-500 mt-1">Persistent memory the agent can reference</p></div>
        <button onClick={() => { setEditing({ id: '', title: '', content: '', tags: [], updated_at: '' }); setShowForm(true) }}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gradient-to-r from-cyan-800/60 to-blue-800/60 hover:from-cyan-700/60 hover:to-blue-700/60 border border-cyan-500/20 text-white text-sm transition-all">
          <Plus className="w-4 h-4" /> Add Knowledge</button>
      </div>
      {loading ? (
        <div className="flex-1 flex items-center justify-center"><Loader2 className="w-8 h-8 text-cyan-400 animate-spin" /></div>
      ) : showForm && editing ? (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-4">
            <input value={editing.title} onChange={e => setEditing({ ...editing, title: e.target.value })} placeholder="Title"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
            <textarea value={editing.content} onChange={e => setEditing({ ...editing, content: e.target.value })} placeholder="Knowledge content (markdown supported)..." rows={12}
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
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search knowledge..."
                className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
            </div>
            <div className="space-y-3">
              {filtered.map(item => (
                <div key={item.id} className="card-3d bg-white/3 border border-white/5 rounded-2xl p-4 hover:border-cyan-500/20 transition-all">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-cyan-900/50 text-cyan-400 flex items-center justify-center flex-shrink-0"><Brain className="w-5 h-5" /></div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-white">{item.title}</h3>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{item.content}</p>
                      {item.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {item.tags.map(tag => <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-cyan-900/30 text-cyan-400/80">{tag}</span>)}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => { setEditing(item); setShowForm(true) }} className="p-1.5 rounded-lg text-gray-500 hover:text-cyan-400 hover:bg-white/5 transition-all"><Edit3 className="w-3.5 h-3.5" /></button>
                      <button onClick={() => remove(item.id)} className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-white/5 transition-all"><Trash className="w-3.5 h-3.5" /></button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
