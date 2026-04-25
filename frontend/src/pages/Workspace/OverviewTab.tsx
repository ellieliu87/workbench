import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Lightbulb } from 'lucide-react'
import api from '@/lib/api'
import Chart from '@/components/charts/Chart'
import type { WorkspaceData } from '@/types'

interface Props {
  functionId: string
  onAskAgent: (q: string) => void
  onContextChange: (ctx: string | null) => void
}

export default function OverviewTab({ functionId, onAskAgent, onContextChange }: Props) {
  const [data, setData] = useState<WorkspaceData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!functionId) return
    setData(null)
    setError(null)
    api
      .get<WorkspaceData>(`/api/workspace/${functionId}`)
      .then((r) => setData(r.data))
      .catch((e) => setError(e?.response?.data?.detail || 'Failed to load workspace'))
  }, [functionId])

  useEffect(() => {
    if (!data) return
    const kpiSummary = data.kpis.map((k) => `${k.label}=${k.value}`).join(', ')
    onContextChange(`${data.function_name} (Overview): ${kpiSummary}`)
    return () => onContextChange(null)
  }, [data, onContextChange])

  if (error) {
    return (
      <div className="panel" style={{ background: 'var(--error-bg)', borderColor: 'var(--error)' }}>
        <div style={{ color: 'var(--error)', fontWeight: 600 }}>{error}</div>
      </div>
    )
  }

  if (!data) {
    return <div style={{ color: 'var(--text-muted)' }}>Loading workspace…</div>
  }

  return (
    <div>
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {data.kpis.map((k) => (
          <button
            key={k.label}
            onClick={() => onAskAgent(`Explain "${k.label}" — current value ${k.value}`)}
            className="text-left transition-all"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: 16,
            }}
            onMouseEnter={(e) => {
              ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)'
            }}
            onMouseLeave={(e) => {
              ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'
            }}
          >
            <div className="metric-label">{k.label}</div>
            <div className="metric-value mt-1">{k.value}</div>
            {k.delta && (
              <div
                className={
                  k.delta_dir === 'up' ? 'delta-up'
                    : k.delta_dir === 'down' ? 'delta-down'
                    : 'delta-flat'
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

      {/* Charts */}
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

      {/* Tables */}
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

      {/* Insights */}
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
