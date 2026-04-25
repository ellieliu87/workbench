import { useEffect, useRef, useState } from 'react'
import { Database, Plus, RefreshCw, Trash2, Upload, Snowflake, Cloud, FileText, Globe, HardDrive } from 'lucide-react'
import api from '@/lib/api'
import type { DataSource } from '@/types'

const TYPE_META: Record<DataSource['type'], { label: string; icon: any; color: string }> = {
  snowflake:   { label: 'Snowflake',    icon: Snowflake, color: '#29B5E8' },
  onelake:     { label: 'OneLake',      icon: Cloud,     color: '#0078D4' },
  file_upload: { label: 'File Upload',  icon: FileText,  color: '#7C3AED' },
  rest_api:    { label: 'REST API',     icon: Globe,     color: '#059669' },
  postgres:    { label: 'Postgres',     icon: Database,  color: '#336791' },
  s3:          { label: 'S3',           icon: HardDrive, color: '#D97706' },
}

export default function DataSourcesTab() {
  const [sources, setSources] = useState<DataSource[]>([])
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [draft, setDraft] = useState({ name: '', type: 'snowflake' as DataSource['type'], description: '', host: '', database: '' })
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setLoading(true)
    api.get<DataSource[]>('/api/datasources').then((r) => setSources(r.data)).finally(() => setLoading(false))
  }

  useEffect(load, [])

  const create = async () => {
    if (!draft.name) return
    await api.post('/api/datasources', {
      name: draft.name,
      type: draft.type,
      description: draft.description,
      config: { host: draft.host, database: draft.database },
    })
    setShowNew(false)
    setDraft({ name: '', type: 'snowflake', description: '', host: '', database: '' })
    load()
  }

  const test = async (id: string) => {
    await api.post(`/api/datasources/${id}/test`)
    load()
  }

  const remove = async (id: string) => {
    if (!confirm('Delete this data source?')) return
    await api.delete(`/api/datasources/${id}`)
    load()
  }

  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    const fd = new FormData()
    fd.append('file', f)
    await api.post('/api/datasources/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    if (fileRef.current) fileRef.current.value = ''
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
          {loading ? 'Loading…' : `${sources.length} data source${sources.length === 1 ? '' : 's'} configured`}
        </div>
        <div className="flex gap-2">
          <input ref={fileRef} type="file" className="hidden" onChange={onFileChange} accept=".csv,.json,.parquet,.xlsx,.xls" />
          <button
            onClick={() => fileRef.current?.click()}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            <Upload size={13} /> Upload File
          </button>
          <button
            onClick={() => setShowNew((v) => !v)}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            <Plus size={13} /> Add Source
          </button>
        </div>
      </div>

      {showNew && (
        <div className="panel mb-4">
          <div className="font-display text-base font-semibold mb-3">New Data Source</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Name">
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                className="input"
                placeholder="e.g. Snowflake — Risk Mart"
              />
            </Field>
            <Field label="Type">
              <select
                value={draft.type}
                onChange={(e) => setDraft({ ...draft, type: e.target.value as DataSource['type'] })}
                className="input"
              >
                {Object.entries(TYPE_META).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Host / endpoint">
              <input
                value={draft.host}
                onChange={(e) => setDraft({ ...draft, host: e.target.value })}
                className="input"
                placeholder="e.g. cma_warehouse.snowflakecomputing.com"
              />
            </Field>
            <Field label="Database / lakehouse">
              <input
                value={draft.database}
                onChange={(e) => setDraft({ ...draft, database: e.target.value })}
                className="input"
                placeholder="e.g. CMA"
              />
            </Field>
            <Field label="Description" className="md:col-span-2">
              <textarea
                rows={2}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                className="input resize-none"
              />
            </Field>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setShowNew(false)} className="px-3 py-2 text-xs rounded-lg" style={{ color: 'var(--text-muted)' }}>
              Cancel
            </button>
            <button
              onClick={create}
              disabled={!draft.name}
              className="px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              Create
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {sources.map((s) => {
          const meta = TYPE_META[s.type]
          const Icon = meta.icon
          return (
            <div key={s.id} className="panel">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                    style={{ background: `${meta.color}1A`, color: meta.color }}
                  >
                    <Icon size={16} />
                  </div>
                  <div>
                    <div className="font-semibold text-sm">{s.name}</div>
                    <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      {meta.label}
                    </div>
                  </div>
                </div>
                <StatusPill status={s.status} />
              </div>
              {s.description && (
                <div className="text-xs my-2" style={{ color: 'var(--text-secondary)' }}>
                  {s.description}
                </div>
              )}
              {s.connection_string && (
                <div
                  className="text-[11px] font-mono px-2 py-1 rounded mt-2"
                  style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}
                >
                  {s.connection_string}
                </div>
              )}
              <div className="flex items-center justify-between mt-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  {s.last_synced ? `Synced ${new Date(s.last_synced).toLocaleString()}` : 'Never synced'}
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => test(s.id)}
                    className="p-1.5 rounded-md transition-colors"
                    style={{ color: 'var(--text-muted)' }}
                    title="Test connection"
                  >
                    <RefreshCw size={13} />
                  </button>
                  <button
                    onClick={() => remove(s.id)}
                    className="p-1.5 rounded-md transition-colors"
                    style={{ color: 'var(--text-muted)' }}
                    title="Delete"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <style>{`
        .input {
          width: 100%;
          padding: 8px 10px;
          border-radius: 8px;
          font-size: 13px;
          background: var(--bg-elevated);
          border: 1px solid var(--border);
          color: var(--text-primary);
        }
      `}</style>
    </div>
  )
}

function Field({ label, children, className = '' }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={className}>
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

function StatusPill({ status }: { status: DataSource['status'] }) {
  const map = {
    connected:    { color: 'var(--success)', bg: 'var(--success-bg)', text: 'CONNECTED' },
    pending:      { color: 'var(--warning)', bg: 'var(--warning-bg)', text: 'PENDING' },
    disconnected: { color: 'var(--text-muted)', bg: 'var(--bg-elevated)', text: 'DISCONNECTED' },
    error:        { color: 'var(--error)', bg: 'var(--error-bg)', text: 'ERROR' },
  } as const
  const m = map[status]
  return (
    <span
      style={{
        background: m.bg,
        color: m.color,
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: '0.08em',
        padding: '3px 8px',
        borderRadius: 9999,
      }}
    >
      {m.text}
    </span>
  )
}
