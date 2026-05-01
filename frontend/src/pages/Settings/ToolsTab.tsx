import { useEffect, useRef, useState } from 'react'
import { Plus, Pencil, Trash2, Play, Code2, X, Sparkles, AlertCircle, CheckCircle2, Wand2, Loader2, Lock, UserCog, ChevronDown, ChevronRight } from 'lucide-react'
import api from '@/lib/api'
import type { PythonTool, ToolParameter, ToolTestResponse, ToolDraftResponse } from '@/types'

const EMPTY_TOOL: PythonTool = {
  id: '',
  name: '',
  description: '',
  parameters: [],
  python_source: '',
  function_name: '',
  enabled: true,
}

interface EditorState {
  open: boolean
  mode: 'create' | 'edit'
  tool: PythonTool | null
  testArgs: string
  testResult: ToolTestResponse | null
  saving: boolean
  saveError: string | null
}

export default function ToolsTab() {
  const [tools, setTools] = useState<PythonTool[]>([])
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<EditorState>({
    open: false, mode: 'create', tool: null, testArgs: '{}', testResult: null, saving: false, saveError: null,
  })

  const load = () => {
    setLoading(true)
    api.get<PythonTool[]>('/api/tools').then((r) => setTools(r.data)).finally(() => setLoading(false))
  }

  useEffect(load, [])

  const openCreate = async () => {
    const r = await api.get<{ python_source: string; function_name: string }>('/api/tools/template')
    setEditor({
      open: true,
      mode: 'create',
      tool: { ...EMPTY_TOOL, python_source: r.data.python_source, function_name: r.data.function_name, name: r.data.function_name },
      testArgs: '{\n  "symbol": "AAPL",\n  "lookback_days": 30\n}',
      testResult: null,
      saving: false,
      saveError: null,
    })
  }

  const openEdit = (t: PythonTool) => {
    const sampleArgs: Record<string, any> = {}
    for (const p of t.parameters) {
      sampleArgs[p.name] =
        p.type === 'integer' || p.type === 'number' ? 1 :
        p.type === 'boolean' ? false :
        p.type === 'array' ? [] :
        p.type === 'object' ? {} :
        ''
    }
    setEditor({
      open: true,
      mode: 'edit',
      tool: { ...t, parameters: [...t.parameters] },
      testArgs: JSON.stringify(sampleArgs, null, 2),
      testResult: null,
      saving: false,
      saveError: null,
    })
  }

  const closeEditor = () => setEditor((e) => ({ ...e, open: false, tool: null, testResult: null, saveError: null }))

  const updateField = <K extends keyof PythonTool>(k: K, v: PythonTool[K]) => {
    setEditor((e) => (e.tool ? { ...e, tool: { ...e.tool, [k]: v } } : e))
  }

  const addParam = () => {
    if (!editor.tool) return
    updateField('parameters', [...editor.tool.parameters, { name: '', type: 'string', description: '', required: true }])
  }

  const updateParam = (idx: number, patch: Partial<ToolParameter>) => {
    if (!editor.tool) return
    const next = editor.tool.parameters.map((p, i) => (i === idx ? { ...p, ...patch } : p))
    updateField('parameters', next)
  }

  const removeParam = (idx: number) => {
    if (!editor.tool) return
    updateField('parameters', editor.tool.parameters.filter((_, i) => i !== idx))
  }

  const save = async () => {
    if (!editor.tool || !editor.tool.name || !editor.tool.function_name || !editor.tool.python_source) return
    setEditor((e) => ({ ...e, saving: true, saveError: null }))
    try {
      const payload = {
        name: editor.tool.name,
        description: editor.tool.description,
        parameters: editor.tool.parameters,
        python_source: editor.tool.python_source,
        function_name: editor.tool.function_name,
      }
      if (editor.mode === 'create') {
        await api.post('/api/tools', payload)
      } else {
        await api.patch(`/api/tools/${editor.tool.id}`, payload)
      }
      closeEditor()
      load()
    } catch (err: any) {
      setEditor((e) => ({ ...e, saving: false, saveError: err?.response?.data?.detail || 'Save failed' }))
    }
  }

  const runTest = async () => {
    if (!editor.tool) return
    let args: Record<string, any> = {}
    try {
      args = editor.testArgs.trim() ? JSON.parse(editor.testArgs) : {}
    } catch (e: any) {
      setEditor((s) => ({ ...s, testResult: { ok: false, error: `Invalid JSON: ${e.message}`, duration_ms: 0 } }))
      return
    }
    // For unsaved tools, save inline first; for saved, just hit /test
    setEditor((s) => ({ ...s, testResult: null }))
    if (editor.mode === 'create' || editor.tool.id === '') {
      // Need to save first to test — guide the user
      setEditor((s) => ({ ...s, testResult: { ok: false, error: 'Save the tool before running a test.', duration_ms: 0 } }))
      return
    }
    const r = await api.post<ToolTestResponse>(`/api/tools/${editor.tool.id}/test`, { args })
    setEditor((s) => ({ ...s, testResult: r.data }))
  }

  const remove = async (id: string) => {
    if (!confirm('Delete this tool?')) return
    await api.delete(`/api/tools/${id}`)
    load()
  }

  const toggle = async (id: string) => {
    await api.patch(`/api/tools/${id}/toggle`)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
          {loading
            ? 'Loading…'
            : `${tools.filter((t) => t.enabled).length} of ${tools.length} tools enabled`}
          {' '}· Each tool is a Python function the agent can call.
        </div>
        <button
          onClick={openCreate}
          className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          <Plus size={13} /> New Tool
        </button>
      </div>

      {(() => {
        const userTools = tools.filter((t) => t.source === 'user')
        const builtinTools = tools.filter((t) => (t.source ?? 'user') === 'builtin')
        const packedByPack = new Map<string, PythonTool[]>()
        for (const t of tools) {
          if (t.source !== 'pack') continue
          const pid = t.pack_id || 'unknown'
          if (!packedByPack.has(pid)) packedByPack.set(pid, [])
          packedByPack.get(pid)!.push(t)
        }

        const renderCard = (t: PythonTool) => {
          const isUser = (t.source ?? 'user') === 'user'
          const isPack = t.source === 'pack'
          const badgeBg = isUser ? 'rgba(217,119,6,0.12)' : isPack ? 'rgba(37,99,235,0.12)' : 'rgba(8,145,178,0.12)'
          const badgeColor = isUser ? '#D97706' : isPack ? '#2563EB' : '#0891B2'
          return (
            <div key={t.id} className="panel">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: 'rgba(0,73,119,0.10)', color: 'var(--accent)' }}
                  >
                    <Code2 size={16} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-sm font-semibold truncate">{t.name}</span>
                      <span
                        className="pill flex items-center gap-1"
                        style={{
                          fontSize: 9, fontWeight: 700,
                          background: badgeBg,
                          color: badgeColor,
                          borderColor: 'transparent',
                          textTransform: 'uppercase', letterSpacing: '0.06em',
                        }}
                      >
                        {isUser ? <><UserCog size={9} /> User</>
                          : isPack ? <>Pack: {t.pack_id}</>
                          : <><Lock size={9} /> Built-in</>}
                      </span>
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      {t.parameters.length} param{t.parameters.length === 1 ? '' : 's'} · entry: <code>{t.function_name}</code>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => toggle(t.id)}
                  className="px-2 py-1 rounded-full text-[10px] font-bold tracking-wider"
                  style={{
                    background: t.enabled ? 'var(--success-bg)' : 'var(--bg-elevated)',
                    color: t.enabled ? 'var(--success)' : 'var(--text-muted)',
                  }}
                >
                  {t.enabled ? 'ON' : 'OFF'}
                </button>
              </div>
              <div className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                {t.description}
              </div>
              {t.parameters.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {t.parameters.map((p) => (
                    <span key={p.name} className="pill" style={{ fontSize: 10 }}>
                      {p.name}: {p.type}
                      {!p.required && <span style={{ opacity: 0.6 }}>?</span>}
                    </span>
                  ))}
                </div>
              )}
              <div
                className="flex items-center justify-end gap-1 mt-3 pt-3"
                style={{ borderTop: '1px solid var(--border-subtle)' }}
              >
                <button
                  onClick={() => openEdit(t)}
                  className="p-1.5 rounded-md transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                  title="Edit / Test"
                  onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--accent)')}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
                >
                  <Pencil size={13} />
                </button>
                <button
                  onClick={() => remove(t.id)}
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
        }

        const packIds = Array.from(packedByPack.keys()).sort()

        return (
          <>
            <CollapsibleSection
              id="tools:user"
              defaultOpen
              icon={UserCog}
              color="#D97706"
              title="User-Customized Tools"
              subtitle="Tools you registered. Editable & deletable."
              count={userTools.length}
              kindLabel="tool"
            >
              {userTools.length === 0 ? (
                <div className="panel text-center py-6 text-xs mb-5" style={{ color: 'var(--text-muted)' }}>
                  None yet. Click <strong>+ New Tool</strong> or use the Wand to draft one with the agent.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
                  {userTools.map(renderCard)}
                </div>
              )}
            </CollapsibleSection>

            {packIds.map((pid) => {
              const inPack = packedByPack.get(pid) || []
              return (
                <CollapsibleSection
                  key={pid}
                  id={`tools:pack:${pid}`}
                  icon={Lock}
                  color="#2563EB"
                  title={`Domain Pack — ${pid}`}
                  subtitle="Installed by a domain pack. Read-only here; manage with the pack."
                  count={inPack.length}
                  kindLabel="tool"
                >
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
                    {inPack.map(renderCard)}
                  </div>
                </CollapsibleSection>
              )
            })}

            <CollapsibleSection
              id="tools:builtin"
              icon={Lock}
              color="#0891B2"
              title="Built-in Tools"
              subtitle="Shipped with the workbench."
              count={builtinTools.length}
              kindLabel="tool"
            >
              {builtinTools.length === 0 ? (
                <div className="panel text-center py-6 text-xs" style={{ color: 'var(--text-muted)' }}>
                  No built-in tools.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {builtinTools.map(renderCard)}
                </div>
              )}
            </CollapsibleSection>
          </>
        )
      })()}

      {editor.open && editor.tool && (
        <ToolEditor
          state={editor}
          onClose={closeEditor}
          onSave={save}
          onRunTest={runTest}
          onChange={updateField}
          onAddParam={addParam}
          onUpdateParam={updateParam}
          onRemoveParam={removeParam}
          onTestArgsChange={(v) => setEditor((e) => ({ ...e, testArgs: v }))}
          onDraftApplied={(d) => setEditor((e) => (e.tool ? {
            ...e,
            tool: {
              ...e.tool,
              name: d.name,
              description: d.description,
              function_name: d.function_name,
              parameters: d.parameters,
              python_source: d.python_source,
            },
            // Pre-fill the test args with reasonable defaults from the new params
            testArgs: JSON.stringify(
              Object.fromEntries(d.parameters.map((p) => [p.name,
                p.type === 'integer' || p.type === 'number' ? 0 :
                p.type === 'boolean' ? false :
                p.type === 'array' ? [] :
                p.type === 'object' ? {} : ''])),
              null, 2,
            ),
            saveError: null,
          } : e))}
        />
      )}
    </div>
  )
}

