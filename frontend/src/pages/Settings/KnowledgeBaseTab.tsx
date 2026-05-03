import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Upload, Trash2, FileText, FileSpreadsheet, FileCode2, FileImage,
  FileBox, BookOpen, Search, Filter,
} from 'lucide-react'
import api from '@/lib/api'

type DocumentInfo = {
  id: string
  name: string
  size_bytes: number
  extension: string
  scope: string | null
  uploaded_at: string
}

type DocsRoot = {
  root: string
  exists: boolean
  extensions: string[]
  env_var: string
  env_value: string | null
}

const EXT_META: Record<string, { color: string; icon: any }> = {
  '.md':    { color: '#0EA5E9', icon: FileText },
  '.txt':   { color: '#64748B', icon: FileText },
  '.pdf':   { color: '#DC2626', icon: FileBox },
  '.docx':  { color: '#2563EB', icon: FileText },
  '.pptx':  { color: '#EA580C', icon: FileImage },
  '.py':    { color: '#7C3AED', icon: FileCode2 },
  '.csv':   { color: '#059669', icon: FileSpreadsheet },
  '.xlsx':  { color: '#16A34A', icon: FileSpreadsheet },
  '.xls':   { color: '#16A34A', icon: FileSpreadsheet },
  '.json':  { color: '#D97706', icon: FileCode2 },
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatDate(iso: string): string {
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

export default function KnowledgeBaseTab() {
  const [docs, setDocs] = useState<DocumentInfo[]>([])
  const [root, setRoot] = useState<DocsRoot | null>(null)
  const [loading, setLoading] = useState(true)
  const [scopeFilter, setScopeFilter] = useState<string>('__all__')
  const [searchQuery, setSearchQuery] = useState('')
  const [uploadScope, setUploadScope] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [d, r] = await Promise.all([
        api.get<DocumentInfo[]>('/api/documents'),
        api.get<DocsRoot>('/api/documents/root'),
      ])
      setDocs(d.data)
      setRoot(r.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const scopes = useMemo(() => {
    const s = new Set<string>()
    for (const d of docs) if (d.scope) s.add(d.scope)
    return Array.from(s).sort()
  }, [docs])

  const filtered = useMemo(() => {
    return docs.filter((d) => {
      if (scopeFilter === '__all__') {
        // pass
      } else if (scopeFilter === '__root__') {
        if (d.scope) return false
      } else if (d.scope !== scopeFilter) {
        return false
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        if (!d.name.toLowerCase().includes(q) && !(d.scope || '').toLowerCase().includes(q)) {
          return false
        }
      }
      return true
    })
  }, [docs, scopeFilter, searchQuery])

  const totalSize = useMemo(() => docs.reduce((sum, d) => sum + d.size_bytes, 0), [docs])

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    setUploading(true)
    try {
      for (const f of files) {
        const fd = new FormData()
        fd.append('file', f)
        if (uploadScope.trim()) fd.append('scope', uploadScope.trim())
        try {
          await api.post('/api/documents/upload', fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
        } catch (err: any) {
          alert(`Upload failed for ${f.name}: ${err?.response?.data?.detail || err.message}`)
        }
      }
      if (fileRef.current) fileRef.current.value = ''
      await load()
    } finally {
      setUploading(false)
    }
  }

  const onDelete = async (id: string, name: string) => {
    if (!confirm(`Delete ${name}?`)) return
    await api.delete(`/api/documents/${encodeURIComponent(id)}`)
    load()
  }

  return (
    <div>
      {/* ─ Header strip ─────────────────────────────────────────────────── */}
      <div
        className="rounded-xl p-4 mb-5 flex flex-wrap items-center gap-4"
        style={{
          background: 'linear-gradient(135deg, rgba(14,165,233,0.06), rgba(124,58,237,0.04))',
          border: '1px solid var(--border)',
        }}
      >
        <div
          className="w-11 h-11 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: 'rgba(14,165,233,0.12)', color: '#0EA5E9' }}
        >
          <BookOpen size={20} />
        </div>
        <div className="flex-1 min-w-[260px]">
          <div className="font-display text-base font-semibold mb-0.5">Knowledge Base</div>
          <div className="text-[12px] leading-snug" style={{ color: 'var(--text-secondary)' }}>
            Upload model whitepapers, reports, decks, and code that the{' '}
            <span className="font-mono text-[11px]" style={{ color: 'var(--accent)' }}>rag_search</span>{' '}
            tool can query for domain-specific context. Group related files by scope (e.g.{' '}
            <span className="font-mono text-[11px]">retail_deposit</span>) so agents can pre-filter their searches.
          </div>
        </div>
        <div className="flex flex-col items-end gap-0.5 text-[11px]" style={{ color: 'var(--text-muted)' }}>
          <div><strong style={{ color: 'var(--text-primary)' }}>{docs.length}</strong> file{docs.length === 1 ? '' : 's'}</div>
          <div>{formatBytes(totalSize)} stored</div>
        </div>
      </div>

      {/* ─ Action bar ──────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="relative flex-1 min-w-[220px] max-w-[420px]">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search filenames or scopes…"
            className="w-full pl-9 pr-3 py-2 rounded-lg text-[13px]"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
          />
        </div>
        <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px]"
             style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
          <Filter size={12} style={{ color: 'var(--text-muted)' }} />
          <select
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value)}
            className="bg-transparent outline-none"
            style={{ color: 'var(--text-primary)' }}
          >
            <option value="__all__">All scopes</option>
            <option value="__root__">No scope (root)</option>
            {scopes.map((s) => (<option key={s} value={s}>{s}</option>))}
          </select>
        </div>

        <input
          value={uploadScope}
          onChange={(e) => setUploadScope(e.target.value)}
          placeholder="Upload scope (optional, e.g. retail_deposit)"
          className="px-3 py-2 rounded-lg text-[12px] flex-1 min-w-[200px] max-w-[300px]"
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
        />
        <input
          ref={fileRef}
          type="file"
          multiple
          className="hidden"
          accept={root?.extensions.join(',') || '.md,.txt,.pdf,.docx,.pptx,.py,.csv,.xlsx,.xls,.json'}
          onChange={onUpload}
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          <Upload size={13} /> {uploading ? 'Uploading…' : 'Upload Files'}
        </button>
      </div>

      {/* ─ Storage path hint ──────────────────────────────────────────── */}
      {root && (
        <div
          className="text-[11px] mb-4 px-3 py-2 rounded-md font-mono"
          style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}
        >
          <span className="opacity-60">Storage:</span> {root.root}
          {!root.exists && <span style={{ color: 'var(--warning)' }}> (will be created on first upload)</span>}
          {root.env_value && <span className="opacity-60"> · via ${root.env_var}</span>}
        </div>
      )}

      {/* ─ File grid ──────────────────────────────────────────────────── */}
      {loading ? (
        <div className="text-sm text-center py-12" style={{ color: 'var(--text-muted)' }}>Loading…</div>
      ) : filtered.length === 0 ? (
        <div
          className="text-center py-16 rounded-xl"
          style={{ border: '1px dashed var(--border)', background: 'var(--bg-elevated)' }}
        >
          <BookOpen size={28} className="mx-auto mb-3" style={{ color: 'var(--text-muted)' }} />
          <div className="text-sm font-semibold mb-1">
            {docs.length === 0 ? 'No documents yet' : 'No documents match this filter'}
          </div>
          <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
            {docs.length === 0
              ? 'Upload whitepapers, reports, decks, or code so agents can ground their answers.'
              : 'Try clearing the search or scope filter.'}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((d) => {
            const meta = EXT_META[d.extension] || { color: '#64748B', icon: FileText }
            const Icon = meta.icon
            return (
              <div key={d.id} className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="flex items-start gap-3 mb-2">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: `${meta.color}1A`, color: meta.color }}
                  >
                    <Icon size={16} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-[13px] truncate" title={d.name}>{d.name}</div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {d.scope && (
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded-md font-mono"
                          style={{ background: 'rgba(14,165,233,0.12)', color: '#0EA5E9' }}
                        >
                          {d.scope}
                        </span>
                      )}
                      <span
                        className="text-[10px] uppercase tracking-wider font-semibold"
                        style={{ color: 'var(--text-muted)' }}
                      >
                        {d.extension.replace('.', '')}
                      </span>
                    </div>
                  </div>
                </div>
                <div
                  className="flex items-center justify-between mt-auto pt-3"
                  style={{ borderTop: '1px solid var(--border-subtle)' }}
                >
                  <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                    {formatBytes(d.size_bytes)} · {formatDate(d.uploaded_at)}
                  </div>
                  <button
                    onClick={() => onDelete(d.id, d.name)}
                    className="p-1.5 rounded-md transition-colors"
                    style={{ color: 'var(--text-muted)' }}
                    title="Delete"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
