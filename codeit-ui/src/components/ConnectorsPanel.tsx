import { useState, useEffect } from 'react'
import {
  Github, MessageCircle, Cloud, Cpu, Server, Plug,
  Link2, Loader2, Settings, X,
} from 'lucide-react'
import * as codeitApi from '../services/codeitApi'
import { emitLog } from '../utils/logger'

interface ConnectorItem { id: string; name: string; type: string; icon: string; status: 'connected' | 'disconnected' | 'error'; config: Record<string, string> }

export function ConnectorsPanel() {
  const [connectors, setConnectors] = useState<ConnectorItem[]>([])
  const [editing, setEditing] = useState<ConnectorItem | null>(null)
  const [validating, setValidating] = useState(false)
  const [validationMsg, setValidationMsg] = useState<string | null>(null)
  const [validationOk, setValidationOk] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    codeitApi.listConnectors().then(data => {
      if (data.length === 0) {
        const defaults = [
          { name: 'GitHub', type: 'github', icon: 'github', config: { token: '', org: '', default_branch: 'main' } },
          { name: 'Discord', type: 'discord', icon: 'discord', config: { bot_token: '', server_id: '', channel_id: '' } },
          { name: 'AWS', type: 'aws', icon: 'aws', config: { access_key: '', secret_key: '', region: 'us-east-1' } },
          { name: 'RunPod', type: 'runpod', icon: 'runpod', config: { api_key: '', gpu_type: 'RTX 4090' } },
          { name: 'Custom Server', type: 'server', icon: 'server', config: { host: '', port: '22', username: '', ssh_key: '' } },
        ]
        Promise.all(defaults.map(d => codeitApi.createConnector(d))).then(() => {
          codeitApi.listConnectors().then(seeded => { setConnectors(seeded); setLoading(false) })
        }).catch(() => setLoading(false))
      } else {
        setConnectors(data); setLoading(false)
      }
    }).catch(() => setLoading(false))
  }, [])

  const iconMap: Record<string, React.ReactNode> = {
    github: <Github className="w-5 h-5" />, discord: <MessageCircle className="w-5 h-5" />,
    aws: <Cloud className="w-5 h-5" />, runpod: <Cpu className="w-5 h-5" />, server: <Server className="w-5 h-5" />,
  }
  const descMap: Record<string, string> = {
    github: 'Repositories, PRs, Issues, Code Review', discord: 'Bot messaging, notifications, commands',
    aws: 'EC2, S3, Lambda, ECS deployment', runpod: 'GPU cloud computing for ML workloads', server: 'SSH access to remote servers',
  }
  const statusColors: Record<string, string> = { connected: 'bg-emerald-400', disconnected: 'bg-gray-600', error: 'bg-red-400' }

  async function validateConnector(c: ConnectorItem): Promise<{ ok: boolean; msg: string }> {
    switch (c.type) {
      case 'github': {
        if (!c.config.token) return { ok: false, msg: 'GitHub token is required' }
        const res = await fetch('https://api.github.com/user', { headers: { Authorization: `token ${c.config.token}`, Accept: 'application/json' } })
        if (!res.ok) return { ok: false, msg: `Invalid GitHub token (HTTP ${res.status})` }
        const user = await res.json() as { login: string }
        return { ok: true, msg: `Connected as ${user.login}` }
      }
      case 'discord': {
        if (!c.config.bot_token) return { ok: false, msg: 'Discord bot token is required' }
        if (c.config.bot_token.length < 50) return { ok: false, msg: 'Discord bot token appears too short' }
        if (!c.config.server_id && !c.config.channel_id) return { ok: true, msg: 'Bot token saved \u2014 add server/channel ID to enable messaging' }
        return { ok: true, msg: `Bot token saved${c.config.server_id ? ` (server: ${c.config.server_id})` : ''} \u2014 will verify when used` }
      }
      case 'aws': {
        if (!c.config.access_key || !c.config.secret_key) return { ok: false, msg: 'AWS access key and secret key are required' }
        if (!/^AKIA[A-Z0-9]{16}$/.test(c.config.access_key)) return { ok: false, msg: 'Invalid AWS access key format (should start with AKIA)' }
        if (c.config.secret_key.length < 20) return { ok: false, msg: 'AWS secret key appears too short' }
        return { ok: true, msg: `Saved (${c.config.region || 'us-east-1'}) \u2014 credentials not verified` }
      }
      case 'runpod': {
        if (!c.config.api_key) return { ok: false, msg: 'RunPod API key is required' }
        const res = await fetch('https://api.runpod.io/graphql?api_key=' + encodeURIComponent(c.config.api_key), {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: '{ myself { id email } }' })
        })
        if (!res.ok) return { ok: false, msg: `RunPod API error (HTTP ${res.status})` }
        const data = await res.json() as { data?: { myself?: { email?: string } }; errors?: unknown[] }
        if (data.errors) return { ok: false, msg: 'Invalid RunPod API key' }
        return { ok: true, msg: `Connected${data.data?.myself?.email ? ` (${data.data.myself.email})` : ''}` }
      }
      case 'server': {
        if (!c.config.host) return { ok: false, msg: 'Server host is required' }
        if (!c.config.username) return { ok: false, msg: 'SSH username is required' }
        const port = parseInt(c.config.port || '22')
        if (isNaN(port) || port < 1 || port > 65535) return { ok: false, msg: 'Invalid port number' }
        return { ok: true, msg: `Saved for ${c.config.username}@${c.config.host}:${port} \u2014 not verified` }
      }
      default:
        return { ok: true, msg: 'Connected' }
    }
  }

  async function saveConnector(c: ConnectorItem) {
    setValidating(true); setValidationMsg(null); setValidationOk(false)
    try {
      const result = await validateConnector(c)
      if (!result.ok) { setValidationMsg(result.msg); setValidationOk(false); setValidating(false); return }
      setValidationMsg(result.msg); setValidationOk(true)
      await codeitApi.updateConnector(c.id, { status: 'connected', config: c.config })
      setConnectors(p => p.map(x => x.id === c.id ? { ...c, status: 'connected' } : x))
      emitLog('info', 'connectors', `${c.name} connected successfully`)
      setTimeout(() => { setEditing(null); setValidationMsg(null) }, 1500)
    } catch (err) {
      setValidationMsg(`Connection failed: ${err instanceof Error ? err.message : String(err)}`)
      setConnectors(p => p.map(x => x.id === c.id ? { ...c, status: 'error' } : x))
    }
    setValidating(false)
  }
  function disconnect(id: string) {
    codeitApi.disconnectConnector(id).then(() => {
      setConnectors(p => p.map(c => c.id === id ? { ...c, status: 'disconnected', config: Object.fromEntries(Object.keys(c.config).map(k => [k, ''])) } : c))
      emitLog('info', 'connectors', `Disconnected connector ${id}`)
    }).catch(err => emitLog('error', 'connectors', `Disconnect failed: ${err.message}`))
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div><h2 className="text-lg font-semibold text-white flex items-center gap-2"><Plug className="w-5 h-5 text-cyan-400" /> Connectors</h2>
          <p className="text-xs text-gray-500 mt-1">Connect to external platforms and services</p></div>
      </div>
      {loading ? (
        <div className="flex-1 flex items-center justify-center"><Loader2 className="w-8 h-8 text-cyan-400 animate-spin" /></div>
      ) : editing ? (
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
            {validationMsg && (
              <div className={`text-xs px-3 py-2 rounded-lg ${validationOk ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/20' : 'bg-red-900/30 text-red-400 border border-red-500/20'}`}>{validationMsg}</div>
            )}
            <div className="flex gap-3 pt-2">
              <button onClick={() => saveConnector(editing)} disabled={validating} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white text-sm transition-all disabled:opacity-50">{validating ? <><Loader2 className="w-4 h-4 animate-spin" /> Validating...</> : <><Link2 className="w-4 h-4" /> Connect</>}</button>
              <button onClick={() => { setEditing(null); setValidationMsg(null) }} className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white text-sm transition-all">Cancel</button>
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
                      <div className={`w-2 h-2 rounded-full ${statusColors[c.status]}`} />
                      <span className="text-xs text-gray-500 capitalize">{c.status}</span></div>
                    <p className="text-xs text-gray-600 mt-0.5">{descMap[c.type] || c.type}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {c.status === 'connected' ? (
                      <button onClick={() => disconnect(c.id)} className="px-3 py-1.5 rounded-lg text-xs text-red-400 border border-red-500/20 hover:bg-red-900/20 transition-all flex items-center gap-1.5"><X className="w-3 h-3" /> Disconnect</button>
                    ) : (
                      <button onClick={() => setEditing(c)} className="px-3 py-1.5 rounded-lg text-xs text-cyan-400 border border-cyan-500/20 hover:bg-cyan-900/20 transition-all flex items-center gap-1.5"><Settings className="w-3 h-3" /> Configure</button>
                    )}
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
