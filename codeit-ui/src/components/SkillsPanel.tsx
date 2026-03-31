import { useState, useEffect } from 'react'
import { BookOpen, Plus, Save, Edit3, Trash, ToggleLeft, ToggleRight, Loader2 } from 'lucide-react'
import * as codeitApi from '../services/codeitApi'
import { emitLog } from '../utils/logger'

interface SkillItem { id: string; name: string; description: string; content: string; enabled: boolean }

export function SkillsPanel() {
  const [skills, setSkills] = useState<SkillItem[]>([])
  const [editing, setEditing] = useState<SkillItem | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    codeitApi.listSkills().then(items => { setSkills(items); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  function toggle(id: string) {
    const sk = skills.find(s => s.id === id)
    if (!sk) return
    codeitApi.updateSkill(id, { enabled: !sk.enabled }).then(updated => {
      setSkills(p => p.map(s => s.id === id ? { ...s, enabled: updated.enabled } : s))
    }).catch(err => emitLog('error', 'skills', `Toggle failed: ${err.message}`))
  }
  function remove(id: string) {
    codeitApi.deleteSkill(id).then(() => setSkills(p => p.filter(s => s.id !== id)))
      .catch(err => emitLog('error', 'skills', `Delete failed: ${err.message}`))
  }
  function saveSkill(s: SkillItem) {
    if (s.id) {
      codeitApi.updateSkill(s.id, s).then(updated => {
        setSkills(p => p.map(x => x.id === s.id ? { ...x, ...updated } : x))
      }).catch(err => emitLog('error', 'skills', `Update failed: ${err.message}`))
    } else {
      codeitApi.createSkill({ name: s.name, description: s.description, content: s.content, enabled: s.enabled }).then(created => {
        setSkills(p => [...p, created])
      }).catch(err => emitLog('error', 'skills', `Create failed: ${err.message}`))
    }
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
      {loading ? (
        <div className="flex-1 flex items-center justify-center"><Loader2 className="w-8 h-8 text-cyan-400 animate-spin" /></div>
      ) : showForm && editing ? (
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
