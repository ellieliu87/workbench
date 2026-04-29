import { useEffect, useRef, useState } from 'react'
import {
  Boxes, Upload, Plus, Trash2, X, Sparkles, Link2, Activity,
  TrendingUp, FileBox, Loader2,
} from 'lucide-react'
import api from '@/lib/api'
import { useChatStore } from '@/store/chatStore'
import type {
  TrainedModel, Dataset, ModelMetricsResponse,
} from '@/types'
import {
  ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend,
} from 'recharts'

const SOURCE_BADGE: Record<TrainedModel['source_kind'], { label: string; color: string }> = {
  regression: { label: 'BUILT IN-APP', color: '#0891B2' },
  upload:     { label: 'UPLOADED',     color: '#7C3AED' },
  uri:        { label: 'ARTIFACTORY',  color: '#D97706' },
}

const TYPE_LABEL: Record<TrainedModel['model_type'], string> = {
  ols: 'OLS Regression',
  logistic: 'Logistic Regression',
  uploaded: 'Uploaded Artifact',
  external: 'External Reference',
}

interface Props {
  functionId: string
  functionName: string
  onAskAgent: (q: string) => void
  onContextChange: (ctx: string | null) => void
}

export default function ModelsTab({ functionId, functionName, onAskAgent, onContextChange }: Props) {
  const [models, setModels] = useState<TrainedModel[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [loading, setLoading] = useState(true)
  const [activeModel, setActiveModel] = useState<TrainedModel | null>(null)
  const [buildOpen, setBuildOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uriOpen, setUriOpen] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<TrainedModel[]>(`/api/models`, { params: { function_id: functionId } }),
      api.get<Dataset[]>(`/api/datasets`, { params: { function_id: functionId } }),
    ])
      .then(([m, d]) => { setModels(m.data); setDatasets(d.data) })
      .finally(() => setLoading(false))
  }

  useEffect(load, [functionId])

  useEffect(() => {
    onContextChange(`${functionName} (Models tab): ${models.length} model${models.length === 1 ? '' : 's'} registered`)
    return () => onContextChange(null)
  }, [models.length, functionName, onContextChange])

  const remove = async (id: string) => {
    if (!confirm('Delete this model?')) return
    await api.delete(`/api/models/${id}`)
    if (activeModel?.id === id) setActiveModel(null)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div>
          <div className="font-display text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            Model Registry
          </div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {loading
              ? 'Loading…'
              : `${models.length} model${models.length === 1 ? '' : 's'}. Build OLS / logistic in-app, upload an artifact, or reference a URI in the company artifactory.`}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setUriOpen(true)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            <Link2 size={13} /> From URI
          </button>
          <button
            onClick={() => setUploadOpen(true)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            <Upload size={13} /> Upload Artifact
          </button>
          <button
            onClick={() => setBuildOpen(true)}
            disabled={datasets.length === 0}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
            style={{ background: 'var(--accent)', color: '#fff' }}
            title={datasets.length === 0 ? 'Bind a dataset first (Data tab)' : ''}
          >
            <Plus size={13} /> Build Regression
          </button>
        </div>
      </div>

      {!loading && models.length === 0 && (
        <div
          className="panel text-center"
          style={{ padding: '40px 20px', borderStyle: 'dashed' }}
        >
          <Boxes size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            No models yet
          </div>
          <div className="text-xs mt-1 mb-4" style={{ color: 'var(--text-muted)' }}>
            {datasets.length === 0
              ? 'Bind a dataset on the Data tab first, then come back to build a regression.'
              : 'Build a regression from a bound dataset, or upload / reference an existing model.'}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {models.map((m) => (
          <ModelCard
            key={m.id}
            model={m}
            datasetName={datasets.find((d) => d.id === m.dataset_id)?.name}
            onOpen={() => setActiveModel(m)}
            onDelete={() => remove(m.id)}
            onAskAgent={onAskAgent}
          />
        ))}
      </div>

      {buildOpen && (
        <BuildRegressionModal
          functionId={functionId}
          datasets={datasets}
          onClose={() => setBuildOpen(false)}
          onCreated={() => { setBuildOpen(false); load() }}
        />
      )}
      {uploadOpen && (
        <UploadModelModal
          functionId={functionId}
          onClose={() => setUploadOpen(false)}
          onCreated={() => { setUploadOpen(false); load() }}
        />
      )}
      {uriOpen && (
        <FromUriModal
          functionId={functionId}
          onClose={() => setUriOpen(false)}
          onCreated={() => { setUriOpen(false); load() }}
        />
      )}
      {activeModel && (
        <ModelDetailPanel
          model={activeModel}
          onClose={() => setActiveModel(null)}
          onAskAgent={onAskAgent}
        />
      )}
    </div>
  )
}

// ── Model card ──────────────────────────────────────────────────────────────
function ModelCard({
  model, datasetName, onOpen, onDelete, onAskAgent,
}: {
  model: TrainedModel
  datasetName?: string
  onOpen: () => void
  onDelete: () => void
  onAskAgent: (q: string) => void
}) {
  const setEntity = useChatStore((s) => s.setEntity)
  const badge = SOURCE_BADGE[model.source_kind]
  const Icon = model.source_kind === 'regression' ? Activity : model.source_kind === 'upload' ? FileBox : Link2

  // Pick the headline metric to display
  const headline = (() => {
    const m = model.train_metrics
    if (m.r2 != null) return { label: 'R²', value: m.r2.toFixed(3) }
    if (m.auc != null) return { label: 'AUC', value: m.auc.toFixed(3) }
    if (m.accuracy != null) return { label: 'ACC', value: m.accuracy.toFixed(3) }
    return { label: 'Type', value: TYPE_LABEL[model.model_type] }
  })()

  return (
    <div className="panel" style={{ padding: 14 }}>
      <div className="flex items-start gap-3 mb-2">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: `${badge.color}1A`, color: badge.color }}
        >
          <Icon size={15} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
            {model.name}
          </div>
          <div className="text-[11px] truncate" style={{ color: 'var(--text-muted)' }}>
            {TYPE_LABEL[model.model_type]}
            {datasetName ? ` · ${datasetName}` : ''}
          </div>
        </div>
      </div>

      {model.description && (
        <div className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
          {model.description}
        </div>
      )}

      <div className="flex flex-wrap gap-1 mb-2">
        <span
          className="pill"
          style={{ fontSize: 10, background: `${badge.color}1A`, color: badge.color, borderColor: 'transparent' }}
        >
          {badge.label}
        </span>
        <span className="pill" style={{ fontSize: 10 }}>
          {headline.label}: <strong style={{ marginLeft: 4 }}>{headline.value}</strong>
        </span>
        {model.feature_columns.length > 0 && (
          <span className="pill" style={{ fontSize: 10 }}>
            {model.feature_columns.length} features
          </span>
        )}
      </div>

      <div
        className="flex items-center justify-between mt-2 pt-2"
        style={{ borderTop: '1px solid var(--border-subtle)' }}
      >
        <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
          {new Date(model.created_at).toLocaleString()}
        </div>
        <div className="flex gap-1">
          <button
            onClick={() => {
              setEntity('model', model.id)
              onAskAgent(`Explain the model "${model.name}" in detail.`)
            }}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="Ask agent"
            onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--accent)')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
          >
            <Sparkles size={13} />
          </button>
          <button
            onClick={onOpen}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="Open"
            onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--accent)')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
          >
            <TrendingUp size={13} />
          </button>
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
        </div>
      </div>
    </div>
  )
}

