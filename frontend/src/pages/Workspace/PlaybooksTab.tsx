/**
 * Playbooks tab — analyst-defined agentic workflows.
 *
 * Layout: a left rail of saved playbooks + the function's published reports,
 * a right pane that switches between Editor (designing a playbook) and Run
 * (executing one and reviewing results phase-by-phase with gate UI).
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ListChecks, Plus, Trash2, X, Play, BookOpen, Save, Download, Send, Sparkles,
  CheckCircle2, AlertCircle, Loader2, ArrowRight, Database, FlaskConical, Type,
  Pencil, Pin, FileText, Wrench, MessageSquare, Brain, ChevronRight, ChevronDown,
  Settings as SettingsIcon, ExternalLink,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import api from '@/lib/api'
import type {
  Dataset, Scenario, Playbook, PlaybookPhase, PlaybookPhaseInput, PlaybookRun,
  PhaseExecution, PublishedReport, PlaybookSkill, TraceStep,
} from '@/types'

interface Props {
  functionId: string
  functionName: string
  onAskAgent: (q: string) => void
  onContextChange: (ctx: string | null) => void
}

type RightView =
  | { kind: 'idle' }
  | { kind: 'editor', playbook: Playbook | 'new' }
  | { kind: 'run', runId: string }
  | { kind: 'report', report: PublishedReport }

const INPUT_KIND_META: Record<PlaybookPhaseInput['kind'], { label: string; icon: any; color: string }> = {
  dataset:       { label: 'Dataset',       icon: Database,    color: '#059669' },
  scenario:      { label: 'Scenario',      icon: FlaskConical, color: '#0891B2' },
  phase_output:  { label: 'Phase Output',  icon: ArrowRight,   color: '#7C3AED' },
  prompt:        { label: 'Free-text',     icon: Type,         color: '#D97706' },
}

/** Convert a kebab-case skill name into a human-readable phase name, e.g.
 *  "mbs-decomposition-specialist" → "MBS Decomposition Specialist". */
