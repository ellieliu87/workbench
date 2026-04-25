import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import api from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

export default function LoginPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [username, setUsername] = useState('demo')
  const [password, setPassword] = useState('capital1')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const r = await api.post('/api/auth/login', { username, password })
      setAuth({
        token: r.data.token,
        username: r.data.username,
        role: r.data.role,
        department: r.data.department,
      })
      navigate('/home')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Sign in failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{
        background:
          'radial-gradient(circle at 30% 20%, rgba(0,73,119,0.10), transparent 60%), radial-gradient(circle at 80% 80%, rgba(8,145,178,0.10), transparent 60%), var(--bg-page)',
      }}
    >
      <div className="w-full max-w-md mx-auto px-6">
        <div className="text-center mb-8">
          <div
            className="inline-flex w-12 h-12 rounded-2xl items-center justify-center mb-4"
            style={{ background: 'linear-gradient(135deg, var(--accent), var(--teal))' }}
          >
            <Sparkles size={20} color="#fff" />
          </div>
          <h1 className="font-display text-3xl mb-1" style={{ color: 'var(--text-primary)' }}>
            CMA Workbench
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Self-serve analytics for Capital Markets &amp; Finance
          </p>
        </div>

        <form
          onSubmit={submit}
          className="panel"
          style={{ boxShadow: '0 24px 48px rgba(0,0,0,0.06)' }}
        >
          <label className="block mb-3">
            <span
              className="block text-[11px] font-semibold uppercase tracking-widest mb-1"
              style={{ color: 'var(--text-secondary)' }}
            >
              Username
            </span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
            />
          </label>
          <label className="block mb-4">
            <span
              className="block text-[11px] font-semibold uppercase tracking-widest mb-1"
              style={{ color: 'var(--text-secondary)' }}
            >
              Password
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
            />
          </label>

          {error && (
            <div
              className="mb-4 px-3 py-2 rounded-lg text-xs"
              style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-50"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>

          <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
            <div
              className="text-[11px]"
              style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}
            >
              Demo users: alice · bob · carol · david · demo
              <br />
              Password: capital1
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
