import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  X, Plus, Briefcase, LineChart, Droplet, ShieldAlert, Banknote,
  Building2, Activity, FileSpreadsheet, BarChart3, FlaskConical,
  Boxes, ListChecks, FileBarChart, Database, ArrowRight, Sparkles,
} from 'lucide-react'
import api from '@/lib/api'
import type { BusinessFunction } from '@/types'

// ── Pickers ────────────────────────────────────────────────────────────────
// Curated icon set — every option here renders cleanly in the home grid card,
// the sidebar, and the workspace header. Adding a new icon needs the same
// `id` to be wired into HomePage.tsx and Sidebar.tsx ICON maps.
const ICON_OPTIONS: { id: string; Icon: any; label: string }[] = [
  { id: 'briefcase',        Icon: Briefcase,        label: 'Briefcase'  },
  { id: 'line-chart',       Icon: LineChart,        label: 'Line chart' },
  { id: 'bar-chart',        Icon: BarChart3,        label: 'Bar chart'  },
  { id: 'activity',         Icon: Activity,         label: 'Activity'   },
  { id: 'shield-alert',     Icon: ShieldAlert,      label: 'Risk'       },
  { id: 'banknote',         Icon: Banknote,         label: 'Treasury'   },
  { id: 'droplet',          Icon: Droplet,          label: 'Liquidity'  },
  { id: 'building-2',       Icon: Building2,        label: 'Capital'    },
  { id: 'file-spreadsheet', Icon: FileSpreadsheet,  label: 'Reporting'  },
  { id: 'flask',            Icon: FlaskConical,     label: 'Workflow'   },
  { id: 'boxes',            Icon: Boxes,            label: 'Models'     },
  { id: 'checks',           Icon: ListChecks,       label: 'Playbooks'  },
  { id: 'file-bar-chart',   Icon: FileBarChart,     label: 'Reports'    },
  { id: 'database',         Icon: Database,         label: 'Data'       },
]

// Small palette tuned to the existing function colors. Custom hex is allowed
// via the text input below the swatches.
const COLOR_PRESETS = [
  '#004977', '#0891B2', '#7C3AED', '#DC2626', '#059669', '#D97706',
  '#FF5C5C', '#00B8D9', '#0F766E', '#E11D48', '#6366F1', '#84CC16',
]

interface Props {
  open: boolean
  onClose: () => void
  existingCategories: string[]    // for the category combobox
  onCreated?: (fn: BusinessFunction) => void
}

