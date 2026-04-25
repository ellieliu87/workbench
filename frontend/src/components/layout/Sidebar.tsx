import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  Home, Settings, LogOut, Briefcase, LineChart, Droplet, ShieldAlert,
  Banknote, Building2, Activity, FileSpreadsheet, Sparkles,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import type { BusinessFunction } from '@/types'

const ICONS: Record<string, any> = {
  briefcase: Briefcase,
  'line-chart': LineChart,
  droplet: Droplet,
  'shield-alert': ShieldAlert,
  banknote: Banknote,
  'building-2': Building2,
  activity: Activity,
  'file-spreadsheet': FileSpreadsheet,
}

export default function Sidebar() {
  const { username, role, department, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [functions, setFunctions] = useState<BusinessFunction[]>([])

  useEffect(() => {
    api.get<BusinessFunction[]>('/api/functions').then((r) => setFunctions(r.data)).catch(() => {})
  }, [])

  const handleLogout = async () => {
    try { await api.post('/api/auth/logout') } catch {}
    logout()
    navigate('/login')
  }

  const initials = (username || 'U').slice(0, 2).toUpperCase()

  return (
    <aside
      className="w-[240px] shrink-0 flex flex-col h-screen"
      style={{ background: 'var(--bg-card)', borderRight: '1px solid var(--border)' }}
    >
      {/* Brand */}
      <div className="px-5 pt-5 pb-4" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, var(--accent), var(--teal))' }}
          >
            <Sparkles size={14} color="#fff" />
          </div>
          <div>
            <div className="font-display text-lg leading-none" style={{ color: 'var(--text-primary)' }}>
              CMA Workbench
            </div>
            <div
              className="font-mono mt-0.5"
              style={{ fontSize: '0.6rem', color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase' }}
            >
              Capital One · Self-Serve
            </div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 pt-3 pb-2 space-y-0.5 overflow-y-auto">
        <div className="px-2 pb-1.5 section-title">Main</div>
        <NavItem to="/home" label="Home" icon={Home} active={location.pathname === '/home'} />

        <div className="px-2 pt-3 pb-1.5 section-title">Functions</div>
        {functions.map((f) => {
          const Icon = ICONS[f.icon] || Briefcase
          return (
            <NavItem
              key={f.id}
              to={`/workspace/${f.id}`}
              label={f.short_name}
              icon={Icon}
              active={location.pathname === `/workspace/${f.id}`}
              accent={f.color}
            />
          )
        })}

        <div className="px-2 pt-3 pb-1.5 section-title">Configuration</div>
        <NavItem
          to="/settings"
          label="Settings"
          icon={Settings}
          active={location.pathname.startsWith('/settings')}
        />
      </nav>

      {/* User footer */}
      <div className="px-4 py-4" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold"
            style={{ background: 'linear-gradient(135deg, var(--accent), var(--teal))', color: '#fff' }}
          >
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
              {username || 'User'}
            </div>
            <div className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
              {role || 'Analyst'} · {department || 'Capital Markets'}
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="p-1.5 rounded-lg transition-colors shrink-0"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={(e) => {
              const el = e.currentTarget
              el.style.color = 'var(--error)'
              el.style.background = 'var(--error-bg)'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget
              el.style.color = 'var(--text-muted)'
              el.style.background = 'transparent'
            }}
            title="Logout"
          >
            <LogOut size={13} />
          </button>
        </div>
      </div>
    </aside>
  )
}

function NavItem({
  to, label, icon: Icon, active, accent,
}: {
  to: string
  label: string
  icon: any
  active?: boolean
  accent?: string
}) {
  return (
    <NavLink
      to={to}
      className={cn(
        'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 border-l-2',
      )}
      style={
        active
          ? {
              background: 'var(--accent-light)',
              borderLeftColor: accent || 'var(--accent)',
              color: 'var(--accent)',
              fontWeight: 600,
            }
          : { borderLeftColor: 'transparent', color: 'var(--text-secondary)' }
      }
      onMouseEnter={(e) => {
        if (active) return
        const el = e.currentTarget as HTMLElement
        el.style.color = 'var(--text-primary)'
        el.style.background = 'var(--bg-elevated)'
      }}
      onMouseLeave={(e) => {
        if (active) return
        const el = e.currentTarget as HTMLElement
        el.style.color = 'var(--text-secondary)'
        el.style.background = 'transparent'
      }}
    >
      <Icon size={15} className="shrink-0" />
      <span className="truncate">{label}</span>
    </NavLink>
  )
}
