import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, MessageCircle, LayoutDashboard, Database, Boxes, FlaskConical, BarChart3,
} from 'lucide-react'
import api from '@/lib/api'
import type { BusinessFunction } from '@/types'
import { useChatStore } from '@/store/chatStore'

import OverviewTab from './OverviewTab'
import DataTab from './DataTab'
import ModelsTab from './ModelsTab'
import AnalyticsTab from './AnalyticsTab'
import ReportsTab from './ReportsTab'

const TABS = [
  { id: 'overview',  label: 'Overview',  icon: LayoutDashboard },
  { id: 'data',      label: 'Data',      icon: Database },
  { id: 'models',    label: 'Models',    icon: Boxes },
  { id: 'analytics', label: 'Analytics', icon: FlaskConical },
  { id: 'reports',   label: 'Reports',   icon: BarChart3 },
] as const

type TabId = (typeof TABS)[number]['id']

export default function WorkspacePage() {
  const { functionId, tab } = useParams<{ functionId: string; tab?: string }>()
  const navigate = useNavigate()
  const setOpen = useChatStore((s) => s.setOpen)
  const setPageContext = useChatStore((s) => s.setPageContext)

  const active: TabId = (TABS.find((t) => t.id === tab)?.id || 'overview') as TabId
  const [meta, setMeta] = useState<BusinessFunction | null>(null)

  useEffect(() => {
    if (!functionId) return
    api.get<BusinessFunction>(`/api/functions/${functionId}`).then((r) => setMeta(r.data)).catch(() => {})
  }, [functionId])

  const askAgent = (q: string) => {
    setOpen(true)
    window.dispatchEvent(new CustomEvent('cma-chat', { detail: q }))
  }

  if (!functionId) return null

  return (
    <div className="max-w-[1320px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
        <div>
          <button
            onClick={() => navigate('/home')}
            className="flex items-center gap-1 text-xs mb-2"
            style={{ color: 'var(--text-muted)' }}
          >
            <ArrowLeft size={12} /> Back to home
          </button>
          <h1 className="page-header" style={{ color: meta?.color || 'var(--text-primary)' }}>
            {meta?.name || functionId}
          </h1>
          {meta && (
            <p className="text-sm max-w-3xl" style={{ color: 'var(--text-muted)' }}>
              {meta.description}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => askAgent(`Brief me on ${meta?.name || functionId} (${active} tab)`)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            <MessageCircle size={13} />
            Ask Agent
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div
        className="flex items-center gap-1 mb-6"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              onClick={() => navigate(`/workspace/${functionId}/${id}`)}
              className="px-4 py-2.5 text-sm font-medium flex items-center gap-2 transition-colors"
              style={{
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                borderBottom: `2px solid ${isActive ? 'var(--accent)' : 'transparent'}`,
                marginBottom: -1,
                fontWeight: isActive ? 600 : 500,
              }}
              onMouseEnter={(e) => {
                if (!isActive) (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)'
              }}
              onMouseLeave={(e) => {
                if (!isActive) (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)'
              }}
            >
              <Icon size={14} />
              {label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {active === 'overview' && (
        <OverviewTab
          functionId={functionId}
          onAskAgent={askAgent}
          onContextChange={setPageContext}
        />
      )}
      {active === 'data' && (
        <DataTab
          functionId={functionId}
          functionName={meta?.name || functionId}
          onAskAgent={askAgent}
          onContextChange={setPageContext}
        />
      )}
      {active === 'models' && (
        <ModelsTab
          functionId={functionId}
          functionName={meta?.name || functionId}
          onAskAgent={askAgent}
          onContextChange={setPageContext}
        />
      )}
      {active === 'analytics' && (
        <AnalyticsTab
          functionId={functionId}
          functionName={meta?.name || functionId}
          onAskAgent={askAgent}
          onContextChange={setPageContext}
        />
      )}
      {active === 'reports' && (
        <ReportsTab
          functionId={functionId}
          functionName={meta?.name || functionId}
          onAskAgent={askAgent}
          onContextChange={setPageContext}
        />
      )}
    </div>
  )
}
