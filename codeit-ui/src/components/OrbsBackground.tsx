export function OrbsBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="orb-1 absolute top-1/4 left-1/3 w-96 h-96 rounded-full opacity-20" style={{ background: 'radial-gradient(circle, #1e3a5f 0%, transparent 70%)' }} />
      <div className="orb-2 absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full opacity-15" style={{ background: 'radial-gradient(circle, #2d8cf0 0%, transparent 70%)' }} />
      <div className="orb-3 absolute top-1/2 right-1/3 w-64 h-64 rounded-full opacity-10" style={{ background: 'radial-gradient(circle, #4fc3f7 0%, transparent 70%)' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="ring-spin w-96 h-96 rounded-full border border-white/5" />
      </div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <div className="ring-spin-reverse w-72 h-72 rounded-full border border-cyan-500/10" />
      </div>
      <div className="pulse-glow absolute top-1/3 left-1/2 -translate-x-1/2 w-64 h-64 rounded-full" style={{ background: 'radial-gradient(circle, rgba(30,58,95,0.6) 0%, transparent 60%)' }} />
    </div>
  )
}
