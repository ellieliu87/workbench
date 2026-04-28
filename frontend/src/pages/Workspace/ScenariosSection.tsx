import { useEffect, useState } from 'react'
import {
  Plus, X, Sparkles, Trash2, Eye, Loader2,
} from 'lucide-react'
import api from '@/lib/api'
import type { Scenario, Dataset } from '@/types'
import { useChatStore } from '@/store/chatStore'
import {
  ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend,
} from 'recharts'

const SEVERITY_COLOR: Record<Scenario['severity'], string> = {
  base: '#059669',
  outlook: '#0891B2',
  adverse: '#D97706',
  severely_adverse: '#DC2626',
  custom: '#7C3AED',
}

const SEVERITY_LABEL: Record<Scenario['severity'], string> = {
  base: 'BASE',
  outlook: 'OUTLOOK',
  adverse: 'ADVERSE',
  severely_adverse: 'SEVERE',
  custom: 'CUSTOM',
}

interface Props {
  functionId: string
  functionName: string
  onAskAgent: (q: string) => void
}

export default function ScenariosSection({ functionId, functionName, onAskAgent }: Props) {
  const setEntity = useChatStore((s) => s.setEntity)
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [loading, setLoading] = useState(true)
  const [previewFor, setPreviewFor] = useState<Scenario | null>(null)
  const [bindOpen, setBindOpen] = useState(false)

  // Scenarios route to the macro-economist agent. We tag the chat context
  // with the scenario entity before dispatching so the backend's _route()
  // sees entity_kind="scenario" and skips the dataset/quality fallbacks.
  const explainScenario = (s: Scenario) => {
    setEntity('scenario', s.id)
    onAskAgent(
      `Explain the macro narrative in the "${s.name}" scenario — ` +
      `regime, rate path, credit/spreads, real economy, and key tail risks. ` +
      `Focus on the scenario story, not column-level commentary.`
    )
  }

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<Scenario[]>(`/api/analytics/scenarios`, { params: { function_id: functionId } }),
      api.get<Dataset[]>(`/api/datasets`, { params: { function_id: functionId } }),
    ])
      .then(([s, d]) => { setScenarios(s.data); setDatasets(d.data) })
      .finally(() => setLoading(false))
  }

  useEffect(load, [functionId])

  const remove = async (id: string) => {
    if (!confirm('Delete this scenario?')) return
    try {
      await api.delete(`/api/analytics/scenarios/${id}`)
      load()
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Could not delete')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {loading
              ? 'Loading…'
              : `${scenarios.length} scenario${scenarios.length === 1 ? '' : 's'} (incl. CCAR built-ins). Used as inputs in the Analytics tab.`}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onAskAgent(`What scenarios do I have for ${functionName}? When should I use each?`)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            <Sparkles size={13} /> Ask Agent
          </button>
          <button
            onClick={() => setBindOpen(true)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            <Plus size={13} /> Add Scenario
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {scenarios.map((s) => (
          <ScenarioCard
            key={s.id}
            scenario={s}
            onPreview={() => setPreviewFor(s)}
            onDelete={s.source_kind === 'builtin' ? undefined : () => remove(s.id)}
            onAskAgent={() => explainScenario(s)}
          />
        ))}
      </div>

      {bindOpen && (
        <AddScenarioModal
          functionId={functionId}
          datasets={datasets}
          onClose={() => setBindOpen(false)}
          onCreated={() => { setBindOpen(false); load() }}
        />
      )}
      {previewFor && (
        <ScenarioPreviewPanel scenario={previewFor} onClose={() => setPreviewFor(null)} />
      )}
    </div>
  )
}