function skillDisplayName(skill: string): string {
  if (!skill) return ''
  return skill
    .split('-')
    .map((w) => (w === 'mbs' || w === 'cmbs' || w === 'rv' || w === 'oas' || w === 'kpi'
      ? w.toUpperCase()
      : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(' ')
}

/** Was this phase name auto-generated (i.e. should it follow the skill)?
 *  True when name is empty, matches "Phase N", or matches the display name
 *  of any known skill. False once the user types a custom name. */
function isAutoPhaseName(name: string, skills: PlaybookSkill[]): boolean {
  if (!name || !name.trim()) return true
  if (/^Phase \d+$/i.test(name.trim())) return true
  const known = new Set(skills.map((s) => skillDisplayName(s.name)))
  return known.has(name.trim())
}

export default function PlaybooksTab({ functionId, functionName, onAskAgent, onContextChange }: Props) {
  const navigate = useNavigate()
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [published, setPublished] = useState<PublishedReport[]>([])
  const [skills, setSkills] = useState<PlaybookSkill[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [right, setRight] = useState<RightView>({ kind: 'idle' })

  const load = () => {
    Promise.all([
      api.get<Playbook[]>('/api/playbooks', { params: { function_id: functionId } }),
      api.get<PublishedReport[]>('/api/playbooks/published', { params: { function_id: functionId } }),
      api.get<PlaybookSkill[]>('/api/playbooks/_skills'),
      api.get<Dataset[]>('/api/datasets', { params: { function_id: functionId } }),
      api.get<Scenario[]>('/api/analytics/scenarios', { params: { function_id: functionId } }),
    ]).then(([pb, pub, sk, ds, sc]) => {
      setPlaybooks(pb.data); setPublished(pub.data); setSkills(sk.data)
      setDatasets(ds.data); setScenarios(sc.data)
    })
  }
  useEffect(load, [functionId])

  useEffect(() => {
    onContextChange(`${functionName} (Playbooks): ${playbooks.length} playbooks, ${published.length} published`)
    return () => onContextChange(null)
  }, [playbooks.length, published.length, functionName, onContextChange])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4" style={{ minHeight: 600 }}>
      {/* Left rail */}
      <div className="lg:col-span-1 space-y-3">
        <div className="panel" style={{ padding: 12 }}>
          <div className="flex items-center justify-between mb-2">
            <span className="section-title" style={{ marginBottom: 0 }}>Playbooks ({playbooks.length})</span>
            <button
              onClick={() => setRight({ kind: 'editor', playbook: 'new' })}
              className="px-2 py-1 rounded-md text-[11px] font-semibold flex items-center gap-1"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              <Plus size={11} /> New
            </button>
          </div>
          {playbooks.length === 0 && (
            <div className="text-[11px] py-2" style={{ color: 'var(--text-muted)' }}>
              No playbooks yet. Create one to compose agent skills into a phased workflow.
            </div>
          )}
          <div className="space-y-1">
            {playbooks.map((p) => {
              const isOpen = right.kind === 'editor' && right.playbook !== 'new' && right.playbook.id === p.id
              return (
                <button
                  key={p.id}
                  onClick={() => setRight({ kind: 'editor', playbook: p })}
                  className="w-full text-left rounded-md transition-colors"
                  style={{
                    padding: '6px 8px',
                    background: isOpen ? 'var(--accent-light)' : 'transparent',
                    border: `1px solid ${isOpen ? 'var(--accent)' : 'var(--border)'}`,
                  }}
                >
                  <div className="text-[12px] font-semibold truncate" style={{ color: isOpen ? 'var(--accent)' : 'var(--text-primary)' }}>
                    {p.name}
                  </div>
                  <div className="text-[10px] truncate" style={{ color: 'var(--text-muted)' }}>
                    {p.phases.length} phase{p.phases.length === 1 ? '' : 's'}
                    {p.description ? ' · ' + p.description : ''}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <button
          onClick={() => navigate('/settings/skills')}
          className="panel w-full text-left transition-colors"
          style={{
            padding: 12,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
          title="Open Settings → Agent Skills"
          onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)')}
          onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.borderColor = '')}
        >
          <div
            className="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
            style={{ background: 'rgba(8,145,178,0.12)', color: 'var(--accent)' }}
          >
            <Wrench size={14} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[12px] font-semibold flex items-center gap-1" style={{ color: 'var(--text-primary)' }}>
              Manage agent skills <ExternalLink size={10} style={{ color: 'var(--text-muted)' }} />
            </div>
            <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              Add or edit the agents you can drop into a phase.
            </div>
          </div>
        </button>

        <div className="panel" style={{ padding: 12 }}>
          <div className="section-title">Published ({published.length})</div>
          {published.length === 0 && (
            <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              Publish a completed run to share its report with the function.
            </div>
          )}
          <div className="space-y-1">
            {published.slice(0, 8).map((r) => (
              <button
                key={r.id}
                onClick={() => setRight({ kind: 'report', report: r })}
                className="w-full text-left rounded-md px-2 py-1 transition-colors"
                style={{ border: '1px solid transparent' }}
                onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = 'var(--bg-elevated)')}
                onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
              >
                <div className="text-[12px] font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                  {r.title}
                </div>
                <div className="text-[10px] truncate" style={{ color: 'var(--text-muted)' }}>
                  by {r.published_by} · {new Date(r.published_at).toLocaleDateString()}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right pane */}
      <div className="lg:col-span-3">
        {right.kind === 'idle' && (
          <EmptyHint onNew={() => setRight({ kind: 'editor', playbook: 'new' })} hasPlaybooks={playbooks.length > 0} />
        )}
        {right.kind === 'editor' && (
          <PlaybookEditor
            functionId={functionId}
            playbook={right.playbook === 'new' ? null : right.playbook}
            skills={skills}
            datasets={datasets}
            scenarios={scenarios}
            onClose={() => setRight({ kind: 'idle' })}
            onSaved={(saved) => { load(); setRight({ kind: 'editor', playbook: saved }) }}
            onRunStarted={(runId) => setRight({ kind: 'run', runId })}
          />
        )}
        {right.kind === 'run' && (
          <RunView
            runId={right.runId}
            datasets={datasets}
            scenarios={scenarios}
            onClose={() => { load(); setRight({ kind: 'idle' }) }}
            onPublished={() => { load() }}
          />
        )}
        {right.kind === 'report' && (
          <ReportView report={right.report} onClose={() => setRight({ kind: 'idle' })} />
        )}
      </div>
    </div>
  )
}

// ── Empty hint ─────────────────────────────────────────────────────────
function EmptyHint({ onNew, hasPlaybooks }: { onNew: () => void; hasPlaybooks: boolean }) {
  return (
    <div className="panel text-center" style={{ padding: '60px 20px', borderStyle: 'dashed' }}>
      <BookOpen size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
      <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
        {hasPlaybooks ? 'Pick a playbook on the left' : 'No playbooks yet'}
      </div>
      <div className="text-xs mt-1 mb-4 max-w-md mx-auto" style={{ color: 'var(--text-muted)' }}>
        A playbook is an ordered set of phases. Each phase is one agent skill (from{' '}
        <strong>Settings → Agent Skills</strong>) running with inputs you choose — datasets,
        scenarios, prior phase outputs, or free-text prompts. Add a gate to pause for review.
      </div>
      <button
        onClick={onNew}
        className="px-3 py-2 rounded-lg text-xs font-semibold"
        style={{ background: 'var(--accent)', color: '#fff' }}
      >
        <Plus size={13} className="inline mr-1" /> New Playbook
      </button>
    </div>
  )
}

// ── Editor ─────────────────────────────────────────────────────────────
function PlaybookEditor({
  functionId, playbook, skills, datasets, scenarios,
  onClose, onSaved, onRunStarted,
}: {
  functionId: string
  playbook: Playbook | null
  skills: PlaybookSkill[]
  datasets: Dataset[]
  scenarios: Scenario[]
  onClose: () => void
  onSaved: (saved: Playbook) => void
  onRunStarted: (runId: string) => void
}) {
  const isNew = !playbook
  const [name, setName] = useState(playbook?.name || '')
  const [description, setDescription] = useState(playbook?.description || '')
  const [phases, setPhases] = useState<PlaybookPhase[]>(playbook?.phases || [])
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset when switching playbooks
  useEffect(() => {
    setName(playbook?.name || '')
    setDescription(playbook?.description || '')
    setPhases(playbook?.phases || [])
    setError(null)
  }, [playbook?.id])

  const addPhase = () => {
    const idx = phases.length + 1
    const firstSkill = skills[0]?.name || ''
    setPhases((ps) => [
      ...ps,
      {
        id: `phase-${idx}`,
        name: firstSkill ? skillDisplayName(firstSkill) : `Phase ${idx}`,
        skill_name: firstSkill,
        instructions: '',
        inputs: [],
        gate: false,
      },
    ])
  }

  const updatePhase = (idx: number, patch: Partial<PlaybookPhase>) => {
    setPhases((ps) => ps.map((p, i) => (i === idx ? { ...p, ...patch } : p)))
  }

  const removePhase = (idx: number) => {
    setPhases((ps) => ps.filter((_, i) => i !== idx).map((p, i) => ({ ...p, id: `phase-${i + 1}` })))
  }

  const movePhase = (idx: number, dir: -1 | 1) => {
    setPhases((ps) => {
      const j = idx + dir
      if (j < 0 || j >= ps.length) return ps
      const out = [...ps]
      const [removed] = out.splice(idx, 1)
      out.splice(j, 0, removed)
      // Re-id sequentially
      return out.map((p, i) => ({ ...p, id: `phase-${i + 1}` }))
    })
  }

  const save = async () => {
    if (!name) { setError('Name required'); return }
    if (phases.length === 0) { setError('At least one phase required'); return }
    setSaving(true); setError(null)
    try {
      const body = { function_id: functionId, name, description, phases }
      const r = isNew
        ? await api.post<Playbook>('/api/playbooks', body)
        : await api.patch<Playbook>(`/api/playbooks/${playbook!.id}`, body)
      onSaved(r.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const runNow = async () => {
    if (phases.length === 0) { setError('Add at least one phase before running.'); return }
    if (!name.trim()) { setError('Name the playbook before running.'); return }
    setRunning(true); setError(null)
    try {
      // Auto-save (create or update) so the latest phases run, even if the user hasn't clicked Save.
      const body = { function_id: functionId, name, description, phases }
      const saved = isNew
        ? (await api.post<Playbook>('/api/playbooks', body)).data
        : (await api.patch<Playbook>(`/api/playbooks/${playbook!.id}`, body)).data
      onSaved(saved)
      const r = await api.post<PlaybookRun>(`/api/playbooks/${saved.id}/run`)
      onRunStarted(r.data.id)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Run failed')
    } finally {
      setRunning(false)
    }
  }

  const remove = async () => {
    if (isNew) return
    if (!confirm(`Delete playbook "${playbook!.name}"?`)) return
    await api.delete(`/api/playbooks/${playbook!.id}`)
    onClose()
  }

  return (
    <div className="panel" style={{ padding: 18 }}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Playbook name"
            className="font-display text-xl font-bold w-full"
            style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-primary)' }}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="One-line description (optional)"
            className="text-xs w-full mt-0.5"
            style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-muted)' }}
          />
        </div>
        <div className="flex gap-1.5 shrink-0">
          {!isNew && (
            <button
              onClick={remove}
              className="px-2 py-1.5 rounded-md text-xs"
              style={{ color: 'var(--text-muted)' }}
              title="Delete playbook"
            >
              <Trash2 size={13} />
            </button>
          )}
          <button
            onClick={save}
            disabled={saving}
            className="px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1 disabled:opacity-40"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            <Save size={12} /> {saving ? 'Saving…' : 'Save'}
          </button>
          <button
            onClick={runNow}
            disabled={running || saving || phases.length === 0 || !name.trim()}
            title={
              phases.length === 0
                ? 'Add at least one phase before running'
                : !name.trim()
                ? 'Name the playbook before running'
                : isNew
                ? 'Saves the playbook, then runs it'
                : 'Run this playbook'
            }
            className="px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1 disabled:opacity-40"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            <Play size={12} /> {running ? 'Running…' : 'Run'}
          </button>
        </div>
      </div>

      <div className="space-y-3 mt-2">
        {phases.length === 0 && (
          <div className="text-xs" style={{ color: 'var(--text-muted)', padding: '20px 0', textAlign: 'center' }}>
            No phases yet. Add the first phase to start composing.
          </div>
        )}
        {phases.map((phase, idx) => (
          <PhaseEditor
            key={phase.id}
            idx={idx}
            phase={phase}
            allPhases={phases}
            skills={skills}
            datasets={datasets}
            scenarios={scenarios}
            onChange={(patch) => updatePhase(idx, patch)}
            onRemove={() => removePhase(idx)}
            onMoveUp={idx > 0 ? () => movePhase(idx, -1) : undefined}
            onMoveDown={idx < phases.length - 1 ? () => movePhase(idx, 1) : undefined}
          />
        ))}
      </div>

      <button
        onClick={addPhase}
        disabled={skills.length === 0}
        className="mt-3 w-full py-2 rounded-md text-xs font-semibold flex items-center justify-center gap-1 disabled:opacity-40"
        style={{
          background: 'var(--bg-elevated)', border: '1.5px dashed var(--border)',
          color: 'var(--text-secondary)',
        }}
      >
        <Plus size={12} /> Add Phase
      </button>

      {error && (
        <div
          className="mt-3 px-3 py-2 rounded-md text-xs"
          style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
        >
          {error}
        </div>
      )}

      <style>{`
        .phase-input {
          width: 100%; padding: 6px 10px; border-radius: 8px; font-size: 12px;
          background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);
        }
      `}</style>
    </div>
  )
}

// ── single phase editor ───────────────────────────────────────────────
function PhaseEditor({
  idx, phase, allPhases, skills, datasets, scenarios,
  onChange, onRemove, onMoveUp, onMoveDown,
}: {
  idx: number
  phase: PlaybookPhase
  allPhases: PlaybookPhase[]
  skills: PlaybookSkill[]
  datasets: Dataset[]
  scenarios: Scenario[]
  onChange: (patch: Partial<PlaybookPhase>) => void
  onRemove: () => void
  onMoveUp?: () => void
  onMoveDown?: () => void
}) {
  const [showAddInput, setShowAddInput] = useState(false)
  const earlierPhases = allPhases.slice(0, idx)

  const addInput = (kind: PlaybookPhaseInput['kind'], ref?: string, text?: string) => {
    const next: PlaybookPhaseInput = { kind, ref_id: ref || null, text: text || null }
    onChange({ inputs: [...phase.inputs, next] })
    setShowAddInput(false)
  }

  const removeInput = (i: number) => {
    onChange({ inputs: phase.inputs.filter((_, j) => j !== i) })
  }

  return (
    <div
      className="rounded-lg"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', padding: 12 }}
    >
      <div className="flex items-start gap-2">
        <div
          className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 font-mono text-sm font-bold"
          style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
        >
          {idx + 1}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <input
              value={phase.name}
              onChange={(e) => onChange({ name: e.target.value })}
              className="phase-input flex-1"
              placeholder="Phase name"
              style={{ fontWeight: 600 }}
            />
            <select
              value={phase.skill_name}
              onChange={(e) => {
                const newSkill = e.target.value
                const patch: Partial<PlaybookPhase> = { skill_name: newSkill }
                if (isAutoPhaseName(phase.name, skills)) {
                  patch.name = skillDisplayName(newSkill)
                }
                onChange(patch)
              }}
              className="phase-input"
              style={{ width: 240 }}
            >
              {(() => {
                const userSkills = skills.filter((s) => s.source === 'user')
                const builtinSkills = skills.filter((s) => (s.source ?? 'builtin') === 'builtin')
                // Group pack skills by pack_id — one optgroup per pack so the
                // dropdown stays scannable as the number of domains grows.
                const packed = new Map<string, typeof skills>()
                for (const s of skills) {
                  if (s.source !== 'pack') continue
                  const pid = s.pack_id || 'unknown'
                  if (!packed.has(pid)) packed.set(pid, [])
                  packed.get(pid)!.push(s)
                }
                return (
                  <>
                    {userSkills.length > 0 && (
                      <optgroup label="★ Your customized agents">
                        {userSkills.map((s) => (
                          <option key={s.name} value={s.name}>{s.name}</option>
                        ))}
                      </optgroup>
                    )}
                    {Array.from(packed.keys()).sort().map((pid) => (
                      <optgroup key={pid} label={`◆ Domain pack — ${pid}`}>
                        {packed.get(pid)!.map((s) => (
                          <option key={s.name} value={s.name}>{s.name}</option>
                        ))}
                      </optgroup>
                    ))}
                    {builtinSkills.length > 0 && (
                      <optgroup label="Built-in agents">
                        {builtinSkills.map((s) => (
                          <option key={s.name} value={s.name}>{s.name}</option>
                        ))}
                      </optgroup>
                    )}
                  </>
                )
              })()}
            </select>
            <label
              className="flex items-center gap-1 text-[11px] shrink-0 cursor-pointer"
              style={{ color: phase.gate ? 'var(--accent)' : 'var(--text-muted)' }}
              title="Pause for analyst approve / modify / reject before continuing"
            >
              <input
                type="checkbox"
                checked={phase.gate}
                onChange={(e) => onChange({ gate: e.target.checked })}
              />
              gate
            </label>
            <button
              onClick={onRemove}
              className="p-1 rounded-md"
              style={{ color: 'var(--text-muted)' }}
              title="Remove phase"
            >
              <Trash2 size={11} />
            </button>
            <div className="flex flex-col">
              {onMoveUp && (
                <button onClick={onMoveUp} className="text-[10px]" style={{ color: 'var(--text-muted)' }} title="Move up">▲</button>
              )}
              {onMoveDown && (
                <button onClick={onMoveDown} className="text-[10px]" style={{ color: 'var(--text-muted)' }} title="Move down">▼</button>
              )}
            </div>
          </div>

          <textarea
            value={phase.instructions || ''}
            onChange={(e) => onChange({ instructions: e.target.value })}
            placeholder="Instructions to the agent (overrides default user message). Optional."
            rows={2}
            className="phase-input resize-none"
          />

          <div className="mt-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
                Inputs ({phase.inputs.length})
              </span>
              {!showAddInput && (
                <button
                  onClick={() => setShowAddInput(true)}
                  className="text-[10px] flex items-center gap-1"
                  style={{ color: 'var(--accent)', fontWeight: 600 }}
                >
                  <Plus size={10} /> add
                </button>
              )}
            </div>
            {phase.inputs.length === 0 && !showAddInput && (
              <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                No inputs. The agent will use only the system prompt and instructions.
              </div>
            )}
            <div className="flex flex-wrap gap-1 mb-1">
              {phase.inputs.map((inp, i) => (
                <InputChip key={i} input={inp} datasets={datasets} scenarios={scenarios} earlierPhases={earlierPhases} onRemove={() => removeInput(i)} />
              ))}
            </div>
            {showAddInput && (
              <AddInputPicker
                datasets={datasets}
                scenarios={scenarios}
                earlierPhases={earlierPhases}
                onAdd={(kind, ref, text) => addInput(kind, ref, text)}
                onClose={() => setShowAddInput(false)}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function InputChip({
  input, datasets, scenarios, earlierPhases, onRemove,
}: {
  input: PlaybookPhaseInput
  datasets: Dataset[]
  scenarios: Scenario[]
  earlierPhases: PlaybookPhase[]
  onRemove: () => void
}) {
  const meta = INPUT_KIND_META[input.kind]
  const Icon = meta.icon
  const label = (() => {
    if (input.kind === 'dataset') return datasets.find((d) => d.id === input.ref_id)?.name || input.ref_id || '?'
    if (input.kind === 'scenario') return scenarios.find((s) => s.id === input.ref_id)?.name || input.ref_id || '?'
    if (input.kind === 'phase_output') {
      const ph = earlierPhases.find((p) => p.id === input.ref_id)
      return ph ? `${ph.id}: ${ph.name}` : input.ref_id || '?'
    }
    return (input.text || '').slice(0, 40) + ((input.text || '').length > 40 ? '…' : '')
  })()
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px]"
      style={{ background: `${meta.color}1A`, color: meta.color, border: `1px solid ${meta.color}40` }}
    >
      <Icon size={10} />
      <span className="font-medium">{meta.label}: {label}</span>
      <button onClick={onRemove} style={{ color: meta.color, opacity: 0.6 }}>
        <X size={10} />
      </button>
    </span>
  )
}

function AddInputPicker({
  datasets, scenarios, earlierPhases, onAdd, onClose,
}: {
  datasets: Dataset[]
  scenarios: Scenario[]
  earlierPhases: PlaybookPhase[]
  onAdd: (kind: PlaybookPhaseInput['kind'], ref?: string, text?: string) => void
  onClose: () => void
}) {
  const [tab, setTab] = useState<'dataset' | 'scenario' | 'phase' | 'prompt'>('dataset')
  const [text, setText] = useState('')
  return (
    <div
      className="rounded-md p-2"
      style={{ background: 'var(--bg-elevated)', border: '1px solid var(--accent)' }}
    >
      <div className="flex items-center gap-1 mb-2">
        {([
          { id: 'dataset',  l: 'Dataset',  I: Database },
          { id: 'scenario', l: 'Scenario', I: FlaskConical },
          { id: 'phase',    l: 'Phase output', I: ArrowRight },
          { id: 'prompt',   l: 'Free-text', I: Type },
        ] as const).map(({ id, l, I }) => {
          const active = tab === id
          return (
            <button
              key={id}
              onClick={() => setTab(id as any)}
              className="px-2 py-1 rounded-md text-[10px] font-semibold flex items-center gap-1"
              style={{
                background: active ? 'var(--bg-card)' : 'transparent',
                color: active ? 'var(--accent)' : 'var(--text-secondary)',
                border: `1px solid ${active ? 'var(--accent)' : 'transparent'}`,
              }}
            >
              <I size={10} /> {l}
            </button>
          )
        })}
        <button onClick={onClose} className="ml-auto text-[10px]" style={{ color: 'var(--text-muted)' }}>
          cancel
        </button>
      </div>
      {tab === 'dataset' && (
        <select onChange={(e) => e.target.value && onAdd('dataset', e.target.value)} className="phase-input" defaultValue="">
          <option value="">Pick a dataset…</option>
          {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      )}
      {tab === 'scenario' && (
        <select onChange={(e) => e.target.value && onAdd('scenario', e.target.value)} className="phase-input" defaultValue="">
          <option value="">Pick a scenario…</option>
          {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.severity})</option>)}
        </select>
      )}
      {tab === 'phase' && (
        <select onChange={(e) => e.target.value && onAdd('phase_output', e.target.value)} className="phase-input" defaultValue="">
          <option value="">Pick an earlier phase…</option>
          {earlierPhases.map((p) => <option key={p.id} value={p.id}>{p.id}: {p.name}</option>)}
        </select>
      )}
      {tab === 'prompt' && (
        <div className="space-y-1">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Free-text prompt to add to the agent context"
            rows={2}
            className="phase-input resize-none"
          />
          <button
            onClick={() => { if (text.trim()) { onAdd('prompt', undefined, text.trim()); setText('') } }}
            disabled={!text.trim()}
            className="px-2 py-1 rounded-md text-[10px] font-semibold disabled:opacity-40"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            Add prompt
          </button>
        </div>
      )}
    </div>
  )
}

// ── Run viewer ────────────────────────────────────────────────────────
function RunView({
  runId, datasets, scenarios, onClose, onPublished,
}: {
  runId: string
  datasets: Dataset[]
  scenarios: Scenario[]
  onClose: () => void
  onPublished: () => void
}) {
  const [run, setRun] = useState<PlaybookRun | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [publishTitle, setPublishTitle] = useState('')
  const [publishing, setPublishing] = useState(false)
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchRun = async () => {
    try {
      const r = await api.get<PlaybookRun>(`/api/playbooks/runs/${runId}`)
      setRun(r.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not fetch run')
    }
  }

  useEffect(() => { fetchRun() }, [runId])

  // Light polling while a phase is running (not at gate; gates are user-driven)
  useEffect(() => {
    if (!run) return
    if (run.status === 'running') {
      // Tight polling while phases stream in trace steps live.
      pollTimer.current = setInterval(fetchRun, 800)
    } else if (pollTimer.current) {
      clearInterval(pollTimer.current); pollTimer.current = null
    }
    return () => {
      if (pollTimer.current) { clearInterval(pollTimer.current); pollTimer.current = null }
    }
  }, [run?.status])

  const submitGate = async (decision: 'approve' | 'modify' | 'reject', notes?: string, modified_output?: string) => {
    try {
      const r = await api.post<PlaybookRun>(`/api/playbooks/runs/${runId}/gate`, {
        decision, notes: notes || null, modified_output: modified_output || null,
      })
      setRun(r.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Gate decision failed')
    }
  }

  const publish = async () => {
    setPublishing(true)
    try {
      await api.post(`/api/playbooks/runs/${runId}/publish`, { title: publishTitle || null })
      onPublished()
      alert('Published.')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Publish failed')
    } finally {
      setPublishing(false)
    }
  }

  const downloadHTML = () => {
    if (!run) return
    const md = run.final_report || ''
    const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${run.playbook_name}</title>
<style>
  body { font-family: 'Instrument Sans', system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #0B0F19; line-height: 1.6; }
  h1, h2, h3 { font-family: 'Playfair Display', Georgia, serif; }
  h1 { border-bottom: 2px solid #004977; padding-bottom: 8px; }
  h2 { color: #004977; margin-top: 32px; }
  blockquote { border-left: 3px solid #004977; padding-left: 12px; color: #2C384A; margin: 12px 0; }
  code { background: #F0F2F5; padding: 1px 5px; border-radius: 3px; font-family: monospace; }
  pre { background: #F0F2F5; padding: 12px; border-radius: 6px; overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
  th, td { border: 1px solid #D8DBE0; padding: 4px 8px; text-align: left; }
  th { background: #004977; color: white; }
</style></head>
<body>
${markdownToHTML(md)}
<hr style="margin-top:40px;border:none;border-top:1px solid #D8DBE0;">
<p style="font-size:11px;color:#768192;text-align:center;">
  CMA Workbench Playbook · ${new Date().toLocaleString()} · run ${run.id}
</p>
</body></html>`
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${run.playbook_name.replace(/[^a-z0-9]+/gi, '_')}-${run.id}.html`
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
  }

  const downloadJSON = () => {
    if (!run) return
    const blob = new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${run.playbook_name.replace(/[^a-z0-9]+/gi, '_')}-${run.id}.json`
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
  }

  if (!run) {
    return (
      <div className="panel" style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)' }}>
        {error || (
          <span className="flex items-center gap-2 justify-center"><Loader2 size={14} className="animate-spin" /> Loading run…</span>
        )}
      </div>
    )
  }

  const done = run.status === 'completed' || run.status === 'rejected'

  return (
    <div className="panel" style={{ padding: 18 }}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="font-display text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            {run.playbook_name}
          </div>
          <div className="text-[11px] mt-0.5 font-mono" style={{ color: 'var(--text-muted)' }}>
            run {run.id} · started {new Date(run.created_at).toLocaleString()}
          </div>
        </div>
        <div className="flex gap-1.5 shrink-0">
          {done && (
            <>
              <button
                onClick={downloadJSON}
                className="px-2 py-1.5 rounded-md text-xs flex items-center gap-1"
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              >
                <Download size={11} /> JSON
              </button>
              <button
                onClick={downloadHTML}
                className="px-2 py-1.5 rounded-md text-xs flex items-center gap-1"
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              >
                <Download size={11} /> HTML
              </button>
            </>
          )}
          <button
            onClick={onClose}
            className="p-1.5 rounded-md"
            style={{ color: 'var(--text-muted)' }}
            title="Close run"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      <RunStatusBanner run={run} />

      <div className="space-y-3 mt-3">
        {run.phases.map((pe, i) => (
          <PhaseRunCard
            key={pe.phase_id}
            idx={i}
            phase={pe}
            isCurrent={
              i === run.current_phase_idx &&
              (run.status === 'awaiting_gate' || run.status === 'running')
            }
            onGate={submitGate}
          />
        ))}
        {run.status === 'running' && run.current_phase_idx < (run.phases.length || 99) && (
          <div className="panel flex items-center gap-2 text-xs" style={{ padding: 10, color: 'var(--text-muted)' }}>
            <Loader2 size={12} className="animate-spin" />
            Running phase {run.current_phase_idx + 1}…
          </div>
        )}
      </div>

      {done && run.final_report && (
        <div className="mt-4">
          <div className="section-title">Final Report</div>
          <div
            className="panel"
            style={{ padding: 18 }}
          >
            <MarkdownBody md={run.final_report} />
          </div>

          {run.status === 'completed' && (
            <div
              className="mt-3 p-3 rounded-lg flex items-center gap-2"
              style={{ background: 'var(--accent-light)', border: '1px solid var(--accent)' }}
            >
              <Pin size={14} style={{ color: 'var(--accent)' }} />
              <input
                value={publishTitle}
                onChange={(e) => setPublishTitle(e.target.value)}
                placeholder={`Title (default: ${run.playbook_name})`}
                className="flex-1 phase-input"
                style={{ background: 'var(--bg-card)' }}
              />
              <button
                onClick={publish}
                disabled={publishing}
                className="px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1 disabled:opacity-40"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                <Send size={11} /> {publishing ? 'Publishing…' : 'Publish'}
              </button>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="mt-3 px-3 py-2 rounded-md text-xs" style={{ background: 'var(--error-bg)', color: 'var(--error)' }}>
          {error}
        </div>
      )}

      <style>{`
        .phase-input {
          width: 100%; padding: 6px 10px; border-radius: 8px; font-size: 12px;
          background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);
        }
      `}</style>
    </div>
  )
}

function RunStatusBanner({ run }: { run: PlaybookRun }) {
  const map: Record<PlaybookRun['status'], { label: string; color: string; bg: string; icon: any }> = {
    running:        { label: 'Running…',        color: 'var(--accent)',  bg: 'var(--accent-light)', icon: Loader2 },
    awaiting_gate:  { label: 'Awaiting gate',   color: 'var(--warning)', bg: 'var(--warning-bg)',   icon: AlertCircle },
    completed:      { label: 'Completed',       color: 'var(--success)', bg: 'var(--success-bg)',   icon: CheckCircle2 },
    rejected:       { label: 'Rejected',        color: 'var(--error)',   bg: 'var(--error-bg)',     icon: AlertCircle },
    failed:         { label: 'Failed',          color: 'var(--error)',   bg: 'var(--error-bg)',     icon: AlertCircle },
  }
  const m = map[run.status]
  const Icon = m.icon
  const completedPhases = run.phases.filter((p) => p.status === 'completed' || p.status === 'rejected').length
  return (
    <div
      className="px-3 py-2 rounded-md flex items-center gap-2 text-xs"
      style={{ background: m.bg, color: m.color, fontWeight: 600 }}
    >
      <Icon size={13} className={run.status === 'running' ? 'animate-spin' : ''} />
      {m.label}
      <span className="font-mono opacity-70 ml-2">
        {completedPhases} / {run.phases.length || '?'} phases done
      </span>
    </div>
  )
}

// ── Agent reasoning trace ─────────────────────────────────────────────
function TracePanel({ trace }: { trace: TraceStep[] }) {
  const [collapsed, setCollapsed] = useState(false)
  const [openSteps, setOpenSteps] = useState<Record<number, boolean>>({})

  const toolCalls = trace.filter((s) => s.kind === 'tool_call').length
  const handoffs = trace.filter((s) => s.kind === 'handoff').length

  const meta: Record<TraceStep['kind'], { color: string; bg: string; icon: any; label: string }> = {
    tool_call:    { color: 'var(--accent)',     bg: 'var(--accent-light)',  icon: Wrench,        label: 'TOOL CALL' },
    tool_output:  { color: 'var(--success)',    bg: 'var(--success-bg)',    icon: ArrowRight,    label: 'TOOL OUTPUT' },
    message:      { color: 'var(--text-primary)', bg: 'var(--bg-elevated)', icon: MessageSquare, label: 'MESSAGE' },
    reasoning:    { color: '#7C3AED',           bg: 'rgba(124,58,237,0.1)', icon: Brain,         label: 'REASONING' },
    handoff:      { color: 'var(--warning)',    bg: 'var(--warning-bg)',    icon: ArrowRight,    label: 'HANDOFF' },
    info:         { color: 'var(--text-muted)', bg: 'var(--bg-elevated)',   icon: AlertCircle,   label: 'INFO' },
  }

  return (
    <div
      className="mt-2"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }}
    >
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
        style={{ background: 'transparent' }}
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
        <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
          Reasoning trace
        </span>
        <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
          {trace.length} step{trace.length === 1 ? '' : 's'}
          {toolCalls > 0 ? ` · ${toolCalls} tool${toolCalls === 1 ? '' : 's'}` : ''}
          {handoffs > 0 ? ` · ${handoffs} handoff${handoffs === 1 ? '' : 's'}` : ''}
        </span>
      </button>
      {!collapsed && (
        <div className="px-3 pb-3 space-y-1.5">
          {trace.map((step, i) => {
            const m = meta[step.kind]
            const Icon = m.icon
            const hasDetail = !!step.detail && step.detail.trim().length > 0
            const isOpen = !!openSteps[i]
            return (
              <div
                key={i}
                className="rounded-md"
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}
              >
                <button
                  onClick={() => hasDetail && setOpenSteps((o) => ({ ...o, [i]: !o[i] }))}
                  disabled={!hasDetail}
                  className="w-full flex items-center gap-2 px-2 py-1.5 text-left"
                  style={{ background: 'transparent', cursor: hasDetail ? 'pointer' : 'default' }}
                >
                  <span
                    className="font-mono text-[9px] font-bold w-5 text-center"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {i + 1}
                  </span>
                  <span
                    className="px-1.5 py-0.5 rounded text-[9px] font-bold flex items-center gap-1"
                    style={{ background: m.bg, color: m.color }}
                  >
                    <Icon size={9} />
                    {m.label}
                  </span>
                  <span className="text-[11px] truncate flex-1" style={{ color: 'var(--text-primary)' }}>
                    {step.label}
                  </span>
                  {step.agent_name && (
                    <span className="text-[9px] font-mono" style={{ color: 'var(--text-muted)' }}>
                      {step.agent_name}
                    </span>
                  )}
                  {hasDetail && (
                    isOpen
                      ? <ChevronDown size={11} style={{ color: 'var(--text-muted)' }} />
                      : <ChevronRight size={11} style={{ color: 'var(--text-muted)' }} />
                  )}
                </button>
                {isOpen && hasDetail && (
                  <pre
                    className="text-[10px] font-mono whitespace-pre-wrap break-words px-2 pb-2 m-0"
                    style={{ color: 'var(--text-secondary)', maxHeight: 320, overflow: 'auto' }}
                  >
                    {step.detail}
                    {step.truncated && <span style={{ color: 'var(--text-muted)' }}>{'\n[truncated]'}</span>}
                  </pre>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function PhaseRunCard({
  idx, phase, isCurrent, onGate,
}: {
  idx: number
  phase: PhaseExecution
  isCurrent: boolean
  onGate: (decision: 'approve' | 'modify' | 'reject', notes?: string, modified_output?: string) => Promise<void>
}) {
  const [showModify, setShowModify] = useState(false)
  const [notes, setNotes] = useState('')
  const [modText, setModText] = useState(phase.output || '')
  const [open, setOpen] = useState(
    isCurrent ||
      phase.status === 'running' ||
      phase.status === 'failed' ||
      phase.status === 'rejected'
  )

  // Auto-expand the card when this phase becomes the active one (status flips
  // from idle to running, or run resumes after a gate). The user can still
  // collapse manually after that.
  useEffect(() => {
    if (phase.status === 'running' || phase.status === 'awaiting_gate' || phase.status === 'failed') {
      setOpen(true)
    }
  }, [phase.status])

  const statusMeta: Record<PhaseExecution['status'], { color: string; bg: string; label: string; icon: any }> = {
    idle:           { color: 'var(--text-muted)', bg: 'var(--bg-elevated)', label: 'IDLE', icon: AlertCircle },
    running:        { color: 'var(--accent)',     bg: 'var(--accent-light)', label: 'RUNNING', icon: Loader2 },
    awaiting_gate:  { color: 'var(--warning)',    bg: 'var(--warning-bg)',  label: 'AWAITING GATE', icon: AlertCircle },
    completed:      { color: 'var(--success)',    bg: 'var(--success-bg)',  label: 'DONE', icon: CheckCircle2 },
    rejected:       { color: 'var(--error)',      bg: 'var(--error-bg)',    label: 'REJECTED', icon: AlertCircle },
    failed:         { color: 'var(--error)',      bg: 'var(--error-bg)',    label: 'FAILED', icon: AlertCircle },
  }
  const m = statusMeta[phase.status]
  const Icon = m.icon

  return (
    <div
      className="rounded-lg"
      style={{ background: 'var(--bg-card)', border: `1px solid ${isCurrent ? 'var(--warning)' : 'var(--border)'}` }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-3 py-2 text-left"
        style={{ background: 'transparent' }}
      >
        <div
          className="w-7 h-7 rounded-md flex items-center justify-center font-mono text-xs font-bold"
          style={{ background: m.bg, color: m.color }}
        >
          {idx + 1}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
            {phase.phase_name}
          </div>
          <div className="text-[10px] truncate font-mono" style={{ color: 'var(--text-muted)' }}>
            skill: {phase.skill_name} · {phase.duration_ms.toFixed(0)} ms
          </div>
        </div>
        <span
          className="pill flex items-center gap-1"
          style={{ background: m.bg, color: m.color, fontSize: 9, fontWeight: 700, borderColor: 'transparent' }}
        >
          <Icon size={9} className={phase.status === 'running' ? 'animate-spin' : ''} />
          {m.label}
        </span>
      </button>

      {open && (
        <div className="px-3 pb-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          {phase.error && (
            <div className="mt-2 px-2 py-1.5 rounded-md text-[11px] font-mono" style={{ background: 'var(--error-bg)', color: 'var(--error)' }}>
              {phase.error}
            </div>
          )}
          {phase.trace && phase.trace.length > 0 && (
            <TracePanel trace={phase.trace} />
          )}
          {phase.output && (
            <div
              className="mt-2"
              style={{
                background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                borderRadius: 8, padding: 12,
              }}
            >
              <MarkdownBody md={phase.output} />
            </div>
          )}
          {phase.gate_decision && (
            <div
              className="mt-2 px-2 py-1.5 rounded-md text-[11px]"
              style={{
                background: phase.gate_decision === 'approve' ? 'var(--success-bg)' :
                            phase.gate_decision === 'reject' ? 'var(--error-bg)' : 'var(--warning-bg)',
                color: phase.gate_decision === 'approve' ? 'var(--success)' :
                       phase.gate_decision === 'reject' ? 'var(--error)' : 'var(--warning)',
              }}
            >
              <strong>Gate: {phase.gate_decision.toUpperCase()}</strong>
              {phase.gate_notes && ` — ${phase.gate_notes}`}
            </div>
          )}

          {isCurrent && phase.status === 'awaiting_gate' && (
            <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
              <div className="text-[11px] font-semibold uppercase tracking-widest mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                Gate decision
              </div>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional notes…"
                rows={2}
                className="phase-input resize-none mb-2"
              />
              {showModify && (
                <textarea
                  value={modText}
                  onChange={(e) => setModText(e.target.value)}
                  rows={6}
                  className="phase-input resize-y mb-2 font-mono"
                  style={{ fontSize: 11 }}
                />
              )}
              <div className="flex gap-1.5">
                <button
                  onClick={() => onGate('approve', notes)}
                  className="px-3 py-1.5 rounded-md text-xs font-semibold"
                  style={{ background: 'var(--success)', color: '#fff' }}
                >
                  ✓ Approve
                </button>
                {!showModify ? (
                  <button
                    onClick={() => setShowModify(true)}
                    className="px-3 py-1.5 rounded-md text-xs font-semibold"
                    style={{ background: 'var(--warning)', color: '#fff' }}
                  >
                    ✎ Modify
                  </button>
                ) : (
                  <button
                    onClick={() => onGate('modify', notes, modText)}
                    className="px-3 py-1.5 rounded-md text-xs font-semibold"
                    style={{ background: 'var(--warning)', color: '#fff' }}
                  >
                    Save modification & approve
                  </button>
                )}
                <button
                  onClick={() => onGate('reject', notes)}
                  className="px-3 py-1.5 rounded-md text-xs font-semibold"
                  style={{ background: 'var(--error)', color: '#fff' }}
                >
                  ✗ Reject
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      <style>{`
        .phase-input {
          width: 100%; padding: 6px 10px; border-radius: 8px; font-size: 12px;
          background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);
        }
      `}</style>
    </div>
  )
}

// ── Published report viewer ──────────────────────────────────────────
function ReportView({ report, onClose }: { report: PublishedReport; onClose: () => void }) {
  return (
    <div className="panel" style={{ padding: 18 }}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="font-display text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            {report.title}
          </div>
          <div className="text-[11px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {report.playbook_name} · published by {report.published_by} on {new Date(report.published_at).toLocaleString()}
          </div>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-md" style={{ color: 'var(--text-muted)' }}>
          <X size={13} />
        </button>
      </div>
      <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, padding: 18 }}>
        <MarkdownBody md={report.body_markdown} />
      </div>
    </div>
  )
}

// ── shared markdown renderer with consistent styling ─────────────────
function MarkdownBody({ md }: { md: string }) {
  return (
    <div style={{ fontSize: 13, lineHeight: 1.65, color: 'var(--text-primary)' }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
    </div>
  )
}

// ── basic markdown→HTML for download (no React), kept dependency-free ─
function markdownToHTML(md: string): string {
  // Safe-ish escaping; the LLM output is markdown so we trust it broadly here.
  let html = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // Headers
  html = html.replace(/^### (.*)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.*)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.*)$/gm, '<h1>$1</h1>')
  // Bold + italics
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  // Blockquotes
  html = html.replace(/^&gt; (.*)$/gm, '<blockquote>$1</blockquote>')
  // Lists (very basic)
  html = html.replace(/^- (.*)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>(\n|$))+/g, (m) => `<ul>${m}</ul>`)
  // Tables — minimal: keep as-is (HTML table tags pass through escape)
  // Paragraphs from blank lines
  html = html.split(/\n{2,}/).map((block) =>
    /^(<h[1-6]|<ul|<blockquote|<table)/.test(block.trim())
      ? block
      : `<p>${block.replace(/\n/g, '<br>')}</p>`
  ).join('\n')
  return html
}
