import { useEffect, useRef, useState } from 'react'
import {
  ArrowDown, ArrowUp, Lightbulb, Pin, Settings as SettingsIcon, Check,
  BarChart3, Table as TableIcon,
} from 'lucide-react'
import api from '@/lib/api'
import Chart from '@/components/charts/Chart'
import InteractiveTable from '@/components/charts/InteractiveTable'
import { useChatStore } from '@/store/chatStore'
import type { ChartSpec, PlotConfig, WorkspaceData } from '@/types'

interface Props {
  functionId: string
  onAskAgent: (q: string) => void
  onContextChange: (ctx: string | null) => void
}

interface PreviewBundle {
  spec: ChartSpec
  rows: Record<string, any>[]
  columns: string[]
  source: string
}

type SectionKey = 'pinned' | 'kpis' | 'charts' | 'tables' | 'insights'

interface Visibility {
  pinned: boolean
  kpis: boolean
  charts: boolean
  tables: boolean
  insights: boolean
}

const DEFAULT_VISIBILITY: Visibility = {
  pinned: true, kpis: true, charts: true, tables: true, insights: true,
}

function visibilityKey(functionId: string) {
  return `cma:overview:visibility:${functionId}`
}

function loadVisibility(functionId: string): Visibility {
  try {
    const raw = localStorage.getItem(visibilityKey(functionId))
    if (raw) return { ...DEFAULT_VISIBILITY, ...JSON.parse(raw) }
  } catch {}
  return DEFAULT_VISIBILITY
}

function saveVisibility(functionId: string, v: Visibility) {
  try {
    localStorage.setItem(visibilityKey(functionId), JSON.stringify(v))
  } catch {}
}

