import { useState, useEffect } from 'react'
import { Settings, X, Loader2 } from 'lucide-react'
import { apiGet, apiPost } from '../utils/api'

export function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
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
