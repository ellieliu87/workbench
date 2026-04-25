import { useLocation } from 'react-router-dom'
import { Bell, MessageCircle, Search } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

export default function Topbar() {
  const setOpen = useChatStore((s) => s.setOpen)
  const location = useLocation()

  const breadcrumb = (() => {
    if (location.pathname === '/home') return 'Home'
    if (location.pathname.startsWith('/workspace/')) {
      const fid = location.pathname.split('/')[2]
      return `Workspace · ${fid?.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}`
    }
    if (location.pathname.startsWith('/settings')) return 'Settings'
    return ''
  })()

  return (
    <header
      className="h-14 shrink-0 flex items-center justify-between px-6"
      style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-3 text-sm font-mono" style={{ color: 'var(--text-muted)' }}>
        <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{breadcrumb}</span>
      </div>

      <div className="flex-1 max-w-md mx-8">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--text-muted)' }}
          />
          <input
            placeholder="Search functions, KPIs, data sources…"
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm transition-colors"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
      </div>

      <div className="flex items-center gap-1">
        <button
          className="p-2 rounded-lg transition-colors"
          style={{ color: 'var(--text-muted)' }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)' }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--text-muted)' }}
          title="Alerts"
        >
          <Bell size={15} />
        </button>
        <button
          onClick={() => setOpen(true)}
          className="ml-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          <MessageCircle size={13} />
          Ask Agent
        </button>
      </div>
    </header>
  )
}