// ── Build regression modal ──────────────────────────────────────────────────
function BuildRegressionModal({
  functionId, datasets, onClose, onCreated,
}: {
  functionId: string
  datasets: Dataset[]
  onClose: () => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [datasetId, setDatasetId] = useState(datasets[0]?.id || '')
  const [target, setTarget] = useState('')
  const [features, setFeatures] = useState<string[]>([])
  const [modelType, setModelType] = useState<'ols' | 'logistic'>('ols')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dataset = datasets.find((d) => d.id === datasetId)
  const numericCols = (dataset?.columns || []).filter(
    (c) => c.dtype.startsWith('float') || c.dtype.startsWith('int'),
  )

  const toggleFeature = (col: string) => {
    if (col === target) return
    setFeatures((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]))
  }

  const submit = async () => {
    if (!datasetId || !name || !target || features.length === 0) return
    setSaving(true)
    setError(null)
    try {
      await api.post('/api/models/build-regression', {
        function_id: functionId,
        name, description,
        dataset_id: datasetId,
        target_column: target,
        feature_columns: features,
        model_type: modelType,
      })
      onCreated()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Training failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Build a Regression" onClose={onClose} wide>
      <Field label="Model Name">
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Charge-off Driver" />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Dataset">
          <select
            className="input"
            value={datasetId}
            onChange={(e) => { setDatasetId(e.target.value); setTarget(''); setFeatures([]) }}
          >
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.columns.length} cols)
              </option>
            ))}
          </select>
        </Field>
        <Field label="Model Type">
          <div className="grid grid-cols-2 gap-2">
            {(['ols', 'logistic'] as const).map((mt) => {
              const active = modelType === mt
              return (
                <button
                  key={mt}
                  onClick={() => setModelType(mt)}
                  className="py-2 rounded-lg text-xs font-semibold transition-colors"
                  style={{
                    background: active ? 'var(--accent-light)' : 'var(--bg-elevated)',
                    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                    color: active ? 'var(--accent)' : 'var(--text-secondary)',
                  }}
                >
                  {mt === 'ols' ? 'OLS (Linear)' : 'Logistic'}
                </button>
              )
            })}
          </div>
        </Field>
      </div>

      <Field label={`Target Column ${modelType === 'logistic' ? '(numeric — split at median, or 2-class string)' : '(numeric)'}`}>
        <select className="input" value={target} onChange={(e) => setTarget(e.target.value)}>
          <option value="">Select…</option>
          {(dataset?.columns || []).map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} ({c.dtype})
            </option>
          ))}
        </select>
      </Field>

      <Field label={`Feature Columns (${features.length} selected)`}>
        <div
          className="rounded-lg p-2 grid grid-cols-2 md:grid-cols-3 gap-1"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            maxHeight: 240, overflowY: 'auto',
          }}
        >
          {(dataset?.columns || []).filter((c) => c.name !== target).map((c) => {
            const sel = features.includes(c.name)
            const numeric = c.dtype.startsWith('float') || c.dtype.startsWith('int')
            return (
              <label
                key={c.name}
                className="flex items-center gap-2 px-2 py-1 rounded text-xs cursor-pointer"
                style={{
                  background: sel ? 'var(--accent-light)' : 'transparent',
                  color: sel ? 'var(--accent)' : 'var(--text-secondary)',
                }}
                title={numeric ? '' : 'Non-numeric — will be one-hot encoded'}
              >
                <input type="checkbox" checked={sel} onChange={() => toggleFeature(c.name)} />
                <span className="font-mono truncate">{c.name}</span>
                <span className="ml-auto text-[10px] opacity-60">{c.dtype}</span>
              </label>
            )
          })}
        </div>
      </Field>

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
        disabled={!name || !target || features.length === 0 || saving}
        submitLabel={saving ? 'Training…' : 'Train Model'}
      />
    </Modal>
  )
}

