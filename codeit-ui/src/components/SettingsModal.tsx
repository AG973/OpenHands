import { useState, useEffect } from 'react'
import { Settings, X, Loader2, ChevronDown, RefreshCw, Check, Server, Cloud, AlertCircle } from 'lucide-react'
import { apiGet, apiPost } from '../utils/api'

interface ModelOption {
  id: string
  name: string
  provider: string
  base_url: string
  requires_key: boolean
  size_gb?: number
}

interface ModelGroup {
  [provider: string]: ModelOption[]
}

interface ModelsResponse {
  ollama_available: boolean
  ollama_url: string
  groups: ModelGroup
  all_models: ModelOption[]
}

export function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Model selector state
  const [models, setModels] = useState<ModelsResponse | null>(null)
  const [loadingModels, setLoadingModels] = useState(false)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [customModel, setCustomModel] = useState(false)

  useEffect(() => {
    if (!open) return
    apiGet<Record<string, string>>('/api/settings').then(s => {
      setModel(s.llm_model || '')
      setBaseUrl(s.llm_base_url || '')
      setApiKey(s.llm_api_key || '')
    }).catch(() => {})
    fetchModels()
  }, [open])

  async function fetchModels() {
    setLoadingModels(true)
    try {
      const data = await apiGet<ModelsResponse>('/api/codeit/models')
      setModels(data)
    } catch {
      setModels(null)
    }
    setLoadingModels(false)
  }

  function selectModel(m: ModelOption) {
    setModel(m.id)
    setBaseUrl(m.base_url)
    if (!m.requires_key) setApiKey('local-llm')
    setDropdownOpen(false)
    setCustomModel(false)
  }

  function getSelectedModelInfo(): ModelOption | undefined {
    return models?.all_models.find(m => m.id === model)
  }

  async function save() {
    setSaving(true)
    try {
      await apiPost('/api/settings', { llm_model: model, llm_base_url: baseUrl, llm_api_key: apiKey })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally { setSaving(false) }
  }

  if (!open) return null

  const selectedInfo = getSelectedModelInfo()
  const isOllamaModel = model.startsWith('ollama/')
  const needsApiKey = selectedInfo ? selectedInfo.requires_key : !isOllamaModel && !model.includes('ollama')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md" onClick={onClose}>
      <div className="animate-scale-in bg-gray-900/95 border border-white/10 rounded-2xl p-6 w-full max-w-lg shadow-2xl shadow-black/50 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-cyan-400" /> Settings
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors"><X className="w-5 h-5" /></button>
        </div>

        <div className="space-y-5">
          {/* Model Selector */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-sm text-gray-400">Model</label>
              <div className="flex items-center gap-2">
                <button onClick={() => { setCustomModel(!customModel); setDropdownOpen(false) }}
                  className="text-xs text-gray-500 hover:text-cyan-400 transition-colors">
                  {customModel ? 'Use selector' : 'Custom model'}
                </button>
                <button onClick={fetchModels} disabled={loadingModels}
                  className="text-gray-500 hover:text-cyan-400 transition-colors disabled:opacity-50">
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingModels ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>

            {customModel ? (
              <input value={model} onChange={e => setModel(e.target.value)} placeholder="e.g. ollama/qwen2.5-coder:7b or openai/gpt-4o"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 transition-colors" />
            ) : (
              <div className="relative">
                <button onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="w-full flex items-center justify-between bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-left transition-colors hover:border-white/20 focus:outline-none focus:border-cyan-500/50">
                  {model ? (
                    <div className="flex items-center gap-2 min-w-0">
                      {isOllamaModel ? <Server className="w-4 h-4 text-emerald-400 flex-shrink-0" /> : <Cloud className="w-4 h-4 text-blue-400 flex-shrink-0" />}
                      <span className="text-white truncate">{selectedInfo?.name || model}</span>
                      {selectedInfo && <span className="text-xs text-gray-500 flex-shrink-0">{selectedInfo.provider}</span>}
                    </div>
                  ) : (
                    <span className="text-gray-600">Select a model...</span>
                  )}
                  <ChevronDown className={`w-4 h-4 text-gray-500 flex-shrink-0 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {dropdownOpen && (
                  <div className="absolute z-50 mt-1 w-full bg-gray-900 border border-white/10 rounded-xl shadow-2xl shadow-black/50 max-h-72 overflow-y-auto">
                    {models && Object.entries(models.groups).map(([provider, providerModels]) => (
                      <div key={provider}>
                        <div className="sticky top-0 px-3 py-1.5 text-xs font-medium text-gray-500 bg-gray-900/95 border-b border-white/5 flex items-center gap-1.5">
                          {provider.includes('Local') ? <Server className="w-3 h-3 text-emerald-400" /> : <Cloud className="w-3 h-3 text-blue-400" />}
                          {provider}
                          {provider.includes('Local') && <span className="ml-auto text-emerald-400/60 text-[10px]">FREE</span>}
                        </div>
                        {providerModels.map(m => (
                          <button key={m.id} onClick={() => selectModel(m)}
                            className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors hover:bg-white/5 ${model === m.id ? 'bg-cyan-900/20 text-cyan-400' : 'text-gray-300'}`}>
                            <div className="flex-1 min-w-0">
                              <div className="truncate">{m.name}</div>
                              {m.size_gb !== undefined && m.size_gb > 0 && (
                                <div className="text-[10px] text-gray-600">{m.size_gb} GB</div>
                              )}
                            </div>
                            {model === m.id && <Check className="w-4 h-4 text-cyan-400 flex-shrink-0" />}
                            {m.requires_key && <span className="text-[10px] text-amber-500/60 flex-shrink-0">KEY</span>}
                          </button>
                        ))}
                      </div>
                    ))}
                    {(!models || Object.keys(models.groups).length === 0) && (
                      <div className="px-3 py-4 text-center text-sm text-gray-500">
                        {loadingModels ? 'Loading models...' : 'No models found. Check Ollama or use custom model.'}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Ollama status indicator */}
            {models && (
              <div className="flex items-center gap-1.5 mt-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${models.ollama_available ? 'bg-emerald-400' : 'bg-gray-600'}`} />
                <span className="text-[11px] text-gray-500">
                  Ollama {models.ollama_available ? `connected (${models.groups['Ollama (Local)']?.length || 0} models)` : 'not detected'}
                  {!models.ollama_available && <span className="text-gray-600"> — install from ollama.com</span>}
                </span>
              </div>
            )}
          </div>

          {/* Base URL */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">Base URL</label>
            <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)}
              placeholder={isOllamaModel ? 'http://localhost:11434/v1' : 'https://api.openai.com/v1'}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 transition-colors" />
            <p className="text-[11px] text-gray-600 mt-1">Auto-filled when selecting a model. Change only if using a custom endpoint.</p>
          </div>

          {/* API Key */}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block flex items-center gap-2">
              API Key
              {needsApiKey && !apiKey && (
                <span className="flex items-center gap-1 text-amber-400/80 text-[11px]">
                  <AlertCircle className="w-3 h-3" /> Required for this model
                </span>
              )}
            </label>
            <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)}
              placeholder={needsApiKey ? 'Enter your API key' : 'local-llm (no key needed)'}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 transition-colors" />
          </div>
        </div>

        <button onClick={save} disabled={saving || !model}
          className="mt-6 w-full bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white font-medium py-2.5 rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : saved ? 'Saved!' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}
