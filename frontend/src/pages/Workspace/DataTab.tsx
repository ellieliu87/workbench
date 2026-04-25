import { useEffect, useRef, useState } from 'react'
import {
  Database, FileText, Trash2, Upload, Plus, X, Search,
  Snowflake, Cloud, HardDrive, Globe, Eye, Sparkles, Loader2,
  FlaskConical,
} from 'lucide-react'
import api from '@/lib/api'
import type {
  Dataset, DatasetPreview, DataSource, DataSourceTable,
} from '@/types'
import ScenariosSection from './ScenariosSection'

type SectionId = 'datasets' | 'scenarios'

interface Props {
  functionId: string
  functionName: string
  onAskAgent: (q: string) => void
  onContextChange: (ctx: string | null) => void
}

export default function DataTab({ functionId, functionName, onAskAgent, onContextChange }: Props) {
  const [section, setSection] = useState<SectionId>('datasets')
  const [counts, setCounts] = useState<{ datasets: number; scenarios: number }>({ datasets: 0, scenarios: 0 })

  // Lightweight count fetch so the toggle pills stay accurate
  useEffect(() => {
    Promise.all([
      api.get(`/api/datasets`, { params: { function_id: functionId } }),
      api.get(`/api/analytics/scenarios`, { params: { function_id: functionId } }),
    ])
      .then(([d, s]) => setCounts({ datasets: d.data.length, scenarios: s.data.length }))
      .catch(() => {})
  }, [functionId, section])

  useEffect(() => {
    onContextChange(`${functionName} (Data tab · ${section}): ${counts.datasets} datasets, ${counts.scenarios} scenarios`)
    return () => onContextChange(null)
  }, [section, counts, functionName, onContextChange])

  return (
    <div>
      {/* Section toggle */}
      <div
        className="inline-flex p-1 rounded-lg mb-5"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
      >
        {([
          { id: 'datasets',  label: 'Datasets',  icon: Database,      count: counts.datasets },
          { id: 'scenarios', label: 'Scenarios', icon: FlaskConical,  count: counts.scenarios },
        ] as const).map(({ id, label, icon: Icon, count }) => {
          const active = section === id
          return (
            <button
              key={id}
              onClick={() => setSection(id as SectionId)}
              className="px-3.5 py-1.5 rounded-md text-xs font-semibold transition-colors flex items-center gap-1.5"
              style={{
                background: active ? 'var(--bg-card)' : 'transparent',
                color: active ? 'var(--accent)' : 'var(--text-secondary)',
                boxShadow: active ? '0 1px 4px rgba(0,0,0,0.06)' : 'none',
              }}
            >
              <Icon size={13} />
              {label}
              <span
                className="rounded-full px-1.5 py-0.5"
                style={{
                  fontSize: 10, fontWeight: 700,
                  background: active ? 'var(--accent-light)' : 'var(--bg-elevated)',
                  color: active ? 'var(--accent)' : 'var(--text-muted)',
                  marginLeft: 2,
                }}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {section === 'datasets' && (
        <DatasetsSection
          functionId={functionId}
          functionName={functionName}
          onAskAgent={onAskAgent}
        />
      )}
      {section === 'scenarios' && (
        <ScenariosSection
          functionId={functionId}
          functionName={functionName}
          onAskAgent={onAskAgent}
        />
      )}
    </div>
  )
}

const SOURCE_TYPE_META: Record<DataSource['type'], { icon: any; color: string }> = {
  snowflake:   { icon: Snowflake, color: '#29B5E8' },
  onelake:     { icon: Cloud,     color: '#0078D4' },
  postgres:    { icon: Database,  color: '#336791' },
  s3:          { icon: HardDrive, color: '#D97706' },
  rest_api:    { icon: Globe,     color: '#059669' },
  file_upload: { icon: FileText,  color: '#7C3AED' },
}

const FORMAT_LABEL: Record<string, string> = {
  csv: 'CSV', parquet: 'Parquet', xlsx: 'XLSX', xls: 'XLS', json: 'JSON',
}

interface SectionProps {
  functionId: string
  functionName: string
  onAskAgent: (q: string) => void
}

function DatasetsSection({ functionId, functionName, onAskAgent }: SectionProps) {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [sources, setSources] = useState<DataSource[]>([])
  const [loading, setLoading] = useState(true)
  const [previewFor, setPreviewFor] = useState<Dataset | null>(null)
  const [bindOpen, setBindOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<Dataset[]>(`/api/datasets`, { params: { function_id: functionId } }),
      api.get<DataSource[]>(`/api/datasources`),
    ])
      .then(([d, s]) => { setDatasets(d.data); setSources(s.data) })
      .finally(() => setLoading(false))
  }

  useEffect(load, [functionId])

  const remove = async (id: string) => {
    if (!confirm('Delete this dataset?')) return
    await api.delete(`/api/datasets/${id}`)
    if (previewFor?.id === id) setPreviewFor(null)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div>
          <div
            className="font-display text-base font-semibold"
            style={{ color: 'var(--text-primary)' }}
          >
            Bound Datasets
          </div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {loading
              ? 'Loading…'
              : `${datasets.length} dataset${datasets.length === 1 ? '' : 's'} available to ${functionName}'s models, analytics, and reports.`}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onAskAgent(`What datasets do I have for ${functionName}? Suggest analyses I could run.`)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
            }}
          >
            <Sparkles size={13} /> Ask Agent
          </button>
          <button
            onClick={() => setUploadOpen(true)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              color: 'var(--text-secondary)',
            }}
          >
            <Upload size={13} /> Upload File
          </button>
          <button
            onClick={() => setBindOpen(true)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            <Plus size={13} /> Bind Table
          </button>
        </div>
      </div>

      {datasets.length === 0 && !loading && (
        <div
          className="panel text-center"
          style={{ padding: '40px 20px', borderStyle: 'dashed' }}
        >
          <Database size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            No datasets yet
          </div>
          <div className="text-xs mt-1 mb-4" style={{ color: 'var(--text-muted)' }}>
            Bind a table from a connected source, or upload a CSV / Parquet / XLSX / JSON file.
          </div>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => setBindOpen(true)}
              className="px-3 py-2 rounded-lg text-xs font-semibold"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              Bind Table
            </button>
            <button
              onClick={() => setUploadOpen(true)}
              className="px-3 py-2 rounded-lg text-xs font-semibold"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            >
              Upload File
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {datasets.map((d) => (
          <DatasetCard
            key={d.id}
            dataset={d}
            sourceName={sources.find((s) => s.id === d.data_source_id)?.name}
            onPreview={() => setPreviewFor(d)}
            onDelete={() => remove(d.id)}
            onAskAgent={onAskAgent}
          />
        ))}
      </div>

      {bindOpen && (
        <BindTableModal
          functionId={functionId}
          sources={sources}
          onClose={() => setBindOpen(false)}
          onCreated={() => { setBindOpen(false); load() }}
        />
      )}
      {uploadOpen && (
        <UploadFileModal
          functionId={functionId}
          onClose={() => setUploadOpen(false)}
          onCreated={() => { setUploadOpen(false); load() }}
        />
      )}
      {previewFor && (
        <PreviewPanel
          dataset={previewFor}
          onClose={() => setPreviewFor(null)}
          onAskAgent={onAskAgent}
        />
      )}
    </div>
  )
}

// ── Dataset card ───────────────────────────────────────────────────────────
function DatasetCard({
  dataset, sourceName, onPreview, onDelete, onAskAgent,
}: {
  dataset: Dataset
  sourceName?: string
  onPreview: () => void
  onDelete: () => void
  onAskAgent: (q: string) => void
}) {
  const isUpload = dataset.source_kind === 'upload'
  const meta = isUpload ? SOURCE_TYPE_META.file_upload : SOURCE_TYPE_META.snowflake
  const Icon = meta.icon

  return (
    <div className="panel" style={{ padding: 14 }}>
      <div className="flex items-start gap-3 mb-2">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: `${meta.color}1A`, color: meta.color }}
        >
          <Icon size={15} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
            {dataset.name}
          </div>
          <div
            className="text-[11px] truncate font-mono"
            style={{ color: 'var(--text-muted)' }}
            title={isUpload ? dataset.file_path || '' : dataset.table_ref || ''}
          >
            {isUpload
              ? `${FORMAT_LABEL[dataset.file_format || ''] || dataset.file_format} · ${formatBytes(dataset.size_bytes)}`
              : `${sourceName || dataset.data_source_id} · ${dataset.table_ref}`}
          </div>
        </div>
      </div>
      {dataset.description && (
        <div className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
          {dataset.description}
        </div>
      )}

      <div className="flex flex-wrap gap-1 mb-2">
        <span className="pill" style={{ fontSize: 10 }}>
          {dataset.columns.length} cols
        </span>
        {dataset.row_count != null && (
          <span className="pill" style={{ fontSize: 10 }}>
            {dataset.row_count.toLocaleString()} rows
          </span>
        )}
        <span
          className="pill"
          style={{
            fontSize: 10,
            background: isUpload ? 'rgba(124,58,237,0.10)' : 'rgba(41,181,232,0.10)',
            color: isUpload ? '#7C3AED' : '#0078D4',
            borderColor: 'transparent',
          }}
        >
          {isUpload ? 'UPLOAD' : 'SQL TABLE'}
        </span>
      </div>

      <div
        className="flex items-center justify-between mt-2 pt-2"
        style={{ borderTop: '1px solid var(--border-subtle)' }}
      >
        <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
          {dataset.last_synced ? `Synced ${new Date(dataset.last_synced).toLocaleString()}` : ''}
        </div>
        <div className="flex gap-1">
          <button
            onClick={() => onAskAgent(`Tell me about the dataset "${dataset.name}" (${dataset.columns.length} columns).`)}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="Ask agent"
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

// ── Bind-from-table modal ──────────────────────────────────────────────────
function BindTableModal({
  functionId, sources, onClose, onCreated,
}: {
  functionId: string
  sources: DataSource[]
  onClose: () => void
  onCreated: () => void
}) {
  const connected = sources.filter((s) => s.status === 'connected' && s.type !== 'file_upload')
  const [sourceId, setSourceId] = useState<string>(connected[0]?.id || '')
  const [tables, setTables] = useState<DataSourceTable[]>([])
  const [tableRef, setTableRef] = useState<string>('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [filter, setFilter] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sourceId) return
    setTables([])
    setTableRef('')
    api
      .get<{ source_id: string; tables: DataSourceTable[] }>(`/api/datasources/${sourceId}/tables`)
      .then((r) => setTables(r.data.tables))
      .catch(() => setTables([]))
  }, [sourceId])

  useEffect(() => {
    if (tableRef && !name) {
      setName(tableRef.split('.').pop() || tableRef)
    }
  }, [tableRef]) // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = tables.filter((t) => t.ref.toLowerCase().includes(filter.toLowerCase()))
  const selectedTable = tables.find((t) => t.ref === tableRef)

  const submit = async () => {
    if (!sourceId || !tableRef || !name) return
    setSaving(true)
    setError(null)
    try {
      await api.post('/api/datasets/from-table', {
        function_id: functionId,
        name, description,
        data_source_id: sourceId,
        table_ref: tableRef,
      })
      onCreated()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to bind table')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Bind a Table as Dataset" onClose={onClose}>
      <Field label="Data Source">
        <select
          value={sourceId}
          onChange={(e) => setSourceId(e.target.value)}
          className="input"
        >
          {connected.length === 0 && <option value="">No connected sources</option>}
          {connected.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </Field>

      <Field label={`Table (${tables.length} available)`}>
        <div className="relative mb-2">
          <Search
            size={12}
            className="absolute left-2.5 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--text-muted)' }}
          />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter tables…"
            className="input"
            style={{ paddingLeft: 28 }}
          />
        </div>
        <div
          className="rounded-lg p-1 space-y-0.5"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            maxHeight: 220,
            overflowY: 'auto',
          }}
        >
          {filtered.length === 0 && (
            <div className="text-xs px-2 py-3" style={{ color: 'var(--text-muted)' }}>
              No tables match.
            </div>
          )}
          {filtered.map((t) => {
            const sel = t.ref === tableRef
            return (
              <button
                key={t.ref}
                onClick={() => setTableRef(t.ref)}
                className="w-full text-left px-2 py-1.5 rounded-md transition-colors"
                style={{
                  background: sel ? 'var(--accent-light)' : 'transparent',
                  color: sel ? 'var(--accent)' : 'var(--text-primary)',
                }}
              >
                <div className="font-mono text-xs font-semibold">{t.ref}</div>
                <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {t.columns.length} columns: {t.columns.slice(0, 4).map((c) => c.name).join(', ')}
                  {t.columns.length > 4 ? '…' : ''}
                </div>
              </button>
            )
          })}
        </div>
      </Field>

      {selectedTable && (
        <Field label="Schema preview">
          <div
            className="rounded-lg p-2 font-mono"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              fontSize: 11,
              maxHeight: 140,
              overflowY: 'auto',
            }}
          >
            {selectedTable.columns.map((c) => (
              <div key={c.name} className="flex justify-between">
                <span style={{ color: 'var(--text-primary)' }}>{c.name}</span>
                <span style={{ color: 'var(--text-muted)' }}>{c.dtype}</span>
              </div>
            ))}
          </div>
        </Field>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Dataset name">
          <input value={name} onChange={(e) => setName(e.target.value)} className="input" />
        </Field>
        <Field label="Description (optional)">
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input"
          />
        </Field>
      </div>

      {error && (
        <div className="text-xs px-3 py-2 rounded-md" style={{ background: 'var(--error-bg)', color: 'var(--error)' }}>
          {error}
        </div>
      )}

      <ModalFooter
        onClose={onClose}
        onSubmit={submit}
        disabled={!sourceId || !tableRef || !name || saving}
        submitLabel={saving ? 'Binding…' : 'Bind Dataset'}
      />
    </Modal>
  )
}

