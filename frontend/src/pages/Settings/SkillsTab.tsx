import { useEffect, useRef, useState } from 'react'
import { Plus, Pencil, Trash2, Upload, Wrench, Database, FileText, ShieldAlert, Star, X, Sparkles } from 'lucide-react'
import api from '@/lib/api'
import type { AgentSkill, PythonTool } from '@/types'

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
  const [tools, setTools] = useState<PythonTool[]>([])
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<EditorState>({ open: false, mode: 'create', skill: null })
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<AgentSkill[]>('/api/skills'),
      api.get<PythonTool[]>('/api/tools'),
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {skills.map((s) => {
          const meta = CATEGORY_META[s.category]
          const Icon = meta.icon
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
                    <div className="font-semibold text-sm truncate">{s.name}</div>
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
                  title="Edit"
                  onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--accent)')}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
                >
                  <Pencil size={13} />
                </button>
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
              </div>
            </div>
          )
        })}
      </div>

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
  tools: PythonTool[]
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

          <div>
            <div
              className="text-[11px] font-semibold uppercase tracking-widest mb-1"
              style={{ color: 'var(--text-secondary)' }}
            >
              Tools ({s.tools.length} selected)
            </div>
            <div
              className="rounded-lg p-2 space-y-1"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', maxHeight: 220, overflowY: 'auto' }}
            >
              {tools.length === 0 && (
                <div className="text-xs px-2 py-3" style={{ color: 'var(--text-muted)' }}>
                  No tools yet. Open the <strong>Tools</strong> tab to register Python functions.
                </div>
              )}
              {tools.map((t) => {
                const sel = s.tools.includes(t.name)
                return (
                  <label
                    key={t.id}
                    className="flex items-start gap-2 px-2 py-2 rounded-md cursor-pointer transition-colors"
                    style={{ background: sel ? 'var(--accent-light)' : 'transparent' }}
                  >
                    <input type="checkbox" checked={sel} onChange={() => onToggleTool(t.name)} className="mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div
                        className="font-mono text-[12px] font-semibold"
                        style={{ color: sel ? 'var(--accent)' : 'var(--text-primary)' }}
                      >
                        {t.name}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                        {t.description}
                      </div>
                    </div>
                    {!t.enabled && (
                      <span className="pill" style={{ fontSize: 9, color: 'var(--text-muted)' }}>
                        OFF
                      </span>
                    )}
                  </label>
                )
              })}
            </div>
          </div>
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
