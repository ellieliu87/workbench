import { useEffect, useMemo, useState } from 'react'
import {
  Workflow as WorkflowIcon,
  ShieldCheck,
  Building2,
  Landmark,
  TrendingUp,
  Sparkles,
  ChevronDown,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import api from '@/lib/api'
import type {
  DataServiceCard,
  DataServicesIntegrationStatus,
  DataServicesPayload,
} from '@/types'

interface Props {
  functionId: string
  functionName: string
  onAskAgent: (q: string) => void
}

// Icon string from the backend → lucide-react component. Anything not
// in the table renders the WorkflowIcon as a safe fallback so a future
// icon name from OneLake doesn't blank out the card.
const ICON_MAP: Record<string, typeof WorkflowIcon> = {
  WorkflowIcon,
  ShieldCheck,
  Building2,
  Landmark,
  TrendingUp,
}

export default function DataServicesSection({ functionId, functionName, onAskAgent }: Props) {
  const setEntity = useChatStore((s) => s.setEntity)
  const [payload, setPayload] = useState<DataServicesPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ccarYear, setCcarYear] = useState<string | null>(null)

  useEffect(() => {
    setError(null)
    api
      .get<DataServicesPayload>('/api/data_services', { params: { function_id: functionId } })
      .then((r) => {
        setPayload(r.data)
        if (r.data.ccar_years.length && !ccarYear) setCcarYear(r.data.ccar_years[0])
      })
      .catch((e) => setError(e?.response?.data?.detail || 'Could not load Data Services'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [functionId])

  const ccarCards = useMemo(() => {
    if (!payload || !ccarYear) return []
    return payload.ccar_scenarios[ccarYear] || []
  }, [payload, ccarYear])

  const askAboutScenario = (q: string) => {
    setEntity('scenario', null)
    onAskAgent(q)
  }

  if (error) {
    return (
      <div
        className="text-xs px-3 py-2 rounded-md"
        style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
      >
        {error}
      </div>
    )
  }

  if (!payload) {
    return (
      <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
        <Loader2 size={14} className="animate-spin" /> Loading data services…
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Section 1 — Predictive Analytics */}
      <ServiceGroup
        title="Scenario Service from Predictive Analytics"
        sublabel="Built-in services maintained by the Predictive Analytics team."
        status={payload.predictive_status}
      >
        <CardGrid>
          {payload.predictive.map((card) => (
            <ServiceCard
              key={card.id}
              spec={card}
              onAskAgent={() => onAskAgent(card.agent_prompt)}
            />
          ))}
        </CardGrid>
      </ServiceGroup>

      {/* Section 2 — CCAR */}
      <ServiceGroup
        title="CCAR"
        sublabel="Comprehensive Capital Analysis & Review — BHC and supervisory paths."
        status={payload.ccar_status}
        right={
          payload.ccar_years.length ? (
            <div className="flex items-center gap-2">
              <span
                className="text-[10px] font-bold uppercase tracking-widest"
                style={{ color: 'var(--text-muted)' }}
              >
                Year
              </span>
              <div className="relative">
                <select
                  value={ccarYear ?? payload.ccar_years[0]}
                  onChange={(e) => setCcarYear(e.target.value)}
                  className="text-xs font-mono font-semibold pl-2 pr-7 py-1 rounded-md appearance-none cursor-pointer"
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                  }}
                >
                  {payload.ccar_years.map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
                <ChevronDown
                  size={11}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: 'var(--text-muted)' }}
                />
              </div>
            </div>
          ) : null
        }
      >
        <CardGrid>
          {ccarCards.map((card) => (
            <ServiceCard
              key={card.id}
              spec={card}
              onAskAgent={() => askAboutScenario(card.agent_prompt)}
            />
          ))}
        </CardGrid>
      </ServiceGroup>

      {/* Section 3 — Outlook */}
      <ServiceGroup
        title="Outlook"
        sublabel="Internal forward-looking scenarios."
        status={payload.outlook_status}
      >
        <CardGrid>
          {payload.outlook.map((card) => (
            <ServiceCard
              key={card.id}
              spec={card}
              onAskAgent={() => askAboutScenario(card.agent_prompt)}
            />
          ))}
        </CardGrid>
      </ServiceGroup>
    </div>
  )
}

