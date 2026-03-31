import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import * as codeitApi from '../services/codeitApi'
import { OrbsBackground } from './OrbsBackground'

export function LoginScreen({ onAuth }: { onAuth: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isRegister, setIsRegister] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password.trim()) { setError('Username and password are required'); return }
    setLoading(true); setError('')
    try {
      if (isRegister) {
        await codeitApi.register(username.trim(), password)
      } else {
        await codeitApi.login(username.trim(), password)
      }
      onAuth()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen mesh-gradient flex items-center justify-center p-4">
      <OrbsBackground />
      <div className="relative z-10 w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/codeit-logo.png" alt="CODEIT" className="w-16 h-16 mx-auto mb-4 object-contain" />
          <h1 className="text-3xl font-bold text-white tracking-tight">CODEIT</h1>
          <p className="text-gray-400 text-sm mt-1">Digital Solutions Platform</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-black/40 backdrop-blur-xl border border-white/10 rounded-2xl p-8 space-y-4">
          <h2 className="text-lg font-semibold text-white text-center">{isRegister ? 'Create Account' : 'Sign In'}</h2>
          {error && <div className="text-xs text-red-400 bg-red-900/20 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>}
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">Username</label>
            <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Enter username" autoFocus
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
          </div>
          <div>
            <label className="text-sm text-gray-400 mb-1.5 block">Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter password"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50" />
          </div>
          <button type="submit" disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-cyan-700 to-blue-700 hover:from-cyan-600 hover:to-blue-600 text-white font-medium transition-all disabled:opacity-50">
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> {isRegister ? 'Creating...' : 'Signing in...'}</> : isRegister ? 'Create Account' : 'Sign In'}
          </button>
          <p className="text-center text-sm text-gray-500">
            {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button type="button" onClick={() => { setIsRegister(!isRegister); setError('') }} className="text-cyan-400 hover:text-cyan-300 transition-colors">
              {isRegister ? 'Sign In' : 'Register'}
            </button>
          </p>
        </form>
        <p className="text-center text-xs text-gray-600 mt-4">Powered by CODEIT Digital Solutions</p>
      </div>
    </div>
  )
}
