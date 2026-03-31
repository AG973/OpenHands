import {
  Code2, Globe, Github, Smartphone, Cloud, Cpu,
  Sparkles, Rocket, Terminal, ArrowRight,
} from 'lucide-react'
import { OrbsBackground } from './OrbsBackground'

export function WelcomeHero({ onExampleClick }: { onExampleClick: (text: string) => void }) {
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
