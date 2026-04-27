import { useEffect, useMemo, useRef, useState } from 'react'
import { Plus, Pencil, Trash2, Upload, Wrench, Database, FileText, ShieldAlert, Star, X, Sparkles, Lock, UserCog, Search, AlertTriangle } from 'lucide-react'
import api from '@/lib/api'
import type { AgentSkill } from '@/types'

interface AvailableTool {
  name: string
  description: string
  kind: 'introspection' | 'python'
  source: 'builtin' | 'user'
  parameter_count: number
  enabled: boolean
}

const CATEGORY_META: Record<AgentSkill['category'], { label: string; icon: any; color: string }> = {
  analytical: { label: 'Analytical', icon: Wrench,      color: '#0891B2' },
  data:       { label: 'Data',       icon: Database,    color: '#7C3AED' },
  reporting:  { label: 'Reporting',  icon: FileText,    color: '#059669' },
  risk:       { label: 'Risk',       icon: ShieldAlert, color: '#DC2626' },
  custom:     { label: 'Custom',     icon: Star,        color: '#D97706' },
}

interface EditorState {
  open: boolean
  mode: 'create' | 'edit'
  skill: AgentSkill | null
}

const EMPTY_SKILL: AgentSkill = {
  id: '',
  name: '',
  description: '',
  category: 'analytical',
  enabled: true,
  instructions: '',
  tools: [],
}

