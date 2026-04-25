import { useEffect, useState } from 'react'
import {
  BarChart3, Plus, Trash2, X, Sparkles, LineChart as LineIcon, PieChart as PieIcon,
  TrendingUp, GitCommit, Layers, Database, FlaskConical,
} from 'lucide-react'
import api from '@/lib/api'
import Chart from '@/components/charts/Chart'
import type {
  ChartSpec, Dataset, AnalyticsRun, PlotConfig,
} from '@/types'

const CHART_TYPES: { id: PlotConfig['chart_type']; label: string; icon: any }[] = [
  { id: 'line',        label: 'Line',        icon: LineIcon },
  { id: 'bar',         label: 'Bar',         icon: BarChart3 },
  { id: 'area',        label: 'Area',        icon: TrendingUp },
  { id: 'pie',         label: 'Pie',         icon: PieIcon },
  { id: 'scatter',     label: 'Scatter',     icon: GitCommit },
  { id: 'stacked_bar', label: 'Stacked Bar', icon: Layers },
]

interface Props {
  functionId: string
  functionName: string
  onAskAgent: (q: string) => void
  onContextChange: (ctx: string | null) => void
}

export default function ReportsTab({ functionId, functionName, onAskAgent, onContextChange }: Props) {
  const [plots, setPlots] = useState<PlotConfig[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [runs, setRuns] = useState<AnalyticsRun[]>([])
  const [previews, setPreviews] = useState<Record<string, ChartSpec & { source?: string }>>({})
  const [designerOpen, setDesignerOpen] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<PlotConfig[]>('/api/plots', { params: { function_id: functionId } }),
      api.get<Dataset[]>('/api/datasets', { params: { function_id: functionId } }),
      api.get<AnalyticsRun[]>('/api/analytics/runs', { params: { function_id: functionId } }),
    ])
      .then(([p, d, r]) => { setPlots(p.data); setDatasets(d.data); setRuns(r.data) })
      .finally(() => setLoading(false))
  }

  useEffect(load, [functionId])

  useEffect(() => {
    onContextChange(`${functionName} (Reports tab): ${plots.length} report tile${plots.length === 1 ? '' : 's'}`)
    return () => onContextChange(null)
  }, [plots.length, functionName, onContextChange])

  // Render previews for saved plots
  useEffect(() => {
    plots.forEach((p) => {
      api.get(`/api/plots/${p.id}/preview`).then((r) => {
        const spec: ChartSpec & { source?: string } = {
          id: p.id,
          title: p.name,
          type: p.chart_type,
          data: r.data.preview_data,
          x_key: p.x_field,
          y_keys: p.y_fields,
          description: p.description || null,
          source: r.data.source,
        }
        setPreviews((prev) => ({ ...prev, [p.id]: spec }))
      })
    })
  }, [plots])

  const remove = async (id: string) => {
    if (!confirm('Delete this report?')) return
    await api.delete(`/api/plots/${id}`)
    setPreviews((p) => {
      const next = { ...p }
      delete next[id]
      return next
    })
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div>
          <div className="font-display text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            Reports
          </div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {loading
              ? 'Loading…'
              : `${plots.length} report tile${plots.length === 1 ? '' : 's'} · pulls from your bound datasets and analytics runs.`}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onAskAgent(`Suggest a report for ${functionName} based on what's available.`)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
            }}
          >
            <Sparkles size={13} /> Ask Agent
          </button>
          <button
            onClick={() => setDesignerOpen(true)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            <Plus size={13} /> New Report
          </button>
        </div>
      </div>

      {!loading && plots.length === 0 && (
        <div
          className="panel text-center"
          style={{ padding: '40px 20px', borderStyle: 'dashed' }}
        >
          <BarChart3 size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            No reports yet
          </div>
          <div className="text-xs mt-1 mb-4" style={{ color: 'var(--text-muted)' }}>
            Build a tile from a dataset, an analytics run, or sample data.
          </div>
          <button
            onClick={() => setDesignerOpen(true)}
            className="px-3 py-2 rounded-lg text-xs font-semibold"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            <Plus size={13} className="inline mr-1" /> New Report
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {plots.map((p) => {
          const spec = previews[p.id]
          return (
            <div key={p.id} className="panel">
              <div className="flex items-start justify-between mb-3">
                <div className="min-w-0">
                  <div className="font-display text-base font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                    {p.name}
                  </div>
                  <div className="text-[11px] truncate" style={{ color: 'var(--text-muted)' }}>
                    {p.chart_type} · {p.x_field} → {p.y_fields.join(', ')}
                    {spec?.source === 'live' && (
                      <span className="pill ml-2" style={{ fontSize: 9, background: 'var(--success-bg)', color: 'var(--success)', borderColor: 'transparent' }}>
                        LIVE
                      </span>
                    )}
                    {spec?.source === 'sample' && (
                      <span className="pill ml-2" style={{ fontSize: 9, background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
                        SAMPLE
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button
                    onClick={() => onAskAgent(`Explain the ${p.name} report.`)}
                    className="p-1.5 rounded-md"
                    style={{ color: 'var(--text-muted)' }}
                    title="Ask agent"
                  >
                    <Sparkles size={13} />
                  </button>
                  <button
                    onClick={() => remove(p.id)}
                    className="p-1.5 rounded-md"
                    style={{ color: 'var(--text-muted)' }}
                    title="Delete"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
              {spec ? (
                <Chart spec={spec} height={240} />
              ) : (
                <div
                  className="flex items-center justify-center text-xs"
                  style={{ height: 240, color: 'var(--text-muted)' }}
                >
                  Loading preview…
                </div>
              )}
              {p.description && (
                <div className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                  {p.description}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {designerOpen && (
        <ReportDesigner
          functionId={functionId}
          datasets={datasets}
          runs={runs}
          onClose={() => setDesignerOpen(false)}
          onCreated={() => { setDesignerOpen(false); load() }}
        />
      )}
    </div>
  )
}

// ── Designer ──────────────────────────────────────────────────────────
type SourceKind = 'dataset' | 'run' | 'sample'

function ReportDesigner({
  functionId, datasets, runs, onClose, onCreated,
}: {
  functionId: string
  datasets: Dataset[]
  runs: AnalyticsRun[]
  onClose: () => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [chartType, setChartType] = useState<PlotConfig['chart_type']>('line')
  const [sourceKind, setSourceKind] = useState<SourceKind>('dataset')
  const [datasetId, setDatasetId] = useState(datasets[0]?.id || '')
  const [runId, setRunId] = useState(runs[0]?.id || '')
  const [aggregation, setAggregation] = useState<PlotConfig['aggregation']>('none')
  const [fields, setFields] = useState<string[]>([])
  const [xField, setXField] = useState('')
  const [yFields, setYFields] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load fields whenever the source changes
  useEffect(() => {
    setXField('')
    setYFields([])
    const params: Record<string, string> = {}
    if (sourceKind === 'dataset' && datasetId) params.dataset_id = datasetId
    else if (sourceKind === 'run' && runId) params.run_id = runId
    else params.data_source_id = 'ds-snowflake-prod'
    api.get<{ fields: string[] }>('/api/plots/fields', { params }).then((r) => setFields(r.data.fields ?? []))
  }, [sourceKind, datasetId, runId])

  const toggleY = (f: string) => {
    setYFields((prev) => (prev.includes(f) ? prev.filter((y) => y !== f) : [...prev, f]))
  }

  const submit = async () => {
    if (!name || !xField || yFields.length === 0) return
    setSaving(true)
    setError(null)
    try {
      await api.post('/api/plots', {
        function_id: functionId,
        name,
        chart_type: chartType,
        dataset_id: sourceKind === 'dataset' ? datasetId : null,
        run_id: sourceKind === 'run' ? runId : null,
        data_source_id: sourceKind === 'sample' ? 'ds-snowflake-prod' : null,
        x_field: xField,
        y_fields: yFields,
        aggregation,
        filters: [],
        description,
      })
      onCreated()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  // Build a live preview spec
  const previewSpec: ChartSpec | null = (() => {
    if (!xField || yFields.length === 0) return null
    const sample =
      chartType === 'pie'
        ? [
            { [xField]: 'A', [yFields[0]]: 38 },
            { [xField]: 'B', [yFields[0]]: 27 },
            { [xField]: 'C', [yFields[0]]: 18 },
            { [xField]: 'D', [yFields[0]]: 17 },
          ]
        : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'].map((m, i) => ({
            [xField]: m,
            ...Object.fromEntries(yFields.map((y, j) => [y, 100 + i * 12 + j * 8])),
          }))
    return {
      id: 'preview', title: name || 'Preview', type: chartType,
      data: sample, x_key: xField, y_keys: yFields,
    }
  })()

  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(11,15,25,0.45)' }} onClick={onClose} />
      <div
        className="fixed top-0 right-0 bottom-0 z-50 flex flex-col"
        style={{
          width: 'min(960px, 96vw)',
          background: 'var(--bg-card)', borderLeft: '1px solid var(--border)',
          boxShadow: '-12px 0 48px rgba(0,0,0,0.18)',
        }}
      >
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{
            background: 'linear-gradient(135deg, var(--accent), var(--teal))',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>
            Design Report Tile
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg" style={{ color: 'rgba(255,255,255,0.85)' }}>
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto grid grid-cols-1 lg:grid-cols-5 gap-0">
          {/* Designer column */}
          <div className="lg:col-span-2 p-5 space-y-4" style={{ borderRight: '1px solid var(--border)' }}>
            <Field label="Report Name">
              <input
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. EVE Profile by Scenario"
              />
            </Field>

            <Field label="Source">
              <div className="grid grid-cols-3 gap-1 mb-2 p-1 rounded-lg" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
                {([
                  { k: 'dataset', l: 'Dataset', icon: Database, disabled: datasets.length === 0 },
                  { k: 'run', l: 'Run', icon: FlaskConical, disabled: runs.length === 0 },
                  { k: 'sample', l: 'Sample', icon: BarChart3, disabled: false },
                ] as const).map(({ k, l, icon: I, disabled }) => {
                  const active = sourceKind === k
                  return (
                    <button
                      key={k}
                      onClick={() => setSourceKind(k as SourceKind)}
                      disabled={disabled}
                      className="py-2 rounded-md text-[11px] font-semibold transition-colors flex items-center justify-center gap-1 disabled:opacity-40"
                      style={{
                        background: active ? 'var(--bg-card)' : 'transparent',
                        color: active ? 'var(--accent)' : 'var(--text-secondary)',
                        boxShadow: active ? '0 1px 4px rgba(0,0,0,0.05)' : 'none',
                      }}
                    >
                      <I size={11} /> {l}
                    </button>
                  )
                })}
              </div>
              {sourceKind === 'dataset' && (
                <select
                  className="input"
                  value={datasetId}
                  onChange={(e) => setDatasetId(e.target.value)}
                >
                  {datasets.length === 0 && <option value="">No datasets bound</option>}
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              )}
              {sourceKind === 'run' && (
                <select
                  className="input"
                  value={runId}
                  onChange={(e) => setRunId(e.target.value)}
                >
                  {runs.length === 0 && <option value="">No runs yet</option>}
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              )}
              {sourceKind === 'sample' && (
                <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  Synthetic data — useful for sketching layouts.
                </div>
              )}
            </Field>

            <Field label="Chart Type">
              <div className="grid grid-cols-3 gap-2">
                {CHART_TYPES.map(({ id, label, icon: Icon }) => {
                  const active = chartType === id
                  return (
                    <button
                      key={id}
                      onClick={() => setChartType(id)}
                      className="flex flex-col items-center gap-1 py-2 rounded-lg text-[11px] font-medium transition-all"
                      style={{
                        background: active ? 'var(--accent-light)' : 'var(--bg-elevated)',
                        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                        color: active ? 'var(--accent)' : 'var(--text-secondary)',
                      }}
                    >
                      <Icon size={14} />
                      {label}
                    </button>
                  )
                })}
              </div>
            </Field>

            <Field label="X Axis Field">
              <select className="input" value={xField} onChange={(e) => setXField(e.target.value)}>
                <option value="">Select…</option>
                {fields.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </Field>

            <Field label={`Y Axis Fields (${yFields.length} selected)`}>
              <div
                className="grid grid-cols-2 gap-1 p-2 rounded-lg"
                style={{
                  background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  maxHeight: 200, overflowY: 'auto',
                }}
              >
                {fields.length === 0 && (
                  <div className="text-xs col-span-2 py-2" style={{ color: 'var(--text-muted)' }}>
                    Pick a source to see fields
                  </div>
                )}
                {fields.filter((f) => f !== xField).map((f) => {
                  const sel = yFields.includes(f)
                  return (
                    <label
                      key={f}
                      className="flex items-center gap-2 px-2 py-1 rounded text-xs cursor-pointer"
                      style={{ background: sel ? 'var(--accent-light)' : 'transparent', color: sel ? 'var(--accent)' : 'var(--text-secondary)' }}
                    >
                      <input type="checkbox" checked={sel} onChange={() => toggleY(f)} />
                      {f}
                    </label>
                  )
                })}
              </div>
            </Field>

            <Field label="Aggregation">
              <select
                className="input"
                value={aggregation}
                onChange={(e) => setAggregation(e.target.value as PlotConfig['aggregation'])}
              >
                <option value="none">None</option>
                <option value="sum">Sum</option>
                <option value="avg">Average</option>
                <option value="count">Count</option>
                <option value="min">Min</option>
                <option value="max">Max</option>
              </select>
            </Field>

            <Field label="Description (optional)">
              <textarea
                rows={2}
                className="input resize-none"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>

            {error && (
              <div className="text-xs px-3 py-2 rounded-md" style={{ background: 'var(--error-bg)', color: 'var(--error)' }}>
                {error}
              </div>
            )}
          </div>

          {/* Live preview column */}
          <div className="lg:col-span-3 p-5 space-y-3">
            <div className="font-display text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
              Live Preview
            </div>
            <div
              className="panel"
              style={{ minHeight: 320, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              {previewSpec ? (
                <div style={{ width: '100%' }}>
                  <Chart spec={previewSpec} height={300} />
                  <div
                    className="text-[11px] mt-2 text-center"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    Sample data — actual rendering uses the source you picked when saved.
                  </div>
                </div>
              ) : (
                <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  Pick a chart type, X / Y fields to see a live preview.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-between gap-2 px-5 py-3" style={{ borderTop: '1px solid var(--border)' }}>
          <div
            className="text-[11px] flex items-center gap-1"
            style={{ color: 'var(--text-muted)' }}
          >
            <Sparkles size={11} /> Tip: pull from a Run to chart prediction paths over time.
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-2 text-xs rounded-lg" style={{ color: 'var(--text-muted)' }}>
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={!name || !xField || yFields.length === 0 || saving}
              className="px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              {saving ? 'Saving…' : 'Save Report'}
            </button>
          </div>
        </div>
      </div>

      <style>{`
        .input {
          width: 100%; padding: 8px 10px; border-radius: 8px; font-size: 13px;
          background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);
        }
      `}</style>
    </>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span
        className="block text-[11px] font-semibold uppercase tracking-widest mb-1"
        style={{ color: 'var(--text-secondary)' }}
      >
        {label}
      </span>
      {children}
    </label>
  )
}