export default function OverviewTab({ functionId, onAskAgent, onContextChange }: Props) {
  const setEntity = useChatStore((s) => s.setEntity)
  const [data, setData] = useState<WorkspaceData | null>(null)
  const [pinnedTiles, setPinnedTiles] = useState<PlotConfig[]>([])
  const [previews, setPreviews] = useState<Record<string, PreviewBundle>>({})
  const [error, setError] = useState<string | null>(null)
  const [visibility, setVisibility] = useState<Visibility>(() => loadVisibility(functionId))
  const [customizeOpen, setCustomizeOpen] = useState(false)
  const customizeAnchorRef = useRef<HTMLButtonElement>(null)

  // Reload visibility when the function changes
  useEffect(() => { setVisibility(loadVisibility(functionId)) }, [functionId])

  // Persist visibility on every change
  useEffect(() => { saveVisibility(functionId, visibility) }, [functionId, visibility])

  useEffect(() => {
    if (!functionId) return
    setData(null); setError(null); setPinnedTiles([]); setPreviews({})
    api
      .get<WorkspaceData>(`/api/workspace/${functionId}`)
      .then((r) => setData(r.data))
      .catch((e) => setError(e?.response?.data?.detail || 'Failed to load workspace'))
    api
      .get<PlotConfig[]>(`/api/plots`, { params: { function_id: functionId, pinned: true } })
      .then((r) => setPinnedTiles(r.data))
      .catch(() => {})
  }, [functionId])

  // Render previews for pinned tiles
  useEffect(() => {
    pinnedTiles.forEach((p) => {
      api.get(`/api/plots/${p.id}/preview`).then((r) => {
        const spec: ChartSpec = {
          id: p.id,
          title: p.name,
          type: p.chart_type,
          data: r.data.preview_data,
          x_key: p.x_field,
          y_keys: p.y_fields,
          description: p.description || null,
        }
        const cols = (r.data.columns || []).map((c: any) => c.name) ||
          (r.data.preview_data[0] ? Object.keys(r.data.preview_data[0]) : [])
        setPreviews((prev) => ({
          ...prev,
          [p.id]: { spec, rows: r.data.preview_data, columns: cols, source: r.data.source },
        }))
      }).catch(() => {})
    })
  }, [pinnedTiles])

  useEffect(() => {
    if (!data) return
    const kpiSummary = data.kpis.map((k) => `${k.label}=${k.value}`).join(', ')
    const pinNote = pinnedTiles.length > 0 ? ` · ${pinnedTiles.length} pinned tile${pinnedTiles.length === 1 ? '' : 's'}` : ''
    onContextChange(`${data.function_name} (Overview): ${kpiSummary}${pinNote}`)
    return () => onContextChange(null)
  }, [data, pinnedTiles.length, onContextChange])

  const unpin = async (id: string) => {
    await api.post(`/api/plots/${id}/pin`)
    setPinnedTiles((tiles) => tiles.filter((t) => t.id !== id))
  }

  if (error) {
    return (
      <div className="panel" style={{ background: 'var(--error-bg)', borderColor: 'var(--error)' }}>
        <div style={{ color: 'var(--error)', fontWeight: 600 }}>{error}</div>
      </div>
    )
  }
  if (!data) return <div style={{ color: 'var(--text-muted)' }}>Loading workspace…</div>

  // Are any non-default sections visible?
  const anyVisible = visibility.pinned || visibility.kpis || visibility.charts || visibility.tables || visibility.insights
  const hiddenCount = Object.values(visibility).filter((v) => !v).length

  return (
    <div>
      {/* Customize affordance */}
      <div className="flex justify-end mb-3 relative">
        <button
          ref={customizeAnchorRef}
          onClick={() => setCustomizeOpen((o) => !o)}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
          style={{
            background: hiddenCount > 0 ? 'var(--accent-light)' : 'var(--bg-card)',
            border: '1px solid var(--border)',
            color: hiddenCount > 0 ? 'var(--accent)' : 'var(--text-secondary)',
          }}
        >
          <SettingsIcon size={12} />
          Customize
          {hiddenCount > 0 && (
            <span
              className="rounded-full px-1.5 py-0.5"
              style={{
                fontSize: 9, fontWeight: 700, lineHeight: 1,
                background: 'var(--accent)', color: '#fff',
              }}
            >
              {hiddenCount}
            </span>
          )}
        </button>
        {customizeOpen && (
          <CustomizePopover
            visibility={visibility}
            onChange={setVisibility}
            onClose={() => setCustomizeOpen(false)}
            pinnedCount={pinnedTiles.length}
            chartCount={data.charts.length}
            tableCount={data.tables.length}
            insightCount={data.insights.length}
          />
        )}
      </div>

      {!anyVisible && (
        <div
          className="panel text-center"
          style={{ padding: '28px 20px', borderStyle: 'dashed' }}
        >
          <SettingsIcon size={20} style={{ color: 'var(--text-muted)', margin: '0 auto 8px' }} />
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            All sections hidden
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            Click <strong>Customize</strong> to bring sections back, or pin tiles from the Analytics tab.
          </div>
        </div>
      )}

      {/* Pinned tiles */}
      {visibility.pinned && pinnedTiles.length > 0 && (
        <section className="mb-6">
          <SectionHeader
            icon={Pin}
            title={`Pinned (${pinnedTiles.length})`}
            hint="Pinned from Analytics — click the pin icon to remove"
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {pinnedTiles.map((p) => (
              <PinnedTileCard
                key={p.id}
                tile={p}
                preview={previews[p.id]}
                onUnpin={() => unpin(p.id)}
                onAskAgent={onAskAgent}
              />
            ))}
          </div>
        </section>
      )}

      {/* KPIs */}
      {visibility.kpis && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {data.kpis.map((k) => (
            <button
              key={k.label}
              onClick={() => {
                setEntity('kpi', k.label)
                onAskAgent(`Explain "${k.label}" — current value ${k.value}`)
              }}
              className="text-left transition-all"
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 12,
                padding: 16,
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)' }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)' }}
            >
              <div className="metric-label">{k.label}</div>
              <div className="metric-value mt-1">{k.value}</div>
              {k.delta && (
                <div
                  className={
                    k.delta_dir === 'up' ? 'delta-up'
                      : k.delta_dir === 'down' ? 'delta-down' : 'delta-flat'
                  }
                  style={{ fontSize: 12, fontWeight: 600, marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}
                >
                  {k.delta_dir === 'up' && <ArrowUp size={11} />}
                  {k.delta_dir === 'down' && <ArrowDown size={11} />}
                  {k.delta}
                  {k.sublabel && (
                    <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> · {k.sublabel}</span>
                  )}
                </div>
              )}
              {!k.delta && k.sublabel && (
                <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                  {k.sublabel}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Charts */}
      {visibility.charts && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {data.charts.map((c) => (
            <div key={c.id} className="panel">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="font-display text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {c.title}
                  </div>
                  {c.description && (
                    <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                      {c.description}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => onAskAgent(`Explain the ${c.title} chart`)}
                  className="text-xs px-2 py-1 rounded-md transition-colors"
                  style={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  Explain
                </button>
              </div>
              <Chart spec={c} />
            </div>
          ))}
        </div>
      )}

      {/* Tables */}
      {visibility.tables && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {data.tables.map((t) => (
            <div key={t.title} className="panel">
              <div className="font-display text-base font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
                {t.title}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      {t.columns.map((c) => (
                        <th
                          key={c}
                          className="text-left py-2 px-2"
                          style={{
                            color: 'var(--text-secondary)',
                            fontSize: 10,
                            fontWeight: 700,
                            letterSpacing: '0.08em',
                            textTransform: 'uppercase',
                            borderBottom: '1px solid var(--border)',
                          }}
                        >
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {t.rows.map((r, i) => (
                      <tr key={i}>
                        {r.map((cell, j) => (
                          <td
                            key={j}
                            className="py-2 px-2 font-mono"
                            style={{
                              borderBottom: '1px solid var(--border-subtle)',
                              color: cellColor(cell),
                            }}
                          >
                            {cell as any}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Insights */}
      {visibility.insights && (
        <div className="panel">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb size={14} style={{ color: 'var(--warning)' }} />
            <div className="font-display text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
              Today's Insights
            </div>
          </div>
          <ul className="space-y-2">
            {data.insights.map((s, i) => (
              <li key={i} className="flex gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                <span style={{ color: 'var(--accent)', fontWeight: 700 }}>·</span>
                <span>{s}</span>
                <button
                  onClick={() => onAskAgent(`Tell me more: ${s}`)}
                  className="ml-auto text-xs"
                  style={{ color: 'var(--accent)' }}
                >
                  discuss →
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Pinned tile card (read-only render with unpin) ──────────────────────────
function PinnedTileCard({
  tile, preview, onUnpin, onAskAgent,
}: {
  tile: PlotConfig
  preview?: PreviewBundle
  onUnpin: () => void
  onAskAgent: (q: string) => void
}) {
  const isTable = tile.tile_type === 'table'
  return (
    <div className="panel">
      <div className="flex items-start justify-between mb-3 gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center shrink-0"
            style={{
              background: isTable ? 'rgba(15,118,110,0.10)' : 'var(--accent-light)',
              color: isTable ? '#0F766E' : 'var(--accent)',
            }}
          >
            {isTable ? <TableIcon size={14} /> : <BarChart3 size={14} />}
          </div>
          <div className="min-w-0">
            <div className="font-display text-base font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
              {tile.name}
            </div>
            <div className="text-[11px] truncate" style={{ color: 'var(--text-muted)' }}>
              {isTable ? 'Table' : tile.chart_type}
              {preview?.source === 'live' && (
                <span className="pill ml-2" style={{ fontSize: 9, background: 'var(--success-bg)', color: 'var(--success)', borderColor: 'transparent' }}>
                  LIVE
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <button
            onClick={() => onAskAgent(`Explain the pinned ${isTable ? 'table' : 'chart'} "${tile.name}".`)}
            className="p-1.5 rounded-md"
            style={{ color: 'var(--text-muted)' }}
            title="Ask agent"
          >
            <span style={{ fontSize: 12 }}>✦</span>
          </button>
          <button
            onClick={onUnpin}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'var(--accent)' }}
            title="Unpin from Overview"
          >
            <Pin size={13} fill="currentColor" />
          </button>
        </div>
      </div>

      {!preview ? (
        <div
          className="flex items-center justify-center text-xs"
          style={{ height: 220, color: 'var(--text-muted)' }}
        >
          Loading preview…
        </div>
      ) : isTable ? (
        <InteractiveTable
          rows={preview.rows}
          columns={(tile.table_columns && tile.table_columns.length > 0)
            ? tile.table_columns
            : preview.columns}
          defaultSort={tile.table_default_sort || null}
          defaultSortDesc={!!tile.table_default_sort_desc}
          height={260}
        />
      ) : (
        <Chart spec={preview.spec} height={220} brushable />
      )}
    </div>
  )
}

// ── Customize popover ───────────────────────────────────────────────────────
function CustomizePopover({
  visibility, onChange, onClose, pinnedCount, chartCount, tableCount, insightCount,
}: {
  visibility: Visibility
  onChange: (v: Visibility) => void
  onClose: () => void
  pinnedCount: number
  chartCount: number
  tableCount: number
  insightCount: number
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    // Defer the handler to avoid catching the click that opened the popover
    const t = setTimeout(() => document.addEventListener('mousedown', handler), 0)
    return () => {
      clearTimeout(t)
      document.removeEventListener('mousedown', handler)
    }
  }, [onClose])

  const setKey = (k: SectionKey, value: boolean) => onChange({ ...visibility, [k]: value })
  const showAll = () => onChange({ ...DEFAULT_VISIBILITY })

  const rows: { k: SectionKey; label: string; count: number; subtle?: string }[] = [
    { k: 'pinned',   label: 'Pinned tiles',  count: pinnedCount,  subtle: pinnedCount === 0 ? 'pin from Analytics' : undefined },
    { k: 'kpis',     label: 'KPI strip',     count: 4 },
    { k: 'charts',   label: 'Charts',        count: chartCount },
    { k: 'tables',   label: 'Tables',        count: tableCount },
    { k: 'insights', label: "Today's insights", count: insightCount },
  ]

  return (
    <div
      ref={ref}
      className="absolute z-30 right-0 top-full mt-2 panel"
      style={{
        width: 280, padding: 0,
        boxShadow: '0 12px 32px rgba(0,0,0,0.12)',
      }}
    >
      <div
        className="px-3 py-2 flex items-center justify-between"
        style={{ borderBottom: '1px solid var(--border-subtle)' }}
      >
        <div className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
          Show on Overview
        </div>
        <button
          onClick={showAll}
          className="text-[11px]"
          style={{ color: 'var(--accent)', fontWeight: 600 }}
        >
          Show all
        </button>
      </div>
      <div>
        {rows.map(({ k, label, count, subtle }) => {
          const on = visibility[k]
          return (
            <button
              key={k}
              onClick={() => setKey(k, !on)}
              className="w-full flex items-center gap-3 px-3 py-2 transition-colors text-left"
              style={{
                background: 'transparent',
                borderBottom: '1px solid var(--border-subtle)',
              }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = 'var(--bg-elevated)')}
              onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
            >
              <div
                className="w-4 h-4 rounded flex items-center justify-center shrink-0"
                style={{
                  background: on ? 'var(--accent)' : 'var(--bg-elevated)',
                  border: `1px solid ${on ? 'var(--accent)' : 'var(--border)'}`,
                }}
              >
                {on && <Check size={10} color="#fff" strokeWidth={3} />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm" style={{ color: on ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: 500 }}>
                  {label}
                </div>
                {subtle && (
                  <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    {subtle}
                  </div>
                )}
              </div>
              <div className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>
                {count}
              </div>
            </button>
          )
        })}
      </div>
      <div className="px-3 py-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
        Saved per function in your browser.
      </div>
    </div>
  )
}

function SectionHeader({
  icon: Icon, title, hint,
}: { icon: any; title: string; hint?: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={13} style={{ color: 'var(--accent)' }} />
      <div className="font-display text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
        {title}
      </div>
      {hint && (
        <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
          {hint}
        </div>
      )}
    </div>
  )
}

function cellColor(cell: any): string {
  const s = String(cell || '').toUpperCase()
  if (s.includes('OK') || s.includes('PASS')) return 'var(--success)'
  if (s.includes('WATCH') || s.includes('WARN')) return 'var(--warning)'
  if (s.includes('BREACH') || s.includes('FAIL')) return 'var(--error)'
  return 'var(--text-primary)'
}