// ── Section wrapper ────────────────────────────────────────────────────
function ServiceGroup({
  title, sublabel, right, status, children,
}: {
  title: string
  sublabel?: string
  right?: React.ReactNode
  status?: DataServicesIntegrationStatus
  children: React.ReactNode
}) {
  return (
    <section>
      <div className="flex items-end justify-between mb-3 gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2
              className="text-[13px] font-bold uppercase tracking-wider"
              style={{ color: 'var(--text-primary)' }}
            >
              {title}
            </h2>
            {status && <IntegrationBadge status={status} />}
          </div>
          {sublabel && (
            <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {sublabel}
            </div>
          )}
        </div>
        {right}
      </div>
      {children}
    </section>
  )
}

function IntegrationBadge({ status }: { status: DataServicesIntegrationStatus }) {
  // Three states: live (green), enabled-but-fallback (amber), static
  // (subtle grey). Hover surfaces the detail string from the backend
  // (e.g. "OneLake `Finance/cma/ccar_scenarios` — live").
  let color: string, bg: string, label: string, Icon = CheckCircle2
  if (status.live) {
    color = 'var(--success)'; bg = 'var(--success-bg)'
    label = `live · ${status.name}`
  } else if (status.enabled) {
    color = 'var(--warning)'; bg = 'var(--warning-bg)'
    label = `${status.name} · fallback`
    Icon = AlertCircle
  } else {
    color = 'var(--text-muted)'; bg = 'var(--bg-elevated)'
    label = 'static'
    Icon = CheckCircle2
  }
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase tracking-widest"
      style={{ color, background: bg, border: `1px solid ${bg}` }}
      title={status.detail}
    >
      <Icon size={9} /> {label}
    </span>
  )
}

// Shared 2-up grid so cards remain the same size regardless of how
// many a section happens to contain.
function CardGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 auto-rows-fr">
      {children}
    </div>
  )
}

// ── The one card ───────────────────────────────────────────────────────
function ServiceCard({
  spec, onAskAgent,
}: { spec: DataServiceCard; onAskAgent: () => void }) {
  const Icon = ICON_MAP[spec.icon] || WorkflowIcon
  return (
    <article
      className="rounded-lg p-4 transition-all hover:shadow-md group flex flex-col h-full"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${spec.color}`,
      }}
    >
      <div className="flex items-start gap-3 flex-1">
        <div
          className="w-9 h-9 rounded-md flex items-center justify-center shrink-0"
          style={{ background: `${spec.color}1A`, color: spec.color }}
        >
          <Icon size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2 mb-0.5">
            <h3
              className="text-[13px] font-bold leading-tight truncate"
              style={{ color: 'var(--text-primary)' }}
            >
              {spec.title}
            </h3>
            <span
              className="font-mono text-[9px] font-semibold uppercase tracking-widest shrink-0"
              style={{ color: spec.color }}
            >
              {spec.tag}
            </span>
          </div>
          <div className="text-[11px] mb-2" style={{ color: 'var(--text-muted)' }}>
            {spec.subtitle}
          </div>
          <p
            className="text-[12px] leading-relaxed"
            style={{ color: 'var(--text-secondary)' }}
          >
            {spec.description}
          </p>
        </div>
      </div>
      <div className="pt-3 mt-auto">
        <button
          onClick={onAskAgent}
          className="text-[11px] font-semibold flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ color: spec.color }}
        >
          <Sparkles size={11} /> Ask agent →
        </button>
      </div>
    </article>
  )
}