export default function SkillsTab() {
  const [skills, setSkills] = useState<AgentSkill[]>([])
  const [tools, setTools] = useState<AvailableTool[]>([])
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<EditorState>({ open: false, mode: 'create', skill: null })
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<AgentSkill[]>('/api/skills'),
      api.get<AvailableTool[]>('/api/skills/_available_tools'),
    ])
      .then(([s, t]) => { setSkills(s.data); setTools(t.data) })
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const openCreate = async () => {
    const r = await api.get<{ template: string }>('/api/skills/template?name=Untitled%20Skill')
    setEditor({
      open: true,
      mode: 'create',
      skill: { ...EMPTY_SKILL, instructions: r.data.template },
    })
  }

  const openEdit = (s: AgentSkill) => {
    setEditor({ open: true, mode: 'edit', skill: { ...s } })
  }

  const closeEditor = () => setEditor({ open: false, mode: 'create', skill: null })

  const save = async () => {
    if (!editor.skill || !editor.skill.name) return
    if (editor.mode === 'create') {
      await api.post('/api/skills', {
        name: editor.skill.name,
        description: editor.skill.description,
        category: editor.skill.category,
        instructions: editor.skill.instructions,
        tools: editor.skill.tools,
      })
    } else {
      await api.patch(`/api/skills/${editor.skill.id}`, {
        name: editor.skill.name,
        description: editor.skill.description,
        category: editor.skill.category,
        instructions: editor.skill.instructions,
        tools: editor.skill.tools,
        enabled: editor.skill.enabled,
      })
    }
    closeEditor()
    load()
  }

  const insertTemplate = async () => {
    if (!editor.skill) return
    const name = editor.skill.name || 'Untitled Skill'
    const r = await api.get<{ template: string }>(`/api/skills/template?name=${encodeURIComponent(name)}`)
    setEditor((e) => (e.skill ? { ...e, skill: { ...e.skill, instructions: r.data.template } } : e))
  }

  const toggle = async (id: string) => {
    await api.patch(`/api/skills/${id}/toggle`)
    load()
  }

  const remove = async (id: string) => {
    if (!confirm('Delete this skill?')) return
    await api.delete(`/api/skills/${id}`)
    load()
  }

  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    const fd = new FormData()
    fd.append('file', f)
    await api.post('/api/skills/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    if (fileRef.current) fileRef.current.value = ''
    load()
  }

  const updateField = <K extends keyof AgentSkill>(k: K, v: AgentSkill[K]) => {
    setEditor((e) => (e.skill ? { ...e, skill: { ...e.skill, [k]: v } } : e))
  }

  const toggleTool = (name: string) => {
    if (!editor.skill) return
    const has = editor.skill.tools.includes(name)
    updateField('tools', has ? editor.skill.tools.filter((t) => t !== name) : [...editor.skill.tools, name])
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
          {loading
            ? 'Loading…'
            : `${skills.filter((s) => s.enabled).length} of ${skills.length} skills enabled`}
        </div>
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={onFileChange}
            accept=".md,.txt,.json,.yaml,.yml"
          />
          <button
            onClick={() => fileRef.current?.click()}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            <Upload size={13} /> Upload Skill
          </button>
          <button
            onClick={openCreate}
            className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            <Plus size={13} /> New Skill
          </button>
        </div>
      </div>

      {(() => {
        const userCustom = skills.filter((s) => s.source === 'user')
        const builtin = skills.filter((s) => (s.source ?? 'builtin') === 'builtin')
        // Group pack-derived skills by their pack_id so each pack gets its
        // own section. Packs are sorted alphabetically; skills within a pack
        // are kept in API order.
        const packedByPack = new Map<string, AgentSkill[]>()
        for (const s of skills) {
          if (s.source !== 'pack') continue
          const pid = s.pack_id || 'unknown'
          if (!packedByPack.has(pid)) packedByPack.set(pid, [])
          packedByPack.get(pid)!.push(s)
        }

        const renderCard = (s: AgentSkill) => {
          const meta = CATEGORY_META[s.category]
          const Icon = meta.icon
          const isUser = s.source === 'user'
          const isPack = s.source === 'pack'
          const badgeBg = isUser ? 'rgba(217,119,6,0.12)' : isPack ? 'rgba(37,99,235,0.12)' : 'rgba(8,145,178,0.12)'
          const badgeColor = isUser ? '#D97706' : isPack ? '#2563EB' : '#0891B2'
          return (
            <div key={s.id} className="panel">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: `${meta.color}1A`, color: meta.color }}
                  >
                    <Icon size={16} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-sm truncate">{s.name}</span>
                      <span
                        className="pill flex items-center gap-1"
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          background: badgeBg,
                          color: badgeColor,
                          borderColor: 'transparent',
                          textTransform: 'uppercase',
                          letterSpacing: '0.06em',
                        }}
                      >
                        {isUser ? <><UserCog size={9} /> User</>
                          : isPack ? <>Pack: {s.pack_id}</>
                          : <><Lock size={9} /> Built-in</>}
                      </span>
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      {meta.label}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => toggle(s.id)}
                  className="px-2 py-1 rounded-full text-[10px] font-bold tracking-wider transition-colors"
                  style={{
                    background: s.enabled ? 'var(--success-bg)' : 'var(--bg-elevated)',
                    color: s.enabled ? 'var(--success)' : 'var(--text-muted)',
                  }}
                >
                  {s.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
              <div className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                {s.description}
              </div>
              {s.tools.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {s.tools.map((t) => (
                    <span key={t} className="pill" style={{ fontSize: 10 }}>
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <div
                className="flex items-center justify-end gap-1 mt-3 pt-3"
                style={{ borderTop: '1px solid var(--border-subtle)' }}
              >
                <button
                  onClick={() => openEdit(s)}
                  className="p-1.5 rounded-md transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                  title={isUser ? 'Edit' : 'View / fork to user copy'}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--accent)')}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
                >
                  <Pencil size={13} />
                </button>
                {isUser && (
                  <button
                    onClick={() => remove(s.id)}
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
          )
        }

        const SectionHeader = ({
          icon: Icon, color, title, subtitle, count,
        }: { icon: any; color: string; title: string; subtitle: string; count: number }) => (
          <div className="flex items-center gap-2 mb-2 mt-1">
            <div
              className="w-6 h-6 rounded-md flex items-center justify-center"
              style={{ background: `${color}1A`, color }}
            >
              <Icon size={13} />
            </div>
            <div className="flex items-baseline gap-2 min-w-0">
              <span className="text-[12px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-primary)' }}>
                {title}
              </span>
              <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
                {count} skill{count === 1 ? '' : 's'}
              </span>
              <span className="text-[11px] truncate" style={{ color: 'var(--text-muted)' }}>
                · {subtitle}
              </span>
            </div>
          </div>
        )

        const packIds = Array.from(packedByPack.keys()).sort()

        return (
          <>
            <SectionHeader
              icon={UserCog}
              color="#D97706"
              title="User-Customized Skills"
              subtitle="Skills you uploaded or created. Editable & deletable."
              count={userCustom.length}
            />
            {userCustom.length === 0 ? (
              <div className="panel text-center py-6 text-xs mb-5" style={{ color: 'var(--text-muted)' }}>
                None yet. Click <strong>+ New Skill</strong> or <strong>Upload Skill</strong> to add your own.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
                {userCustom.map(renderCard)}
              </div>
            )}

            {/* One section per domain pack — scales naturally to 5-6 packs. */}
            {packIds.map((pid) => {
              const inPack = packedByPack.get(pid) || []
              return (
                <div key={pid}>
                  <SectionHeader
                    icon={Star}
                    color="#2563EB"
                    title={`Domain Pack — ${pid}`}
                    subtitle="Installed by a domain pack. Read-only here; manage with the pack."
                    count={inPack.length}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
                    {inPack.map(renderCard)}
                  </div>
                </div>
              )
            })}

            <SectionHeader
              icon={Lock}
              color="#0891B2"
              title="Built-in Skills"
              subtitle="Shipped with the workbench. Read-only — fork by editing & saving."
              count={builtin.length}
            />
            {builtin.length === 0 ? (
              <div className="panel text-center py-6 text-xs" style={{ color: 'var(--text-muted)' }}>
                No built-in skills found in <code>agent/skills/</code>.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {builtin.map(renderCard)}
              </div>
            )}
          </>
        )
      })()}

      {editor.open && editor.skill && (
        <SkillEditor
          state={editor}
          tools={tools}
          onClose={closeEditor}
          onSave={save}
          onChange={updateField}
          onToggleTool={toggleTool}
          onInsertTemplate={insertTemplate}
        />
      )}
    </div>
  )
}

interface EditorProps {
  state: EditorState
  tools: AvailableTool[]
  onClose: () => void
  onSave: () => void
  onChange: <K extends keyof AgentSkill>(k: K, v: AgentSkill[K]) => void
  onToggleTool: (name: string) => void
  onInsertTemplate: () => void
}

function SkillEditor({ state, tools, onClose, onSave, onChange, onToggleTool, onInsertTemplate }: EditorProps) {
  const s = state.skill!
  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(11,15,25,0.45)' }} onClick={onClose} />
      <div
        className="fixed top-0 right-0 bottom-0 z-50 flex flex-col"
        style={{
          width: 'min(720px, 92vw)',
          background: 'var(--bg-card)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-12px 0 48px rgba(0,0,0,0.18)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{
            background: 'linear-gradient(135deg, var(--accent), var(--teal))',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div>
            <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>
              {state.mode === 'create' ? 'New Skill' : 'Edit Skill'}
            </div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
              {state.mode === 'edit' ? s.id : 'Drafting…'}
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

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name">
              <input
                className="input"
                value={s.name}
                onChange={(e) => onChange('name', e.target.value)}
                placeholder="e.g. Daily NIM Brief"
              />
            </Field>
            <Field label="Category">
              <select
                className="input"
                value={s.category}
                onChange={(e) => onChange('category', e.target.value as AgentSkill['category'])}
              >
                {Object.entries(CATEGORY_META).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Description">
            <textarea
              rows={2}
              className="input resize-none"
              value={s.description}
              onChange={(e) => onChange('description', e.target.value)}
            />
          </Field>

          <div>
            <div className="flex items-center justify-between mb-1">
              <span
                className="text-[11px] font-semibold uppercase tracking-widest"
                style={{ color: 'var(--text-secondary)' }}
              >
                System Instructions
              </span>
              <button
                onClick={onInsertTemplate}
                className="text-[11px] flex items-center gap-1"
                style={{ color: 'var(--accent)', fontWeight: 600 }}
              >
                <Sparkles size={11} /> Use Template
              </button>
            </div>
            <textarea
              rows={14}
              className="input resize-y font-mono"
              style={{ fontSize: 12, lineHeight: 1.55 }}
              value={s.instructions || ''}
              onChange={(e) => onChange('instructions', e.target.value)}
              placeholder="Markdown describing what the skill does, when to use it, and how to format the output…"
            />
          </div>

          <ToolPicker
            allTools={tools}
            selected={s.tools}
            onToggle={onToggleTool}
          />
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-2 px-5 py-3"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <button onClick={onClose} className="px-3 py-2 text-xs rounded-lg" style={{ color: 'var(--text-muted)' }}>
            Cancel
          </button>
          <button
            onClick={onSave}
            disabled={!s.name}
            className="px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            {state.mode === 'create' ? 'Create Skill' : 'Save Changes'}
          </button>
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

// ── Tool picker: chips for what's wired in + search-to-add for the rest ──
function ToolPicker({
  allTools, selected, onToggle,
}: {
  allTools: AvailableTool[]
  selected: string[]
  onToggle: (name: string) => void
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const byName = useMemo(() => {
    const m = new Map<string, AvailableTool>()
    for (const t of allTools) m.set(t.name, t)
    return m
  }, [allTools])

  const selectedTools = selected.map((n) => byName.get(n) || null)
  const unknownNames = selected.filter((n) => !byName.has(n))

  // What's not wired in yet, optionally narrowed by the query.
  const candidates = useMemo(() => {
    const q = query.trim().toLowerCase()
    return allTools
      .filter((t) => !selected.includes(t.name))
      .filter((t) => !q || t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q))
  }, [allTools, selected, query])

  // Click-outside closes the dropdown.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const addTool = (name: string) => {
    onToggle(name)
    setQuery('')
    setActiveIdx(0)
    inputRef.current?.focus()
  }

  return (
    <div>
      <div
        className="flex items-baseline justify-between mb-1"
      >
        <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
          Tools ({selected.length})
        </span>
        <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
          {allTools.length} available · {selected.length === 0 ? 'add the first one below' : 'click × on a chip to remove'}
        </span>
      </div>

      {/* Selected chips */}
      <div
        className="rounded-lg p-2 flex flex-wrap gap-1.5 min-h-[44px]"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
      >
        {selected.length === 0 && unknownNames.length === 0 && (
          <span className="text-[11px] px-1 py-1" style={{ color: 'var(--text-muted)' }}>
            No tools wired in yet.
          </span>
        )}

        {unknownNames.map((name) => (
          <span
            key={`missing:${name}`}
            className="inline-flex items-center gap-1 rounded-full"
            style={{
              padding: '3px 6px 3px 8px',
              background: 'var(--warning-bg)',
              color: 'var(--warning)',
              border: '1px solid currentColor',
              fontSize: 11,
            }}
            title="Tool not in catalog — probably a typo or it was deleted. Click × to remove."
          >
            <AlertTriangle size={10} />
            <span className="font-mono">{name}</span>
            <button
              onClick={() => onToggle(name)}
              className="ml-1 rounded-full"
              style={{ width: 14, height: 14, lineHeight: '12px', textAlign: 'center', background: 'transparent', color: 'inherit' }}
            >
              <X size={10} />
            </button>
          </span>
        ))}

        {selectedTools.map((t, i) => {
          if (!t) return null
          const isUser = t.source === 'user'
          const isPython = t.kind === 'python'
          return (
            <span
              key={`sel:${t.name}`}
              className="inline-flex items-center gap-1 rounded-full"
              style={{
                padding: '3px 6px 3px 8px',
                background: 'var(--accent-light)',
                color: 'var(--accent)',
                border: '1px solid var(--accent)',
                fontSize: 11,
              }}
              title={`${t.kind === 'introspection' ? 'introspection' : (isUser ? 'user python tool' : 'built-in python tool')}${t.description ? ' — ' + t.description : ''}`}
            >
              <span className="font-mono">{t.name}</span>
              {isUser && (
                <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.85 }}>U</span>
              )}
              {!isPython && (
                <span style={{ fontSize: 8, fontWeight: 700, opacity: 0.6 }}>·intro</span>
              )}
              <button
                onClick={() => onToggle(t.name)}
                className="ml-1 rounded-full"
                style={{ width: 14, height: 14, lineHeight: '12px', textAlign: 'center', background: 'transparent', color: 'inherit' }}
              >
                <X size={10} />
              </button>
            </span>
          )
        })}
      </div>

      {/* Search-to-add */}
      <div ref={containerRef} className="relative mt-2">
        <div
          className="flex items-center gap-2 rounded-lg px-2"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <Search size={13} style={{ color: 'var(--text-muted)' }} />
          <input
            ref={inputRef}
            value={query}
            onFocus={() => setOpen(true)}
            onChange={(e) => { setQuery(e.target.value); setOpen(true); setActiveIdx(0) }}
            onKeyDown={(e) => {
              if (!open) return
              if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx((i) => Math.min(i + 1, candidates.length - 1)) }
              else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx((i) => Math.max(i - 1, 0)) }
              else if (e.key === 'Enter' && candidates[activeIdx]) { e.preventDefault(); addTool(candidates[activeIdx].name) }
              else if (e.key === 'Escape') { setOpen(false) }
            }}
            placeholder={selected.length === 0 ? 'Search and add tools…' : 'Add another tool…'}
            className="flex-1 py-2 outline-none"
            style={{ background: 'transparent', border: 'none', fontSize: 12, color: 'var(--text-primary)' }}
          />
          {query && (
            <button
              onClick={() => { setQuery(''); inputRef.current?.focus() }}
              className="text-[10px]"
              style={{ color: 'var(--text-muted)' }}
            >
              clear
            </button>
          )}
        </div>

        {open && (
          <div
            className="absolute left-0 right-0 mt-1 rounded-lg overflow-y-auto"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
              maxHeight: 280,
              zIndex: 60,
            }}
          >
            {candidates.length === 0 ? (
              <div className="text-xs px-3 py-2" style={{ color: 'var(--text-muted)' }}>
                {query.trim() ? 'No tools match.' : 'All available tools are already wired in.'}
              </div>
            ) : (
              candidates.map((t, i) => {
                const active = i === activeIdx
                return (
                  <button
                    key={`add:${t.kind}:${t.name}`}
                    onMouseEnter={() => setActiveIdx(i)}
                    onClick={() => addTool(t.name)}
                    className="w-full flex items-start gap-2 px-3 py-2 text-left transition-colors"
                    style={{ background: active ? 'var(--bg-elevated)' : 'transparent' }}
                  >
                    <span
                      className="mt-0.5 inline-block rounded"
                      style={{
                        padding: '1px 5px',
                        fontSize: 8,
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        background: t.kind === 'introspection'
                          ? 'rgba(8,145,178,0.12)'
                          : (t.source === 'user' ? 'rgba(217,119,6,0.12)' : 'rgba(5,150,105,0.12)'),
                        color: t.kind === 'introspection'
                          ? '#0891B2'
                          : (t.source === 'user' ? '#D97706' : '#059669'),
                      }}
                    >
                      {t.kind === 'introspection' ? 'INTRO' : (t.source === 'user' ? 'USER' : 'BUILTIN')}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-[12px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                        {t.name}
                      </div>
                      <div className="text-[11px] truncate" style={{ color: 'var(--text-muted)' }}>
                        {t.description || `${t.parameter_count} param${t.parameter_count === 1 ? '' : 's'}`}
                      </div>
                    </div>
                    <Plus size={11} style={{ color: 'var(--accent)', marginTop: 4 }} />
                  </button>
                )
              })
            )}
          </div>
        )}
      </div>
    </div>
  )
}
