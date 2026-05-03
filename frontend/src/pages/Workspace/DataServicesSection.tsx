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
  Eye,
  X,
} from 'lucide-react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { useChatStore } from '@/store/chatStore'
import api from '@/lib/api'
import type {
  DataServiceCard,
  DataServicesIntegrationStatus,
  DataServicesPayload,
} from '@/types'

interface PreviewTarget {
  id: string
  title: string
  color: string
  tag: string
}

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
  const [previewScenario, setPreviewScenario] = useState<PreviewTarget | null>(null)

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

  const askAboutScenario = (card: DataServiceCard) => {
    // Bind the scenario id when one is available so the macro-economist
    // (or anyone reading entity context) can resolve the right path.
    setEntity('scenario', card.scenario_id || null)
    onAskAgent(card.agent_prompt)
  }

  const askAboutPredictive = (card: DataServiceCard) => {
    // For Data Harness / DQC cards bound to a real Transform, pin the
    // entity so the chat router lands on transform-explainer and the
    // agent reads the actual recipe via `get_transform_recipe`.
    if (card.transform_id) {
      setEntity('transform', card.transform_id)
    } else {
      setEntity(null, null)
    }
    onAskAgent(card.agent_prompt)
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
              onAskAgent={() => askAboutPredictive(card)}
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
              onAskAgent={() => askAboutScenario(card)}
              onPreview={card.scenario_id ? () => setPreviewScenario({ id: card.scenario_id!, title: card.title, color: card.color, tag: card.tag }) : undefined}
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
              onAskAgent={() => askAboutScenario(card)}
              onPreview={card.scenario_id ? () => setPreviewScenario({ id: card.scenario_id!, title: card.title, color: card.color, tag: card.tag }) : undefined}
            />
          ))}
        </CardGrid>
      </ServiceGroup>

      {previewScenario && (
        <ScenarioPreviewPanel
          target={previewScenario}
          onClose={() => setPreviewScenario(null)}
        />
      )}
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
  spec, onAskAgent, onPreview,
}: { spec: DataServiceCard; onAskAgent: () => void; onPreview?: () => void }) {
  const Icon = ICON_MAP[spec.icon] || WorkflowIcon
  return (
    <article
      className="rounded-lg p-4 transition-all hover:shadow-md group flex flex-col h-full relative"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${spec.color}`,
      }}
    >
      {onPreview && (
        <button
          onClick={onPreview}
          className="absolute top-2.5 right-2.5 p-1.5 rounded-md opacity-60 group-hover:opacity-100 transition-opacity"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            color: spec.color,
          }}
          title="Preview scenario data"
        >
          <Eye size={11} />
        </button>
      )}
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
              style={{
                color: spec.color,
                marginRight: onPreview ? 24 : 0, // leave space for the Eye button
              }}
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

// ── Scenario preview side panel ───────────────────────────────────────
// Mirrors ScenariosSection.tsx's panel: line chart over the first 6
// numeric columns + scrollable table of every row. Pulls from the
// same /api/analytics/scenarios/{id}/preview endpoint that's used on
// the Workflow → Data Services tab.
const PREVIEW_PALETTE = ['#004977', '#059669', '#D97706', '#DC2626', '#7C3AED', '#0891B2']

function ScenarioPreviewPanel({
  target, onClose,
}: { target: PreviewTarget; onClose: () => void }) {
  const [data, setData] = useState<{ columns: string[]; rows: Record<string, any>[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setError(null)
    setData(null)
    api.get(`/api/analytics/scenarios/${target.id}/preview`)
      .then((r) => setData(r.data))
      .catch((e) => setError(e?.response?.data?.detail || 'Could not load scenario preview'))
  }, [target.id])

  const numericCols = useMemo(() => {
    if (!data) return []
    return data.columns.filter((c) => {
      if (c === 'month' || c === 'quarter' || c === 'date') return false
      return data.rows.some((r) => typeof r[c] === 'number')
    })
  }, [data])

  return (
    <>
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(11,15,25,0.45)' }}
        onClick={onClose}
      />
      <div
        className="fixed top-0 right-0 bottom-0 z-50 flex flex-col"
        style={{
          width: 'min(880px, 96vw)',
          background: 'var(--bg-card)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-12px 0 48px rgba(0,0,0,0.18)',
        }}
      >
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{
            background: `linear-gradient(135deg, ${target.color}, var(--accent))`,
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div>
            <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>
              {target.title}
            </div>
            <div className="font-mono" style={{ fontSize: 11, color: 'rgba(255,255,255,0.78)' }}>
              {target.tag} · scenario preview
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg" style={{ color: 'rgba(255,255,255,0.85)' }}>
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {error ? (
            <div
              className="text-xs px-3 py-2 rounded-md"
              style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
            >
              {error}
            </div>
          ) : !data ? (
            <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
              <Loader2 size={12} className="animate-spin" /> Loading scenario data…
            </div>
          ) : data.rows.length === 0 ? (
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Scenario has no path data yet.
            </div>
          ) : (
            <>
              {numericCols.length > 0 && (
                <div
                  className="rounded-lg p-3"
                  style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
                >
                  <div
                    className="text-[10px] font-semibold uppercase tracking-widest mb-2"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {numericCols.length > 6 ? 'First 6 series' : `${numericCols.length} series`}
                  </div>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={data.rows} margin={{ top: 6, right: 12, left: -10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                      <XAxis dataKey={data.columns[0]} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                      <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                      <Tooltip contentStyle={{
                        background: 'var(--bg-card)', border: '1px solid var(--border)',
                        borderRadius: 8, fontSize: 11, fontFamily: 'JetBrains Mono, monospace',
                      }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {numericCols.slice(0, 6).map((c, i) => (
                        <Line
                          key={c}
                          type="monotone"
                          dataKey={c}
                          stroke={PREVIEW_PALETTE[i % PREVIEW_PALETTE.length]}
                          strokeWidth={2}
                          dot={{ r: 2 }}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              <div>
                <div
                  className="text-[10px] font-semibold uppercase tracking-widest mb-2"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Path data ({data.rows.length} rows)
                </div>
                <div
                  className="overflow-auto rounded-lg"
                  style={{ border: '1px solid var(--border)', maxHeight: 360 }}
                >
                  <table className="w-full text-xs font-mono">
                    <thead style={{ background: 'var(--bg-elevated)', position: 'sticky', top: 0 }}>
                      <tr>
                        {data.columns.map((c) => (
                          <th
                            key={c}
                            className="text-left py-2 px-3 whitespace-nowrap"
                            style={{
                              fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                              textTransform: 'uppercase', color: 'var(--text-secondary)',
                              borderBottom: '1px solid var(--border)',
                            }}
                          >
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.rows.map((row, i) => (
                        <tr key={i}>
                          {data.columns.map((c) => (
                            <td
                              key={c}
                              className="py-1.5 px-3"
                              style={{ borderBottom: '1px solid var(--border-subtle)' }}
                            >
                              {typeof row[c] === 'number' ? row[c].toFixed(2) : String(row[c] ?? '—')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