// ── Upload model modal ──────────────────────────────────────────────────────
function UploadModelModal({
  functionId, onClose, onCreated,
}: {
  functionId: string
  onClose: () => void
  onCreated: () => void
}) {
  const [files, setFiles] = useState<File[]>([])
  const [names, setNames] = useState<Record<number, string>>({})
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [errors, setErrors] = useState<{ file: string; message: string }[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  const addFiles = (incoming: FileList | null) => {
    if (!incoming || incoming.length === 0) return
    const next = Array.from(incoming)
    setFiles((prev) => {
      // de-dupe by name+size
      const seen = new Set(prev.map((f) => `${f.name}-${f.size}`))
      const filtered = next.filter((f) => !seen.has(`${f.name}-${f.size}`))
      return [...prev, ...filtered]
    })
  }

  const removeAt = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
    setNames((prev) => {
      const out: Record<number, string> = {}
      Object.entries(prev).forEach(([k, v]) => {
        const ki = Number(k)
        if (ki < idx) out[ki] = v
        else if (ki > idx) out[ki - 1] = v
      })
      return out
    })
  }

  const setNameAt = (idx: number, value: string) => {
    setNames((prev) => ({ ...prev, [idx]: value }))
  }

  const totalBytes = files.reduce((s, f) => s + f.size, 0)

  const submit = async () => {
    if (files.length === 0) return
    setSaving(true)
    setErrors([])
    setProgress({ done: 0, total: files.length })
    const failures: { file: string; message: string }[] = []
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const fd = new FormData()
      fd.append('function_id', functionId)
      fd.append('file', file)
      const stem = file.name.split('.').slice(0, -1).join('.') || file.name
      const finalName = (names[i] && names[i].trim()) || stem
      fd.append('name', finalName)
      if (description) fd.append('description', description)
      try {
        await api.post('/api/models/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      } catch (e: any) {
        failures.push({
          file: file.name,
          message: e?.response?.data?.detail || 'Upload failed',
        })
      }
      setProgress({ done: i + 1, total: files.length })
    }
    setErrors(failures)
    setSaving(false)
    if (failures.length === 0) onCreated()
  }

  return (
    <Modal title="Upload Model Artifacts" onClose={onClose}>
      <Field label="Files (PKL / Joblib / ONNX / JSON, max 50 MB each — multi-select supported)">
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pkl,.pickle,.joblib,.onnx,.json"
          onChange={(e) => {
            addFiles(e.target.files)
            // reset so re-picking the same file works
            if (inputRef.current) inputRef.current.value = ''
          }}
          className="hidden"
        />
        <button
          onClick={() => inputRef.current?.click()}
          className="w-full rounded-lg py-5 text-sm transition-colors"
          style={{
            background: 'var(--bg-elevated)',
            border: `1.5px dashed ${files.length > 0 ? 'var(--accent)' : 'var(--border)'}`,
            color: files.length > 0 ? 'var(--accent)' : 'var(--text-muted)',
          }}
        >
          {files.length > 0 ? (
            <div>
              <div className="font-semibold">
                {files.length} file{files.length === 1 ? '' : 's'} selected · {(totalBytes / 1024).toFixed(1)} KB total
              </div>
              <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                Click to add more
              </div>
            </div>
          ) : (
            <>
              <Upload size={20} style={{ display: 'inline-block', marginRight: 6 }} />
              Click to choose model files (you can pick multiple)
            </>
          )}
        </button>
      </Field>

      {files.length > 0 && (
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: '1px solid var(--border)' }}
        >
          {files.map((f, i) => {
            const stem = f.name.split('.').slice(0, -1).join('.') || f.name
            return (
              <div
                key={`${f.name}-${i}`}
                className="flex items-center gap-2 px-3 py-2"
                style={{
                  background: i % 2 === 0 ? 'var(--bg-card)' : 'var(--bg-elevated)',
                  borderBottom: i < files.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                }}
              >
                <FileBox size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                <div
                  className="text-[12px] font-mono truncate min-w-0 flex-1"
                  style={{ color: 'var(--text-secondary)' }}
                  title={f.name}
                >
                  {f.name}
                </div>
                <input
                  className="input"
                  style={{ width: 200, padding: '4px 8px', fontSize: 12 }}
                  placeholder={stem}
                  value={names[i] ?? ''}
                  onChange={(e) => setNameAt(i, e.target.value)}
                  title="Override the model name (defaults to filename stem)"
                  disabled={saving}
                />
                <span
                  className="text-[10px] font-mono shrink-0"
                  style={{ color: 'var(--text-muted)', width: 60, textAlign: 'right' }}
                >
                  {(f.size / 1024).toFixed(1)} KB
                </span>
                <button
                  onClick={() => removeAt(i)}
                  disabled={saving}
                  className="p-1 rounded shrink-0"
                  style={{ color: 'var(--text-muted)' }}
                  title="Remove from list"
                >
                  <X size={12} />
                </button>
              </div>
            )
          })}
        </div>
      )}

      <Field label="Description (optional — applied to all uploaded models)">
        <input
          className="input"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={saving}
        />
      </Field>

      {progress && (
        <div
          className="rounded-md px-3 py-2 text-xs flex items-center gap-2"
          style={{
            background: 'var(--accent-light)',
            color: 'var(--accent)',
          }}
        >
          <span style={{ fontWeight: 600 }}>
            {saving ? 'Uploading…' : 'Done'}
          </span>
          <span className="font-mono">
            {progress.done} / {progress.total}
          </span>
          <div
            className="flex-1 h-1.5 rounded-full"
            style={{ background: 'var(--bg-elevated)' }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(progress.done / progress.total) * 100}%`,
                background: 'var(--accent)',
              }}
            />
          </div>
        </div>
      )}

      {errors.length > 0 && (
        <div className="text-xs px-3 py-2 rounded-md" style={{ background: 'var(--error-bg)', color: 'var(--error)' }}>
          <div className="font-semibold mb-1">{errors.length} upload{errors.length === 1 ? '' : 's'} failed:</div>
          <ul className="space-y-0.5 font-mono">
            {errors.map((e, i) => (
              <li key={i}>· <strong>{e.file}</strong> — {e.message}</li>
            ))}
          </ul>
        </div>
      )}

      <ModalFooter
        onClose={onClose}
        onSubmit={submit}
        disabled={files.length === 0 || saving}
        submitLabel={
          saving
            ? `Uploading ${progress?.done ?? 0}/${progress?.total ?? files.length}…`
            : `Register ${files.length || 'Models'}${files.length > 0 ? ` Model${files.length === 1 ? '' : 's'}` : ''}`
        }
      />
    </Modal>
  )
}

// ── From URI modal ──────────────────────────────────────────────────────────
function FromUriModal({
  functionId, onClose, onCreated,
}: {
  functionId: string
  onClose: () => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [uri, setUri] = useState('artifactory://')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    setSaving(true)
    setError(null)
    try {
      await api.post('/api/models/from-uri', {
        function_id: functionId, name, description,
        artifactory_uri: uri, model_type: 'external',
      })
      onCreated()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Reference an Artifactory Model" onClose={onClose}>
      <Field label="Model name">
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Artifactory URI">
        <input
          className="input font-mono"
          value={uri}
          onChange={(e) => setUri(e.target.value)}
          placeholder="artifactory://prod/credit/pd/v4.pkl"
        />
      </Field>
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
        disabled={!name || !uri || saving}
        submitLabel={saving ? 'Saving…' : 'Register Reference'}
      />
    </Modal>
  )
}

// ── Detail panel ────────────────────────────────────────────────────────────
function ModelDetailPanel({
  model, onClose, onAskAgent,
}: {
  model: TrainedModel
  onClose: () => void
  onAskAgent: (q: string) => void
}) {
  const [metrics, setMetrics] = useState<ModelMetricsResponse | null>(null)

  useEffect(() => {
    api.get<ModelMetricsResponse>(`/api/models/${model.id}/metrics`).then((r) => setMetrics(r.data))
  }, [model.id])

  const coefEntries = Object.entries(model.coefficients || {})
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))

  const monitoringSeries = (() => {
    if (!metrics) return []
    const dates = new Set<string>()
    Object.values(metrics.series).forEach((s) => s.forEach((p) => dates.add(p.asof)))
    const sortedDates = Array.from(dates).sort()
    return sortedDates.map((d) => {
      const row: Record<string, any> = { asof: d.slice(5) }
      Object.entries(metrics.series).forEach(([k, s]) => {
        const point = s.find((p) => p.asof === d)
        if (point) row[k] = point.value
      })
      return row
    })
  })()

  const seriesNames = metrics ? Object.keys(metrics.series) : []
  const COLORS = ['#004977', '#059669', '#D97706', '#DC2626']

  return (
    <>
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(11,15,25,0.45)' }}
        onClick={onClose}
      />
      <div
        className="fixed top-0 bottom-0 z-50 flex flex-col"
        style={{
          // Fill the right pane by anchoring BOTH edges: left at the
          // sidebar's right edge (240px) and right at the viewport edge.
          // Using `width: calc(100vw - 240px)` was wrong because `100vw`
          // includes the scrollbar in Chrome/Firefox, which pushed the
          // drawer's left edge ~16px behind the sidebar.
          left: 240,
          right: 0,
          background: 'var(--bg-card)',
          borderLeft: '1px solid var(--border)',
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
            <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>
              {model.name}
            </div>
            <div className="font-mono" style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
              {TYPE_LABEL[model.model_type]} · {model.id}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg" style={{ color: 'rgba(255,255,255,0.85)' }}>
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Train metrics */}
          <div>
            <div className="section-title">Train Metrics</div>
            <div className="grid grid-cols-3 gap-2">
              {Object.entries(model.train_metrics).map(([k, v]) => (
                <div key={k} className="panel" style={{ padding: 12 }}>
                  <div className="metric-label">{k.toUpperCase()}</div>
                  <div className="metric-value mt-1" style={{ fontSize: 18 }}>
                    {typeof v === 'number' ? (v < 1 ? v.toFixed(4) : v.toLocaleString()) : v}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Coefficients (regression only) */}
          {coefEntries.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="section-title" style={{ marginBottom: 0 }}>
                  Coefficients ({coefEntries.length})
                </div>
                <button
                  onClick={() => onAskAgent(`Interpret the coefficients of the ${model.name} model.`)}
                  className="text-[11px] flex items-center gap-1"
                  style={{ color: 'var(--accent)', fontWeight: 600 }}
                >
                  <Sparkles size={11} /> Interpret
                </button>
              </div>
              <div
                className="rounded-lg overflow-hidden"
                style={{ border: '1px solid var(--border)' }}
              >
                <table className="w-full text-xs font-mono">
                  <thead style={{ background: 'var(--bg-elevated)' }}>
                    <tr>
                      <th className="text-left py-2 px-3" style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                        Feature
                      </th>
                      <th className="text-right py-2 px-3" style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                        Coefficient
                      </th>
                      <th className="py-2 px-3" style={{ width: 200 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const maxAbs = Math.max(...coefEntries.map(([, v]) => Math.abs(v))) || 1
                      return coefEntries.map(([k, v]) => {
                        const positive = v >= 0
                        const pct = (Math.abs(v) / maxAbs) * 100
                        return (
                          <tr key={k}>
                            <td className="py-1.5 px-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>{k}</td>
                            <td className="py-1.5 px-3 text-right" style={{
                              color: positive ? 'var(--success)' : 'var(--error)',
                              borderBottom: '1px solid var(--border-subtle)',
                              fontWeight: 600,
                            }}>
                              {v >= 0 ? '+' : ''}{v.toFixed(4)}
                            </td>
                            <td className="py-1.5 px-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: positive ? 'flex-start' : 'flex-end' }}>
                                <div style={{
                                  width: `${pct}%`, height: 4, borderRadius: 2,
                                  background: positive ? 'var(--success)' : 'var(--error)',
                                }} />
                              </div>
                            </td>
                          </tr>
                        )
                      })
                    })()}
                    {model.intercept != null && (
                      <tr style={{ background: 'var(--bg-elevated)' }}>
                        <td className="py-1.5 px-3" style={{ fontStyle: 'italic' }}>intercept</td>
                        <td className="py-1.5 px-3 text-right" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                          {model.intercept.toFixed(4)}
                        </td>
                        <td></td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Monitoring chart */}
          {monitoringSeries.length > 0 && (
            <div>
              <div className="section-title">Performance Monitoring (12-week)</div>
              <div className="panel" style={{ padding: 14 }}>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={monitoringSeries} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                    <XAxis dataKey="asof" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--bg-card)', border: '1px solid var(--border)',
                        borderRadius: 8, fontSize: 11, fontFamily: 'JetBrains Mono, monospace',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {seriesNames.map((s, i) => (
                      <Line
                        key={s}
                        type="monotone"
                        dataKey={s}
                        stroke={COLORS[i % COLORS.length]}
                        strokeWidth={2}
                        dot={{ r: 2.5 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Source details */}
          <div>
            <div className="section-title">Source</div>
            <div className="panel" style={{ padding: 14 }}>
              <table className="w-full text-xs">
                <tbody>
                  <Row k="Source kind" v={model.source_kind} />
                  <Row k="Model type" v={TYPE_LABEL[model.model_type]} />
                  {model.target_column && <Row k="Target" v={model.target_column} />}
                  {model.feature_columns.length > 0 && (
                    <Row k="Features" v={model.feature_columns.join(', ')} />
                  )}
                  {model.dataset_id && <Row k="Dataset" v={model.dataset_id} />}
                  {model.artifact_path && <Row k="Artifact path" v={model.artifact_path} />}
                  {model.artifactory_uri && <Row k="Artifactory URI" v={model.artifactory_uri} />}
                  <Row k="Created" v={new Date(model.created_at).toLocaleString()} />
                </tbody>
              </table>
            </div>
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

function Row({ k, v }: { k: string; v: string }) {
  return (
    <tr>
      <td className="py-1.5 pr-3" style={{ color: 'var(--text-muted)', width: 130, whiteSpace: 'nowrap' }}>
        {k}
      </td>
      <td className="py-1.5 font-mono" style={{ color: 'var(--text-primary)', wordBreak: 'break-all' }}>
        {v}
      </td>
    </tr>
  )
}

// ── shared modal chrome ─────────────────────────────────────────────────────
function Modal({
  title, onClose, children, wide,
}: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(11,15,25,0.45)' }} onClick={onClose} />
      <div
        className="fixed top-1/2 left-1/2 z-50 flex flex-col"
        style={{
          width: wide ? 'min(720px, 96vw)' : 'min(560px, 96vw)',
          // Take nearly the whole viewport height — a small 8px breathing
          // margin top + bottom (effectively 96vh tall) so feature
          // checklists and metric tables don't have to scroll inside the
          // already-scrollable body.
          maxHeight: 'calc(100vh - 16px)',
          transform: 'translate(-50%, -50%)',
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          boxShadow: '0 24px 64px rgba(0,0,0,0.20)',
        }}
      >
        <div
          className="flex items-center justify-between px-5 py-3.5"
          style={{
            background: 'linear-gradient(135deg, var(--accent), var(--teal))',
            borderTopLeftRadius: 11,
            borderTopRightRadius: 11,
          }}
        >
          <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>
            {title}
          </div>
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