// ── Upload-file modal ──────────────────────────────────────────────────────
function UploadFileModal({
  functionId, onClose, onCreated,
}: {
  functionId: string
  onClose: () => void
  onCreated: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const onFile = (f: File | null) => {
    setFile(f)
    if (f && !name) setName(f.name.split('.').slice(0, -1).join('.') || f.name)
  }

  const submit = async () => {
    if (!file) return
    setSaving(true)
    setError(null)
    const fd = new FormData()
    fd.append('function_id', functionId)
    fd.append('file', file)
    if (name) fd.append('name', name)
    if (description) fd.append('description', description)
    try {
      await api.post('/api/datasets/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      onCreated()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Upload failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Upload Dataset File" onClose={onClose}>
      <Field label="File (CSV / Parquet / XLSX / JSON, max 50 MB)">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.parquet,.xlsx,.xls,.json"
          onChange={(e) => onFile(e.target.files?.[0] || null)}
          className="hidden"
        />
        <button
          onClick={() => inputRef.current?.click()}
          className="w-full rounded-lg py-6 text-sm transition-colors"
          style={{
            background: 'var(--bg-elevated)',
            border: `1.5px dashed ${file ? 'var(--accent)' : 'var(--border)'}`,
            color: file ? 'var(--accent)' : 'var(--text-muted)',
          }}
        >
          {file ? (
            <div>
              <div className="font-semibold">{file.name}</div>
              <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {formatBytes(file.size)} · click to change
              </div>
            </div>
          ) : (
            <>
              <Upload size={20} style={{ display: 'inline-block', marginRight: 6 }} />
              Click to choose a file
            </>
          )}
        </button>
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Dataset name">
          <input value={name} onChange={(e) => setName(e.target.value)} className="input" />
        </Field>
        <Field label="Description (optional)">
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input"
          />
        </Field>
      </div>

      {error && (
        <div className="text-xs px-3 py-2 rounded-md" style={{ background: 'var(--error-bg)', color: 'var(--error)' }}>
          {error}
        </div>
      )}

      <ModalFooter
        onClose={onClose}
        onSubmit={submit}
        disabled={!file || saving}
        submitLabel={saving ? 'Uploading…' : 'Upload & Bind'}
      />
    </Modal>
  )
}

// ── Preview side panel ────────────────────────────────────────────────────
function PreviewPanel({
  dataset, onClose, onAskAgent,
}: {
  dataset: Dataset
  onClose: () => void
  onAskAgent: (q: string) => void
}) {
  const [preview, setPreview] = useState<DatasetPreview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setPreview(null)
    setError(null)
    api
      .get<DatasetPreview>(`/api/datasets/${dataset.id}/preview`, { params: { n: 25 } })
      .then((r) => setPreview(r.data))
      .catch((e) => setError(e?.response?.data?.detail || 'Could not load preview'))
  }, [dataset.id])

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
            background: 'linear-gradient(135deg, var(--accent), var(--teal))',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div>
            <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>
              {dataset.name}
            </div>
            <div className="font-mono" style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
              {dataset.source_kind === 'upload'
                ? `Upload · ${(dataset.file_format || '').toUpperCase()} · ${formatBytes(dataset.size_bytes)}`
                : `${dataset.data_source_id} · ${dataset.table_ref}`}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg"
            style={{ color: 'rgba(255,255,255,0.85)' }}
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {error && (
            <div
              className="text-xs px-3 py-2 rounded-md"
              style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
            >
              {error}
            </div>
          )}
          {!preview && !error && (
            <div
              className="flex items-center gap-2 text-xs"
              style={{ color: 'var(--text-muted)' }}
            >
              <Loader2 size={12} className="animate-spin" /> Loading preview…
            </div>
          )}
          {preview && (
            <>
              <div>
                <div className="section-title">Schema ({preview.columns.length} columns)</div>
                <div
                  className="rounded-lg p-2 font-mono grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-0.5"
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', fontSize: 11 }}
                >
                  {preview.columns.map((c) => (
                    <div key={c.name} className="flex justify-between">
                      <span style={{ color: 'var(--text-primary)' }}>{c.name}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{c.dtype}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="section-title" style={{ marginBottom: 0 }}>
                    Sample Rows ({preview.sample_rows.length}
                    {preview.total_rows != null ? ` of ${preview.total_rows.toLocaleString()}` : ''})
                  </div>
                  <button
                    onClick={() =>
                      onAskAgent(
                        `Look at the dataset "${dataset.name}" — what would you suggest analyzing? Columns: ${preview.columns.map((c) => c.name).join(', ')}.`,
                      )
                    }
                    className="text-[11px] flex items-center gap-1"
                    style={{ color: 'var(--accent)', fontWeight: 600 }}
                  >
                    <Sparkles size={11} /> Ask Agent
                  </button>
                </div>
                <div
                  className="overflow-auto rounded-lg"
                  style={{ border: '1px solid var(--border)', maxHeight: 480 }}
                >
                  <table className="w-full text-xs font-mono">
                    <thead style={{ background: 'var(--bg-elevated)', position: 'sticky', top: 0 }}>
                      <tr>
                        {preview.columns.map((c) => (
                          <th
                            key={c.name}
                            className="text-left py-2 px-3 whitespace-nowrap"
                            style={{
                              fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                              textTransform: 'uppercase', color: 'var(--text-secondary)',
                              borderBottom: '1px solid var(--border)',
                            }}
                          >
                            {c.name}
                            <div
                              style={{ fontSize: 9, fontWeight: 400, textTransform: 'none', color: 'var(--text-muted)' }}
                            >
                              {c.dtype}
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.sample_rows.map((row, i) => (
                        <tr key={i}>
                          {preview.columns.map((c) => (
                            <td
                              key={c.name}
                              className="py-1.5 px-3 whitespace-nowrap"
                              style={{ borderBottom: '1px solid var(--border-subtle)' }}
                            >
                              {formatCell(row[c.name])}
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

// ── Shared modal chrome ───────────────────────────────────────────────────
function Modal({
  title, onClose, children,
}: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(11,15,25,0.45)' }} onClick={onClose} />
      <div
        className="fixed top-1/2 left-1/2 z-50 flex flex-col"
        style={{
          width: 'min(640px, 96vw)',
          maxHeight: '90vh',
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

// ── tiny formatters ───────────────────────────────────────────────────────
function formatBytes(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${(n / 1024 ** 3).toFixed(1)} GB`
}

function formatCell(v: any): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(4)
  }
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
