import { useState, useEffect } from 'react'
import {
  Rocket, Server, Box, Cloud, Cpu, Globe,
  Settings, Sparkles, RefreshCw, Loader2,
} from 'lucide-react'
import * as codeitApi from '../services/codeitApi'
import { emitLog } from '../utils/logger'

export function DeployPanel({ onDeploy }: { onDeploy?: (msg: string) => void }) {
  const targets = [
    { id: 'local', name: 'Local Server', desc: 'Deploy to your local machine or network', icon: <Server className="w-5 h-5" />, status: 'ready' as const, cmd: 'Deploy my app to the local server' },
    { id: 'docker', name: 'Docker Container', desc: 'Build and run inside Docker container', icon: <Box className="w-5 h-5" />, status: 'ready' as const, cmd: 'Deploy my app to a Docker container' },
    { id: 'aws', name: 'AWS (EC2 / ECS)', desc: 'Deploy to Amazon Web Services cloud', icon: <Cloud className="w-5 h-5" />, status: 'needs_config' as const, cmd: 'Deploy my app to AWS EC2' },
    { id: 'runpod', name: 'RunPod GPU', desc: 'Deploy to GPU cloud for ML workloads', icon: <Cpu className="w-5 h-5" />, status: 'needs_config' as const, cmd: 'Deploy my app to RunPod GPU' },
    { id: 'custom', name: 'Custom Server', desc: 'Deploy via SSH to any remote server', icon: <Globe className="w-5 h-5" />, status: 'needs_config' as const, cmd: 'Deploy my app to my custom server via SSH' },
  ]
  const [deploying, setDeploying] = useState<string | null>(null)
  const [_jobs, setJobs] = useState<Array<{ id: string; target: string; status: string; created_at?: string }>>([])

  useEffect(() => {
    codeitApi.listDeployJobs().then(data => setJobs(data)).catch(() => {})
  }, [])

  function handleDeploy(t: typeof targets[0]) {
    setDeploying(t.id)
    codeitApi.createDeployJob(t.id, {}).then(job => {
      setJobs(prev => [job, ...prev])
      emitLog('info', 'deploy', `Deploy job created: ${job.id} (${t.name})`)
    }).catch(err => {
      emitLog('error', 'deploy', `Deploy failed: ${err.message}`)
    })
    if (onDeploy) onDeploy(t.cmd)
    setTimeout(() => setDeploying(null), 2000)
  }

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
                <button onClick={() => handleDeploy(t)} disabled={deploying === t.id}
                  className={`px-4 py-2 rounded-xl text-sm transition-all flex items-center gap-2 ${t.status === 'ready' ? 'bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white' : 'border border-white/10 text-gray-400 hover:text-white hover:bg-white/5'} disabled:opacity-50`}>
                  {deploying === t.id ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Deploying...</> : t.status === 'ready' ? <><Rocket className="w-3.5 h-3.5" /> Deploy</> : <><Settings className="w-3.5 h-3.5" /> Configure</>}
                </button>
              </div>
            </div>
          ))}
          <div className="mt-6 p-4 rounded-2xl bg-white/3 border border-white/5">
            <h3 className="text-sm font-medium text-white mb-2 flex items-center gap-2"><Sparkles className="w-4 h-4 text-cyan-400" /> Quick Deploy via Chat</h3>
            <p className="text-xs text-gray-500">You can also deploy by chatting with the agent. Try saying:</p>
            <div className="mt-3 space-y-1.5">
              {['Deploy my app to Docker', 'Deploy to my AWS EC2 instance', 'Push to my server at 192.168.1.100'].map(cmd => (
                <button key={cmd} onClick={() => onDeploy?.(cmd)} className="w-full text-left text-xs text-cyan-400/70 font-mono bg-white/3 rounded-lg px-3 py-1.5 hover:bg-white/5 hover:text-cyan-400 transition-all cursor-pointer">"{cmd}"</button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