interface ToolEditorProps {
  state: EditorState
  onClose: () => void
  onSave: () => void
  onRunTest: () => void
  onChange: <K extends keyof PythonTool>(k: K, v: PythonTool[K]) => void
  onAddParam: () => void
  onUpdateParam: (idx: number, patch: Partial<ToolParameter>) => void
  onRemoveParam: (idx: number) => void
  onTestArgsChange: (v: string) => void
  onDraftApplied: (d: ToolDraftResponse) => void
}

function ToolEditor({
  state, onClose, onSave, onRunTest, onChange, onAddParam, onUpdateParam, onRemoveParam, onTestArgsChange, onDraftApplied,
}: ToolEditorProps) {
  const t = state.tool!
  const [draftPrompt, setDraftPrompt] = useState('')
  const [drafting, setDrafting] = useState(false)
  const [draftError, setDraftError] = useState<string | null>(null)
  const [draftNotes, setDraftNotes] = useState<string | null>(null)

  const generateDraft = async () => {
    if (!draftPrompt.trim()) return
    setDrafting(true)
    setDraftError(null)
    setDraftNotes(null)
    try {
      const r = await api.post<ToolDraftResponse>('/api/tools/draft', {
        prompt: draftPrompt.trim(),
      })
      onDraftApplied(r.data)
      if (r.data.notes) setDraftNotes(r.data.notes)
    } catch (err: any) {
      setDraftError(err?.response?.data?.detail || 'Draft failed')
    } finally {
      setDrafting(false)
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-40" style={{ background: 'rgba(11,15,25,0.45)' }} onClick={onClose} />
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
              {state.mode === 'create' ? 'New Python Tool' : 'Edit Python Tool'}
            </div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>
              {state.mode === 'edit' ? t.id : 'Drafting…'}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg" style={{ color: 'rgba(255,255,255,0.85)' }}>
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* ── Ask the agent to draft the tool ─────────────────────────── */}
          <div
            className="rounded-lg p-3"
            style={{
              background: 'linear-gradient(135deg, rgba(124,58,237,0.08), rgba(0,73,119,0.06))',
              border: '1px solid var(--border)',
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <Wand2 size={14} style={{ color: '#7C3AED' }} />
              <span className="text-[12px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                Ask the agent to draft this tool
              </span>
              <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Describe what you want in plain English — the agent fills in the form below.
              </span>
            </div>
            <textarea
              rows={2}
              className="input resize-none"
              placeholder="e.g. Calculate the weighted average yield of a list of bonds where each bond has a yield and a market value."
              value={draftPrompt}
              onChange={(e) => setDraftPrompt(e.target.value)}
            />
            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={generateDraft}
                disabled={drafting || !draftPrompt.trim()}
                className="px-3 py-1.5 rounded-md text-[11px] font-semibold flex items-center gap-1.5 disabled:opacity-40"
                style={{ background: '#7C3AED', color: '#fff' }}
              >
                {drafting
                  ? <><Loader2 size={11} className="animate-spin" /> Drafting…</>
                  : <><Wand2 size={11} /> Generate</>
                }
              </button>
              <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                You'll review &amp; edit the draft below before saving.
              </span>
            </div>
            {draftError && (
              <div
                className="mt-2 px-2 py-1.5 rounded-md text-[11px] flex items-start gap-1.5"
                style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
              >
                <AlertCircle size={12} className="mt-0.5 shrink-0" />
                <span className="font-mono">{draftError}</span>
              </div>
            )}
            {draftNotes && !draftError && (
              <div
                className="mt-2 px-2 py-1.5 rounded-md text-[11px] flex items-start gap-1.5"
                style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}
              >
                <AlertCircle size={12} className="mt-0.5 shrink-0" />
                <span><strong>Agent notes:</strong> {draftNotes}</span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Tool Name (advertised to agent)">
              <input
                className="input font-mono"
                value={t.name}
                onChange={(e) => onChange('name', e.target.value)}
                placeholder="e.g. get_position_summary"
              />
            </Field>
            <Field label="Function Name (entry point)">
              <input
                className="input font-mono"
                value={t.function_name}
                onChange={(e) => onChange('function_name', e.target.value)}
                placeholder="e.g. get_position_summary"
              />
            </Field>
          </div>

          <Field label="Description">
            <textarea
              rows={2}
              className="input resize-none"
              value={t.description}
              onChange={(e) => onChange('description', e.target.value)}
              placeholder="What this tool does, in one sentence."
            />
          </Field>

          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
                Parameters ({t.parameters.length})
              </span>
              <button
                onClick={onAddParam}
                className="text-[11px] flex items-center gap-1"
                style={{ color: 'var(--accent)', fontWeight: 600 }}
              >
                <Plus size={11} /> Add Parameter
              </button>
            </div>
            <div
              className="rounded-lg p-2 space-y-2"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
            >
              {t.parameters.length === 0 && (
                <div className="text-xs px-1 py-2" style={{ color: 'var(--text-muted)' }}>
                  No parameters defined. Click <em>Add Parameter</em> to declare the function inputs.
                </div>
              )}
              {t.parameters.map((p, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-center">
                  <input
                    className="input col-span-3 font-mono"
                    placeholder="name"
                    value={p.name}
                    onChange={(e) => onUpdateParam(i, { name: e.target.value })}
                  />
                  <select
                    className="input col-span-2"
                    value={p.type}
                    onChange={(e) => onUpdateParam(i, { type: e.target.value as ToolParameter['type'] })}
                  >
                    <option value="string">string</option>
                    <option value="integer">integer</option>
                    <option value="number">number</option>
                    <option value="boolean">boolean</option>
                    <option value="object">object</option>
                    <option value="array">array</option>
                  </select>
                  <input
                    className="input col-span-5"
                    placeholder="description"
                    value={p.description || ''}
                    onChange={(e) => onUpdateParam(i, { description: e.target.value })}
                  />
                  <label className="col-span-1 flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                    <input type="checkbox" checked={p.required} onChange={(e) => onUpdateParam(i, { required: e.target.checked })} />
                    req
                  </label>
                  <button
                    onClick={() => onRemoveParam(i)}
                    className="col-span-1 p-1.5 rounded-md"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <Field label="Python Source (single function definition)">
            <textarea
              rows={14}
              className="input resize-y font-mono"
              style={{ fontSize: 12, lineHeight: 1.55, tabSize: 4 }}
              value={t.python_source}
              onChange={(e) => onChange('python_source', e.target.value)}
              placeholder={'def my_tool(x: int):\n    return x * 2'}
              spellCheck={false}
            />
          </Field>

          {state.saveError && (
            <div
              className="px-3 py-2 rounded-lg text-xs flex items-start gap-2"
              style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
            >
              <AlertCircle size={13} className="mt-0.5 shrink-0" />
              <span className="font-mono">{state.saveError}</span>
            </div>
          )}

          {/* Test runner */}
          <div
            className="rounded-lg p-3"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
                Test Run
              </span>
              <button
                onClick={onRunTest}
                disabled={state.mode === 'create'}
                className="px-2.5 py-1 rounded-md text-[11px] font-semibold flex items-center gap-1 disabled:opacity-40"
                style={{ background: 'var(--accent)', color: '#fff' }}
                title={state.mode === 'create' ? 'Save the tool first to enable test runs' : 'Run the function in a sandboxed subprocess'}
              >
                <Play size={11} /> Run
              </button>
            </div>
            <textarea
              rows={4}
              className="input resize-none font-mono"
              style={{ fontSize: 12 }}
              value={state.testArgs}
              onChange={(e) => onTestArgsChange(e.target.value)}
              placeholder='{ "x": 10 }'
              spellCheck={false}
            />
            {state.testResult && (
              <div
                className="mt-3 p-2 rounded-md"
                style={{
                  background: state.testResult.ok ? 'var(--success-bg)' : 'var(--error-bg)',
                  border: `1px solid ${state.testResult.ok ? 'var(--success)' : 'var(--error)'}33`,
                }}
              >
                <div
                  className="flex items-center gap-1.5 text-[11px] font-semibold mb-1"
                  style={{ color: state.testResult.ok ? 'var(--success)' : 'var(--error)' }}
                >
                  {state.testResult.ok ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
                  {state.testResult.ok ? 'OK' : 'ERROR'}
                  <span className="ml-auto font-mono opacity-70">{state.testResult.duration_ms.toFixed(0)} ms</span>
                </div>
                <pre
                  className="text-[11px] font-mono whitespace-pre-wrap break-all"
                  style={{ color: 'var(--text-primary)', maxHeight: 180, overflowY: 'auto' }}
                >
{state.testResult.ok
  ? JSON.stringify(state.testResult.result, null, 2)
  : (state.testResult.error || '') + (state.testResult.traceback ? '\n\n' + state.testResult.traceback : '')}
                </pre>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 px-5 py-3" style={{ borderTop: '1px solid var(--border)' }}>
          <div
            className="text-[11px] flex items-center gap-1"
            style={{ color: 'var(--text-muted)' }}
          >
            <Sparkles size={11} /> Functions run in a sandboxed subprocess with a 5-second timeout.
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-2 text-xs rounded-lg" style={{ color: 'var(--text-muted)' }}>
              Cancel
            </button>
            <button
              onClick={onSave}
              disabled={state.saving || !t.name || !t.function_name || !t.python_source}
              className="px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              {state.saving ? 'Saving…' : state.mode === 'create' ? 'Create Tool' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>

      <style>{`
        .input {
          width: 100%; padding: 8px 10px; border-radius: 8px; font-size: 13px;
          background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);
        }
      `}</style>
    </>
  )
}

// ── Collapsible section header ─────────────────────────────────────────
// Persists open/closed state per-id in localStorage so the user's
// choice survives a reload. Only User-Customized opens by default;
// Domain-Pack and Built-in start collapsed to keep noise out of the way.
function CollapsibleSection({
  id, icon: Icon, color, title, subtitle, count, kindLabel = 'item',
  defaultOpen = false, children,
}: {
  id: string
  icon: any
  color: string
  title: string
  subtitle: string
  count: number
  kindLabel?: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const storageKey = `cma-section-${id}`
  const [open, setOpen] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved !== null) return saved === '1'
    } catch {}
    return defaultOpen
  })
  const toggle = () => {
    setOpen((prev) => {
      const next = !prev
      try { localStorage.setItem(storageKey, next ? '1' : '0') } catch {}
      return next
    })
  }
  const Chev = open ? ChevronDown : ChevronRight
  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-2 mb-2 mt-1 w-full text-left rounded-md hover:bg-[var(--bg-elevated)] transition-colors"
        style={{ background: 'transparent', border: 'none', padding: '4px 6px' }}
      >
        <Chev size={13} style={{ color: 'var(--text-muted)' }} />
        <div
          className="w-6 h-6 rounded-md flex items-center justify-center"
          style={{ background: `${color}1A`, color }}
        >
          <Icon size={13} />
        </div>
        <div className="flex items-baseline gap-2 min-w-0">
          <span
            className="text-[12px] font-semibold uppercase tracking-widest"
            style={{ color: 'var(--text-primary)' }}
          >
            {title}
          </span>
          <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
            {count} {kindLabel}{count === 1 ? '' : 's'}
          </span>
          <span className="text-[11px] truncate" style={{ color: 'var(--text-muted)' }}>
            · {subtitle}
          </span>
        </div>
      </button>
      {open && children}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[11px] font-semibold uppercase tracking-widest mb-1" style={{ color: 'var(--text-secondary)' }}>
        {label}
      </span>
      {children}
    </label>
  )
}