export default function NewWorkspaceDrawer({
  open, onClose, existingCategories, onCreated,
}: Props) {
  const navigate = useNavigate()

  // ── Identity state
  const [name, setName] = useState('')
  const [shortName, setShortName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState(existingCategories[0] || '')
  const [newCategory, setNewCategory] = useState('')
  const [iconId, setIconId] = useState<string>('briefcase')
  const [color, setColor] = useState<string>(COLOR_PRESETS[0])

  // ── UI state
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset every time the drawer opens — feels weird if a half-typed name
  // from a prior open lingers.
  useEffect(() => {
    if (!open) return
    setName(''); setShortName(''); setDescription('')
    setCategory(existingCategories[0] || '')
    setNewCategory('')
    setIconId('briefcase')
    setColor(COLOR_PRESETS[0])
    setError(null); setSaving(false)
  }, [open, existingCategories])

  // Auto-suggest short name from name when the user hasn't typed one
  // (first word, max 12 chars). Stops auto-suggesting once the user types
  // anything in shortName.
  const [shortNameDirty, setShortNameDirty] = useState(false)
  useEffect(() => {
    if (shortNameDirty) return
    const auto = name.trim().split(/\s+/)[0] || ''
    setShortName(auto.slice(0, 12))
  }, [name, shortNameDirty])

  // Live id preview — same slugify as the backend so the analyst sees
  // exactly what the URL will be.
  const previewId = useMemo(() => {
    const s = name.trim().toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_+|_+$/g, '')
    return s || '(derived from name)'
  }, [name])

  const effectiveCategory = newCategory.trim() || category

  const validate = (): string | null => {
    if (name.trim().length < 2) return 'Name needs at least 2 characters.'
    if (!effectiveCategory) return 'Pick a category or create a new one.'
    if (existingCategories.length === 0 && !newCategory.trim()) {
      return 'No categories exist yet — create a new one.'
    }
    return null
  }

  const submit = async () => {
    const err = validate()
    if (err) { setError(err); return }
    setSaving(true); setError(null)
    try {
      const r = await api.post<BusinessFunction>('/api/functions', {
        name: name.trim(),
        short_name: shortName.trim() || null,
        description: description.trim(),
        category: effectiveCategory,
        icon: iconId,
        color,
      })
      onCreated?.(r.data)
      onClose()
      // Drop the user straight into the new workspace.
      navigate(`/workspace/${r.data.id}`)
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Could not create workspace.')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  const ActiveIcon = ICON_OPTIONS.find((i) => i.id === iconId)?.Icon || Briefcase

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(11,15,25,0.45)' }}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className="fixed top-0 right-0 bottom-0 z-50 flex flex-col"
        style={{
          width: 'min(640px, 92vw)',
          background: 'var(--bg-card)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-12px 0 48px rgba(0,0,0,0.18)',
        }}
      >
        {/* Header — uses the chosen color so the analyst gets a live preview
            of what the workspace will look like in the home grid. */}
        <div
          className="px-5 py-4 flex items-center justify-between"
          style={{
            background: `linear-gradient(135deg, ${color}, color-mix(in srgb, ${color} 70%, var(--teal)))`,
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(255,255,255,0.20)' }}
            >
              <ActiveIcon size={16} color="#fff" />
            </div>
            <div>
              <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>
                New workspace
              </div>
              <div
                className="font-mono"
                style={{ fontSize: 10, color: 'rgba(255,255,255,0.75)' }}
              >
                {previewId}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: 'rgba(255,255,255,0.85)' }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLElement
              el.style.background = 'rgba(255,255,255,0.18)'
              el.style.color = '#fff'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLElement
              el.style.background = 'transparent'
              el.style.color = 'rgba(255,255,255,0.85)'
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          {/* ── Identity */}
          <Section title="Identity" subtitle="Shown in the home grid, sidebar, and workspace header.">
            <Field label="Name" required>
              <input
                className="cma-input"
                value={name}
                autoFocus
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Counterparty Credit Risk"
                maxLength={80}
              />
            </Field>

            <Field
              label="Short name"
              hint={shortName ? `Sidebar badge: "${shortName}"` : 'Auto-derived from the first word of name.'}
            >
              <input
                className="cma-input"
                value={shortName}
                onChange={(e) => { setShortName(e.target.value); setShortNameDirty(true) }}
                placeholder="e.g. CCR"
                maxLength={40}
              />
            </Field>

            <Field label="Description" hint="One sentence on what this workspace tracks.">
              <textarea
                className="cma-input resize-none"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Exposure, EE, EPE and PFE across cleared and bilateral books."
                maxLength={500}
              />
            </Field>
          </Section>

          {/* ── Category */}
          <Section title="Category" subtitle="Workspaces grouped by category on the home page.">
            {existingCategories.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-2">
                {existingCategories.map((c) => {
                  const active = category === c && !newCategory.trim()
                  return (
                    <button
                      key={c}
                      onClick={() => { setCategory(c); setNewCategory('') }}
                      className="text-left rounded-lg px-3 py-2 text-sm transition-colors"
                      style={{
                        background: active ? 'var(--accent-light)' : 'var(--bg-elevated)',
                        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                        color: active ? 'var(--accent)' : 'var(--text-secondary)',
                        fontWeight: active ? 600 : 500,
                      }}
                    >
                      {c}
                    </button>
                  )
                })}
              </div>
            )}
            <Field label={existingCategories.length > 0 ? 'Or create a new category' : 'Create a category'}>
              <input
                className="cma-input"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                placeholder="e.g. Counterparty Risk"
                maxLength={60}
              />
            </Field>
          </Section>

          {/* ── Icon */}
          <Section title="Icon">
            <div
              className="grid grid-cols-7 gap-2 p-3 rounded-lg"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
            >
              {ICON_OPTIONS.map(({ id, Icon, label }) => {
                const active = iconId === id
                return (
                  <button
                    key={id}
                    onClick={() => setIconId(id)}
                    title={label}
                    className="flex items-center justify-center rounded-md transition-colors"
                    style={{
                      width: 40, height: 40,
                      background: active ? color : 'var(--bg-card)',
                      color: active ? '#fff' : 'var(--text-secondary)',
                      border: `1px solid ${active ? color : 'var(--border)'}`,
                    }}
                  >
                    <Icon size={16} />
                  </button>
                )
              })}
            </div>
          </Section>

          {/* ── Color */}
          <Section title="Accent color" subtitle="Drives the gradient header and home-card hover.">
            <div className="flex flex-wrap gap-2 mb-3">
              {COLOR_PRESETS.map((c) => {
                const active = color.toLowerCase() === c.toLowerCase()
                return (
                  <button
                    key={c}
                    onClick={() => setColor(c)}
                    title={c}
                    className="rounded-md transition-all"
                    style={{
                      width: 32, height: 32,
                      background: c,
                      border: `2px solid ${active ? 'var(--text-primary)' : 'transparent'}`,
                      transform: active ? 'scale(1.06)' : 'scale(1)',
                    }}
                  />
                )
              })}
            </div>
            <Field label="Custom hex (optional)">
              <input
                className="cma-input font-mono"
                value={color}
                onChange={(e) => {
                  const v = e.target.value.trim()
                  setColor(/^#?[0-9a-f]{6}$/i.test(v) ? (v.startsWith('#') ? v : `#${v}`) : v)
                }}
                placeholder="#004977"
                maxLength={7}
              />
            </Field>
          </Section>

          {/* ── Review */}
          <Section title="Review">
            <div
              className="rounded-xl p-4 flex items-start gap-3"
              style={{
                background: 'var(--bg-elevated)',
                border: `1px dashed ${color}`,
              }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: `${color}1A`, color }}
              >
                <ActiveIcon size={18} />
              </div>
              <div className="flex-1 min-w-0">
                <div
                  className="font-display text-base font-semibold"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {name.trim() || 'Workspace name'}
                </div>
                <div className="text-[11px] mb-1" style={{ color: 'var(--text-muted)' }}>
                  <span style={{ color }}>{shortName || name.split(/\s+/)[0] || '—'}</span>
                  <span className="mx-1.5">·</span>
                  <span>{effectiveCategory || 'no category'}</span>
                  <span className="mx-1.5">·</span>
                  <span className="font-mono">{previewId}</span>
                </div>
                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {description.trim()
                    || 'No description yet — add one to give analysts context.'}
                </div>
              </div>
            </div>
            <div
              className="text-[11px] mt-3 flex items-start gap-1.5"
              style={{ color: 'var(--text-muted)' }}
            >
              <Sparkles size={11} className="mt-0.5 shrink-0" />
              <span>
                The new workspace opens empty. Bind datasets in <strong>Data</strong>,
                build models in <strong>Models</strong>, design tiles in <strong>Reporting</strong>,
                and the Overview will populate as you pin them.
              </span>
            </div>
          </Section>

          {error && (
            <div
              className="text-sm px-3 py-2 rounded-md"
              style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
            >
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="px-6 py-3 flex items-center justify-between gap-2"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
            <Plus size={11} className="inline mr-1" />
            <span>Stored in-memory; resets on backend restart.</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-2 text-xs rounded-lg"
              style={{ color: 'var(--text-muted)' }}
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={saving || !name.trim() || !effectiveCategory}
              className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all disabled:opacity-40"
              style={{ background: color, color: '#fff' }}
            >
              {saving ? 'Creating…' : 'Create workspace'} <ArrowRight size={12} />
            </button>
          </div>
        </div>
      </div>

      {/* Local input style so we don't have to add to global CSS */}
      <style>{`
        .cma-input {
          width: 100%; padding: 8px 10px; border-radius: 8px; font-size: 13px;
          background: var(--bg-elevated);
          border: 1px solid var(--border);
          color: var(--text-primary);
          outline: none;
        }
        .cma-input:focus {
          border-color: var(--accent);
          background: var(--bg-card);
        }
      `}</style>
    </>
  )
}

// ── Section + Field helpers ───────────────────────────────────────────────
function Section({
  title, subtitle, children,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div
        className="text-[10px] font-semibold uppercase tracking-widest mb-2"
        style={{ color: 'var(--text-secondary)' }}
      >
        {title}
      </div>
      {subtitle && (
        <div
          className="text-[11px] mb-3 -mt-1"
          style={{ color: 'var(--text-muted)' }}
        >
          {subtitle}
        </div>
      )}
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function Field({
  label, hint, required, children,
}: {
  label: string
  hint?: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <label className="block">
      <span
        className="block text-[11px] font-semibold uppercase tracking-widest mb-1"
        style={{ color: 'var(--text-secondary)' }}
      >
        {label}{required && <span style={{ color: 'var(--error)' }}> *</span>}
      </span>
      {children}
      {hint && (
        <div className="text-[11px] mt-1" style={{ color: 'var(--text-muted)' }}>
          {hint}
        </div>
      )}
    </label>
  )
}