// ── Scenario card ──────────────────────────────────────────────────────────
function ScenarioCard({
  scenario, onPreview, onDelete, onAskAgent,
}: {
  scenario: Scenario
  onPreview: () => void
  onDelete?: () => void
  onAskAgent: () => void
}) {
  const color = SEVERITY_COLOR[scenario.severity]
  const isBuiltin = scenario.source_kind === 'builtin'
  return (
    <div className="panel" style={{ padding: 14 }}>
      <div className="flex items-start gap-2 mb-2">
        <div
          className="w-2.5 self-stretch rounded-sm shrink-0"
          style={{ background: color, marginTop: 2, marginBottom: 2 }}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-0.5">
            <div className="font-semibold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
              {scenario.name}
            </div>
            <span
              className="pill shrink-0"
              style={{
                fontSize: 9, background: `${color}1A`, color, borderColor: 'transparent',
                padding: '1px 6px',
              }}
            >
              {SEVERITY_LABEL[scenario.severity]}
            </span>
          </div>
          {scenario.description && (
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {scenario.description}
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-1 mb-2">
        <span className="pill" style={{ fontSize: 10 }}>
          {scenario.variables.length} vars
        </span>
        {scenario.horizon_months && (
          <span className="pill" style={{ fontSize: 10 }}>
            {scenario.horizon_months}m horizon
          </span>
        )}
        {isBuiltin && <span className="pill" style={{ fontSize: 10 }}>BUILT-IN</span>}
      </div>

      <div
        className="flex items-center justify-between mt-2 pt-2"
        style={{ borderTop: '1px solid var(--border-subtle)' }}
      >
        <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
          {new Date(scenario.created_at).toLocaleDateString()}
        </div>
        <div className="flex gap-1">
          <button
            onClick={onAskAgent}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="Explain macro narrative"
            onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--accent)')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
          >
            <Sparkles size={13} />
          </button>
          <button
            onClick={onPreview}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="Preview"
            onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--accent)')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
          >
            <Eye size={13} />
          </button>
          {onDelete && (
            <button
              onClick={onDelete}
              className="p-1.5 rounded-md transition-colors"
              style={{ color: 'var(--text-muted)' }}
              title="Delete"
              onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--error)')}
              onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Add scenario modal ─────────────────────────────────────────────────────
function AddScenarioModal({
  functionId, datasets, onClose, onCreated,
}: {
  functionId: string
  datasets: Dataset[]
  onClose: () => void
  onCreated: () => void
}) {
  const [mode, setMode] = useState<'dataset' | 'upload'>('dataset')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState<Scenario['severity']>('custom')
  const [datasetId, setDatasetId] = useState(datasets[0]?.id || '')
  const [file, setFile] = useState<File | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    setSaving(true)
    setError(null)
    try {
      let usedDatasetId = datasetId
      if (mode === 'upload' && file) {
        const fd = new FormData()
        fd.append('function_id', functionId)
        fd.append('file', file)
        if (name) fd.append('name', name)
        const r = await api.post<Dataset>('/api/datasets/upload', fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        usedDatasetId = r.data.id
      }
      if (!usedDatasetId) {
        setError('Pick a dataset or upload a file.')
        setSaving(false)
        return
      }
      await api.post('/api/analytics/scenarios/from-dataset', {
        function_id: functionId,
        name, description, severity,
        dataset_id: usedDatasetId,
      })
      onCreated()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to add scenario')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Add Scenario" onClose={onClose}>
      <div
        className="grid grid-cols-2 gap-1 p-1 rounded-lg"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
      >
        {(['dataset', 'upload'] as const).map((m) => {
          const active = mode === m
          return (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="py-2 rounded-md text-xs font-semibold transition-colors"
              style={{
                background: active ? 'var(--bg-card)' : 'transparent',
                color: active ? 'var(--accent)' : 'var(--text-secondary)',
                boxShadow: active ? '0 1px 4px rgba(0,0,0,0.05)' : 'none',
              }}
            >
              {m === 'dataset' ? 'From Bound Dataset' : 'Upload File'}
            </button>
          )
        })}
      </div>

      {mode === 'dataset' ? (
        <Field label="Bound Dataset (use the Datasets section to bind one from Snowflake / OneLake)">
          <select className="input" value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            {datasets.length === 0 && <option value="">No datasets yet</option>}
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.source_kind === 'upload' ? 'upload' : 'sql'})
              </option>
            ))}
          </select>
        </Field>
      ) : (
        <Field label="Scenario File (CSV / Parquet / XLSX / JSON)">
          <input
            type="file"
            accept=".csv,.parquet,.xlsx,.xls,.json"
            onChange={(e) => {
              const f = e.target.files?.[0] || null
              setFile(f)
              if (f && !name) setName(f.name.split('.').slice(0, -1).join('.') || f.name)
            }}
            className="input"
            style={{ padding: 6 }}
          />
          {file && (
            <div className="text-[11px] mt-1" style={{ color: 'var(--text-muted)' }}>
              {file.name} · {(file.size / 1024).toFixed(1)} KB
            </div>
          )}
        </Field>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Scenario name">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Severity">
          <select
            className="input"
            value={severity}
            onChange={(e) => setSeverity(e.target.value as Scenario['severity'])}
          >
            <option value="base">Base</option>
            <option value="adverse">Adverse</option>
            <option value="severely_adverse">Severely Adverse</option>
            <option value="outlook">Outlook</option>
            <option value="custom">Custom</option>
          </select>
        </Field>
      </div>

      <Field label="Description (optional)">
        <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>

      {error && (
        <div className="text-xs px-3 py-2 rounded-md" style={{ background: 'var(--error-bg)', color: 'var(--error)' }}>
          {error}
        </div>
      )}

      <ModalFooter
        onClose={onClose}
        onSubmit={submit}
        disabled={!name || (mode === 'dataset' ? !datasetId : !file) || saving}
        submitLabel={saving ? 'Adding…' : 'Add Scenario'}
      />
    </Modal>
  )
}

// ── Preview side panel ────────────────────────────────────────────────────
function ScenarioPreviewPanel({
  scenario, onClose,
}: { scenario: Scenario; onClose: () => void }) {
  const [data, setData] = useState<{ columns: string[]; rows: Record<string, any>[] } | null>(null)

  useEffect(() => {
    api.get(`/api/analytics/scenarios/${scenario.id}/preview`).then((r) => setData(r.data))
  }, [scenario.id])

  const numericCols = (data?.columns || []).filter((c) => {
    return c !== 'month' && data?.rows.some((r) => typeof r[c] === 'number')
  })
  const COLORS = ['#004977', '#059669', '#D97706', '#DC2626', '#7C3AED', '#0891B2']

  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(11,15,25,0.45)' }} onClick={onClose} />
      <div
        className="fixed top-0 right-0 bottom-0 z-50 flex flex-col"
        style={{
          width: 'min(880px, 96vw)',
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
          <div>
            <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>{scenario.name}</div>
            <div className="font-mono" style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
              {SEVERITY_LABEL[scenario.severity]} · {scenario.variables.length} variables
              {scenario.horizon_months ? ` · ${scenario.horizon_months}m horizon` : ''}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg" style={{ color: 'rgba(255,255,255,0.85)' }}>
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {!data ? (
            <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
              <Loader2 size={12} className="animate-spin" /> Loading…
            </div>
          ) : (
            <>
              {numericCols.length > 0 && (
                <div className="panel" style={{ padding: 14 }}>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={data.rows} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                      <XAxis dataKey={data.columns[0]} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                      <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                      <Tooltip contentStyle={{
                        background: 'var(--bg-card)', border: '1px solid var(--border)',
                        borderRadius: 8, fontSize: 11, fontFamily: 'JetBrains Mono, monospace',
                      }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {numericCols.slice(0, 6).map((c, i) => (
                        <Line key={c} type="monotone" dataKey={c} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 2 }} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div>
                <div className="section-title">Path data ({data.rows.length} rows)</div>
                <div
                  className="overflow-auto rounded-lg"
                  style={{ border: '1px solid var(--border)', maxHeight: 360 }}
                >
                  <table className="w-full text-xs font-mono">
                    <thead style={{ background: 'var(--bg-elevated)', position: 'sticky', top: 0 }}>
                      <tr>
                        {data.columns.map((c) => (
                          <th key={c} className="text-left py-2 px-3 whitespace-nowrap" style={{
                            fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                            textTransform: 'uppercase', color: 'var(--text-secondary)',
                            borderBottom: '1px solid var(--border)',
                          }}>
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.rows.map((row, i) => (
                        <tr key={i}>
                          {data.columns.map((c) => (
                            <td key={c} className="py-1.5 px-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
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

// ── shared modal chrome ───────────────────────────────────────────────────
function Modal({
  title, onClose, children,
}: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(11,15,25,0.45)' }} onClick={onClose} />
      <div
        className="fixed top-1/2 left-1/2 z-50 flex flex-col"
        style={{
          width: 'min(640px, 96vw)', maxHeight: '90vh',
          transform: 'translate(-50%, -50%)',
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 12, boxShadow: '0 24px 64px rgba(0,0,0,0.20)',
        }}
      >
        <div
          className="flex items-center justify-between px-5 py-3.5"
          style={{
            background: 'linear-gradient(135deg, var(--accent), var(--teal))',
            borderTopLeftRadius: 11, borderTopRightRadius: 11,
          }}
        >
          <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>{title}</div>
          <button onClick={onClose} className="p-1.5 rounded-lg" style={{ color: 'rgba(255,255,255,0.85)' }}>
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">{children}</div>
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

function ModalFooter({
  onClose, onSubmit, disabled, submitLabel,
}: {
  onClose: () => void
  onSubmit: () => void
  disabled?: boolean
  submitLabel: string
}) {
  return (
    <div className="flex justify-end gap-2 pt-2">
      <button onClick={onClose} className="px-3 py-2 text-xs rounded-lg" style={{ color: 'var(--text-muted)' }}>
        Cancel
      </button>
      <button
        onClick={onSubmit}
        disabled={disabled}
        className="px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
        style={{ background: 'var(--accent)', color: '#fff' }}
      >
        {submitLabel}
      </button>
    </div>
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
