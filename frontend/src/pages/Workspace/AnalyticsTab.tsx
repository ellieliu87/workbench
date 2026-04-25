import { useEffect, useMemo, useState } from 'react'
import {
  FlaskConical, Play, X, Sparkles, Trash2, ChevronRight,
  AlertCircle, CheckCircle2, Database, Boxes, GripVertical, Hand,
  ArrowRightCircle,
} from 'lucide-react'
import api from '@/lib/api'
import type {
  AnalyticsRun, Scenario, TrainedModel, Dataset,
} from '@/types'
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
  onContextChange: (ctx: string | null) => void
}

// Type-tagged drag payload — shape we put into dataTransfer
type DragPayload =
  | { kind: 'model'; id: string }
  | { kind: 'scenario'; id: string }
  | { kind: 'dataset'; id: string }

const DRAG_MIME = 'application/x-cma-payload'

export default function AnalyticsTab({ functionId, functionName, onAskAgent, onContextChange }: Props) {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [models, setModels] = useState<TrainedModel[]>([])
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [runs, setRuns] = useState<AnalyticsRun[]>([])
  const [loading, setLoading] = useState(true)
  const [activeRun, setActiveRun] = useState<AnalyticsRun | null>(null)

  // Job builder state — populated by drag-and-drop or click-to-assign
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)
  const [selectedInput, setSelectedInput] = useState<{ kind: 'scenario' | 'dataset'; id: string } | null>(null)
  const [horizon, setHorizon] = useState(12)
  const [runName, setRunName] = useState('')
  const [notes, setNotes] = useState('')
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  // Drag state for visual feedback
  const [draggingKind, setDraggingKind] = useState<DragPayload['kind'] | null>(null)
  const [hoverModelDrop, setHoverModelDrop] = useState(false)
  const [hoverInputDrop, setHoverInputDrop] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get<Scenario[]>(`/api/analytics/scenarios`, { params: { function_id: functionId } }),
      api.get<TrainedModel[]>(`/api/models`, { params: { function_id: functionId } }),
      api.get<Dataset[]>(`/api/datasets`, { params: { function_id: functionId } }),
      api.get<AnalyticsRun[]>(`/api/analytics/runs`, { params: { function_id: functionId } }),
    ])
      .then(([s, m, d, r]) => { setScenarios(s.data); setModels(m.data); setDatasets(d.data); setRuns(r.data) })
      .finally(() => setLoading(false))
  }

  useEffect(load, [functionId])

  useEffect(() => {
    onContextChange(`${functionName} (Analytics tab): ${runs.length} runs · ${models.length} models · ${datasets.length + scenarios.length} inputs`)
    return () => onContextChange(null)
  }, [runs.length, models.length, datasets.length, scenarios.length, functionName, onContextChange])

  const selectedModel = useMemo(
    () => models.find((m) => m.id === selectedModelId) || null,
    [models, selectedModelId],
  )
  const selectedScenario = useMemo(
    () => (selectedInput?.kind === 'scenario' ? scenarios.find((s) => s.id === selectedInput.id) : null) || null,
    [scenarios, selectedInput],
  )
  const selectedDataset = useMemo(
    () => (selectedInput?.kind === 'dataset' ? datasets.find((d) => d.id === selectedInput.id) : null) || null,
    [datasets, selectedInput],
  )

  // ── DnD handlers ─────────────────────────────────────────────────────
  const startDrag = (e: React.DragEvent, payload: DragPayload) => {
    e.dataTransfer.setData(DRAG_MIME, JSON.stringify(payload))
    e.dataTransfer.setData('text/plain', `${payload.kind}:${payload.id}`)
    e.dataTransfer.effectAllowed = 'copy'
    setDraggingKind(payload.kind)
  }
  const endDrag = () => {
    setDraggingKind(null)
    setHoverModelDrop(false)
    setHoverInputDrop(false)
  }

  const readPayload = (e: React.DragEvent): DragPayload | null => {
    try {
      const raw = e.dataTransfer.getData(DRAG_MIME) || e.dataTransfer.getData('text/plain')
      if (!raw) return null
      if (raw.includes(':') && !raw.startsWith('{')) {
        const [kind, id] = raw.split(':')
        return { kind: kind as DragPayload['kind'], id }
      }
      return JSON.parse(raw) as DragPayload
    } catch {
      return null
    }
  }

  const onModelDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const payload = readPayload(e)
    if (payload?.kind === 'model') setSelectedModelId(payload.id)
    endDrag()
  }
  const onInputDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const payload = readPayload(e)
    if (payload?.kind === 'scenario' || payload?.kind === 'dataset') {
      setSelectedInput({ kind: payload.kind, id: payload.id })
    }
    endDrag()
  }

  // ── Submit ────────────────────────────────────────────────────────────
  const submit = async () => {
    if (!selectedModelId || !selectedInput) return
    setRunning(true)
    setRunError(null)
    try {
      const r = await api.post<AnalyticsRun>('/api/analytics/runs', {
        function_id: functionId,
        name: runName || null,
        model_id: selectedModelId,
        scenario_id: selectedInput.kind === 'scenario' ? selectedInput.id : null,
        dataset_id: selectedInput.kind === 'dataset' ? selectedInput.id : null,
        horizon_months: horizon,
        notes,
      })
      setActiveRun(r.data)
      // Reset notes/name for next run, keep model+input
      setRunName('')
      setNotes('')
      load()
    } catch (e: any) {
      setRunError(e?.response?.data?.detail || 'Run failed')
    } finally {
      setRunning(false)
    }
  }

  const clearJob = () => {
    setSelectedModelId(null)
    setSelectedInput(null)
    setRunName('')
    setNotes('')
    setRunError(null)
  }

  const removeRun = async (id: string) => {
    if (!confirm('Delete this run?')) return
    await api.delete(`/api/analytics/runs/${id}`)
    if (activeRun?.id === id) setActiveRun(null)
    load()
  }

  return (
    <div onDragEnd={endDrag}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div>
          <div className="font-display text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            Analytics Job Builder
          </div>
          <div className="text-xs flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
            <Hand size={11} />
            Drag a model and an input data source onto the canvas, set a horizon, hit Run.
          </div>
        </div>
        <button
          onClick={() => onAskAgent(`Suggest an analytics run for ${functionName} given the available models and inputs.`)}
          className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          <Sparkles size={13} /> Ask Agent
        </button>
      </div>

      {/* Job builder canvas */}
      <div
        className="panel mb-6"
        style={{ padding: 18, background: 'linear-gradient(180deg, var(--bg-card), var(--bg-page))' }}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Model drop zone */}
          <DropZone
            label="MODEL"
            icon={Boxes}
            highlight={hoverModelDrop || draggingKind === 'model'}
            isOver={hoverModelDrop}
            disabledHint={draggingKind && draggingKind !== 'model' ? 'Drop a model here' : null}
            onDragEnter={() => setHoverModelDrop(true)}
            onDragLeave={() => setHoverModelDrop(false)}
            onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy' }}
            onDrop={onModelDrop}
          >
            {selectedModel ? (
              <SlotFilled
                title={selectedModel.name}
                subtitle={`${selectedModel.model_type.toUpperCase()}${selectedModel.feature_columns.length ? ` · ${selectedModel.feature_columns.length} features` : ''}`}
                color="#7C3AED"
                onClear={() => setSelectedModelId(null)}
              />
            ) : (
              <SlotPlaceholder
                kind="model"
                hint="drop a model here"
                isOver={hoverModelDrop}
                draggingKind={draggingKind}
              />
            )}
          </DropZone>

          {/* Input drop zone */}
          <DropZone
            label="INPUT DATA"
            icon={ArrowRightCircle}
            highlight={hoverInputDrop || draggingKind === 'scenario' || draggingKind === 'dataset'}
            isOver={hoverInputDrop}
            disabledHint={draggingKind === 'model' ? 'Drop a scenario or dataset here' : null}
            onDragEnter={() => setHoverInputDrop(true)}
            onDragLeave={() => setHoverInputDrop(false)}
            onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy' }}
            onDrop={onInputDrop}
          >
            {selectedScenario ? (
              <SlotFilled
                title={selectedScenario.name}
                subtitle={`Scenario · ${SEVERITY_LABEL[selectedScenario.severity]} · ${selectedScenario.variables.length} vars`}
                color={SEVERITY_COLOR[selectedScenario.severity]}
                onClear={() => setSelectedInput(null)}
              />
            ) : selectedDataset ? (
              <SlotFilled
                title={selectedDataset.name}
                subtitle={`Dataset · ${selectedDataset.source_kind === 'upload' ? 'upload' : 'sql'} · ${selectedDataset.columns.length} cols`}
                color="#0891B2"
                onClear={() => setSelectedInput(null)}
              />
            ) : (
              <SlotPlaceholder
                kind="input"
                hint="drop a scenario or dataset here"
                isOver={hoverInputDrop}
                draggingKind={draggingKind}
              />
            )}
          </DropZone>
        </div>

        {/* Run controls */}
        <div className="flex items-end gap-3 mt-4 flex-wrap">
          <Field label={selectedInput?.kind === 'dataset' ? 'Row limit' : 'Horizon (months)'} className="w-32">
            <input
              type="number" min={1} max={500} className="input"
              value={horizon}
              onChange={(e) => setHorizon(Math.max(1, Math.min(500, parseInt(e.target.value || '12'))))}
            />
          </Field>
          <Field label="Run name (optional)" className="flex-1 min-w-[200px]">
            <input className="input" value={runName} onChange={(e) => setRunName(e.target.value)} placeholder="auto-generated if blank" />
          </Field>
          <Field label="Notes (optional)" className="flex-[2] min-w-[200px]">
            <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
          <div className="flex gap-2 mb-0.5">
            <button
              onClick={clearJob}
              disabled={!selectedModelId && !selectedInput && !runName && !notes}
              className="px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            >
              Clear
            </button>
            <button
              onClick={submit}
              disabled={!selectedModelId || !selectedInput || running}
              className="px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              <Play size={13} /> {running ? 'Running…' : 'Run job'}
            </button>
          </div>
        </div>

        {runError && (
          <div
            className="text-xs px-3 py-2 rounded-md mt-3"
            style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
          >
            {runError}
          </div>
        )}
      </div>

      {/* Palette + run history */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 space-y-3">
          <Palette
            title={`Models (${models.length})`}
            icon={Boxes}
            color="#7C3AED"
            empty={models.length === 0 ? 'Build or upload a model on the Models tab.' : null}
          >
            {models.map((m) => (
              <DraggableCard
                key={m.id}
                title={m.name}
                subtitle={m.model_type.toUpperCase()}
                color="#7C3AED"
                selected={selectedModelId === m.id}
                onDragStart={(e) => startDrag(e, { kind: 'model', id: m.id })}
                onClick={() => setSelectedModelId(m.id)}
              />
            ))}
          </Palette>

          <Palette
            title={`Scenarios (${scenarios.length})`}
            icon={FlaskConical}
            color="#0891B2"
          >
            {scenarios.map((s) => (
              <DraggableCard
                key={s.id}
                title={s.name}
                subtitle={`${SEVERITY_LABEL[s.severity]} · ${s.variables.length} vars`}
                color={SEVERITY_COLOR[s.severity]}
                selected={selectedInput?.kind === 'scenario' && selectedInput.id === s.id}
                onDragStart={(e) => startDrag(e, { kind: 'scenario', id: s.id })}
                onClick={() => setSelectedInput({ kind: 'scenario', id: s.id })}
              />
            ))}
          </Palette>

          <Palette
            title={`Datasets (${datasets.length})`}
            icon={Database}
            color="#059669"
            empty={datasets.length === 0 ? 'Bind a dataset on the Data tab.' : null}
          >
            {datasets.map((d) => (
              <DraggableCard
                key={d.id}
                title={d.name}
                subtitle={`${d.source_kind === 'upload' ? 'upload' : 'sql'} · ${d.columns.length} cols`}
                color="#059669"
                selected={selectedInput?.kind === 'dataset' && selectedInput.id === d.id}
                onDragStart={(e) => startDrag(e, { kind: 'dataset', id: d.id })}
                onClick={() => setSelectedInput({ kind: 'dataset', id: d.id })}
              />
            ))}
          </Palette>
        </div>

        <div className="lg:col-span-2">
          <div className="section-title">Run History ({runs.length})</div>
          {!loading && runs.length === 0 && (
            <div
              className="panel text-center"
              style={{ padding: '32px 20px', borderStyle: 'dashed' }}
            >
              <FlaskConical size={24} style={{ color: 'var(--text-muted)', margin: '0 auto 10px' }} />
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                No runs yet
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                Drag a model and an input above, then hit Run job.
              </div>
            </div>
          )}
          <div className="space-y-2">
            {runs.map((r) => (
              <RunRow
                key={r.id}
                run={r}
                modelName={models.find((m) => m.id === r.model_id)?.name}
                scenarioName={scenarios.find((s) => s.id === r.scenario_id)?.name}
                scenarioSeverity={scenarios.find((s) => s.id === r.scenario_id)?.severity}
                datasetName={datasets.find((d) => d.id === r.dataset_id)?.name}
                onOpen={() => setActiveRun(r)}
                onDelete={() => removeRun(r.id)}
                onAskAgent={onAskAgent}
              />
            ))}
          </div>
        </div>
      </div>

      {activeRun && (
        <RunDetailPanel
          run={activeRun}
          model={models.find((m) => m.id === activeRun.model_id)}
          scenario={scenarios.find((s) => s.id === activeRun.scenario_id)}
          dataset={datasets.find((d) => d.id === activeRun.dataset_id)}
          onClose={() => setActiveRun(null)}
          onAskAgent={onAskAgent}
        />
      )}

      <style>{`
        .input {
          width: 100%; padding: 8px 10px; border-radius: 8px; font-size: 13px;
          background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);
        }
      `}</style>
    </div>
  )
}

// ── Drop zone ──────────────────────────────────────────────────────────
function DropZone({
  label, icon: Icon, highlight, isOver, disabledHint, children,
  onDragEnter, onDragLeave, onDragOver, onDrop,
}: {
  label: string
  icon: any
  highlight: boolean
  isOver: boolean
  disabledHint: string | null
  children: React.ReactNode
  onDragEnter: () => void
  onDragLeave: () => void
  onDragOver: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent) => void
}) {
  return (
    <div
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className="rounded-xl p-3 transition-all"
      style={{
        background: isOver ? 'var(--accent-light)' : 'var(--bg-elevated)',
        border: `2px dashed ${isOver ? 'var(--accent)' : highlight ? 'var(--accent)' : 'var(--border)'}`,
        minHeight: 110,
      }}
    >
      <div className="flex items-center gap-1.5 mb-2">
        <Icon size={11} style={{ color: 'var(--text-secondary)' }} />
        <span
          style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.10em',
            color: 'var(--text-secondary)',
          }}
        >
          {label}
        </span>
        {disabledHint && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {disabledHint}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

function SlotPlaceholder({
  kind, hint, isOver, draggingKind,
}: {
  kind: 'model' | 'input'
  hint: string
  isOver: boolean
  draggingKind: DragPayload['kind'] | null
}) {
  const matching =
    (kind === 'model' && draggingKind === 'model') ||
    (kind === 'input' && (draggingKind === 'scenario' || draggingKind === 'dataset'))
  return (
    <div
      className="flex items-center justify-center text-xs"
      style={{
        height: 70,
        color: isOver || matching ? 'var(--accent)' : 'var(--text-muted)',
        fontWeight: matching ? 600 : 400,
      }}
    >
      {isOver ? 'Release to drop' : hint}
    </div>
  )
}

function SlotFilled({
  title, subtitle, color, onClear,
}: {
  title: string
  subtitle: string
  color: string
  onClear: () => void
}) {
  return (
    <div
      className="flex items-start gap-3 px-3 py-2 rounded-lg"
      style={{ background: 'var(--bg-card)', border: `1px solid ${color}40` }}
    >
      <div
        className="w-1.5 self-stretch rounded-sm shrink-0"
        style={{ background: color, marginTop: 2, marginBottom: 2 }}
      />
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
          {title}
        </div>
        <div className="text-[11px] truncate font-mono" style={{ color: 'var(--text-muted)' }}>
          {subtitle}
        </div>
      </div>
      <button
        onClick={onClear}
        className="p-1 rounded-md"
        style={{ color: 'var(--text-muted)' }}
        title="Clear"
      >
        <X size={13} />
      </button>
    </div>
  )
}

// ── Palette ────────────────────────────────────────────────────────────
function Palette({
  title, icon: Icon, color, empty, children,
}: {
  title: string
  icon: any
  color: string
  empty?: string | null
  children: React.ReactNode
}) {
  return (
    <div className="panel" style={{ padding: 12 }}>
      <div className="flex items-center gap-1.5 mb-2">
        <div
          className="w-6 h-6 rounded-md flex items-center justify-center"
          style={{ background: `${color}1A`, color }}
        >
          <Icon size={11} />
        </div>
        <span
          style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.10em',
            color: 'var(--text-secondary)', textTransform: 'uppercase',
          }}
        >
          {title}
        </span>
      </div>
      <div className="space-y-1.5">
        {empty && <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{empty}</div>}
        {children}
      </div>
    </div>
  )
}

function DraggableCard({
  title, subtitle, color, selected, onDragStart, onClick,
}: {
  title: string
  subtitle: string
  color: string
  selected: boolean
  onDragStart: (e: React.DragEvent) => void
  onClick: () => void
}) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      className="rounded-md transition-all cursor-grab active:cursor-grabbing"
      style={{
        padding: '6px 8px',
        background: selected ? `${color}1A` : 'var(--bg-elevated)',
        border: `1px solid ${selected ? color : 'var(--border)'}`,
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        if (!selected) (e.currentTarget as HTMLElement).style.borderColor = color
      }}
      onMouseLeave={(e) => {
        if (!selected) (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'
      }}
    >
      <div className="flex items-center gap-2">
        <GripVertical size={11} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
            {title}
          </div>
          <div className="text-[10px] truncate font-mono" style={{ color: 'var(--text-muted)' }}>
            {subtitle}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Run row ─────────────────────────────────────────────────────────
function RunRow({
  run, modelName, scenarioName, scenarioSeverity, datasetName, onOpen, onDelete, onAskAgent,
}: {
  run: AnalyticsRun
  modelName?: string
  scenarioName?: string
  scenarioSeverity?: Scenario['severity']
  datasetName?: string
  onOpen: () => void
  onDelete: () => void
  onAskAgent: (q: string) => void
}) {
  const isScenario = run.input_kind === 'scenario'
  const color = scenarioSeverity ? SEVERITY_COLOR[scenarioSeverity] : 'var(--accent)'
  const ok = run.status === 'completed'
  const inputLabel = isScenario ? (scenarioName || run.scenario_id) : (datasetName || run.dataset_id)
  return (
    <div
      className="panel cursor-pointer transition-all"
      style={{ padding: 12 }}
      onClick={onOpen}
      onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)')}
      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border)')}
    >
      <div className="flex items-center gap-3">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: ok ? `${color}1A` : 'var(--error-bg)', color: ok ? color : 'var(--error)' }}
        >
          {ok ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
            {run.name}
          </div>
          <div className="text-[11px] truncate font-mono flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
            <span>{modelName || run.model_id}</span>
            <span>×</span>
            <span className="flex items-center gap-1">
              {isScenario ? <FlaskConical size={10} /> : <Database size={10} />}
              {inputLabel}
            </span>
            <span>· {run.horizon_months}m</span>
          </div>
        </div>
        <div className="text-right shrink-0 hidden md:block">
          {ok && run.summary?.mean_prediction != null && (
            <div className="font-mono text-sm" style={{ color: 'var(--text-primary)' }}>
              μ {Number(run.summary.mean_prediction).toFixed(3)}
            </div>
          )}
          <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
            {new Date(run.created_at).toLocaleString()} · {run.duration_ms.toFixed(0)}ms
          </div>
        </div>
        <div className="flex gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onAskAgent(`Interpret the run "${run.name}".`)}
            className="p-1.5 rounded-md"
            style={{ color: 'var(--text-muted)' }}
            title="Ask agent"
          >
            <Sparkles size={13} />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded-md"
            style={{ color: 'var(--text-muted)' }}
            title="Delete"
          >
            <Trash2 size={13} />
          </button>
          <button onClick={onOpen} className="p-1.5 rounded-md" style={{ color: 'var(--text-muted)' }}>
            <ChevronRight size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Run detail panel ──────────────────────────────────────────────────
function RunDetailPanel({
  run, model, scenario, dataset, onClose, onAskAgent,
}: {
  run: AnalyticsRun
  model?: TrainedModel
  scenario?: Scenario
  dataset?: Dataset
  onClose: () => void
  onAskAgent: (q: string) => void
}) {
  const COLORS = ['#004977', '#059669', '#D97706', '#DC2626', '#7C3AED', '#0891B2']
  const allKeys = run.series.length > 0 ? Object.keys(run.series[0]).filter((k) => k !== 'month') : []
  const driverKeys = allKeys.filter((k) => k !== 'prediction').slice(0, 5)

  const inputLabel =
    run.input_kind === 'scenario'
      ? `${scenario?.name || run.scenario_id} (scenario)`
      : `${dataset?.name || run.dataset_id} (dataset)`

  return (
    <SidePanel
      title={run.name}
      subtitle={`${model?.name || run.model_id} × ${inputLabel} · ${run.horizon_months}m · ${run.duration_ms.toFixed(0)}ms`}
      onClose={onClose}
    >
      {run.status === 'failed' && (
        <div
          className="text-xs px-3 py-2 rounded-md"
          style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
        >
          <strong>Run failed:</strong> {run.error || 'Unknown error'}
        </div>
      )}
      {run.status === 'completed' && (
        <>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(run.summary)
              .filter(([k]) => ['min_prediction', 'mean_prediction', 'max_prediction'].includes(k))
              .map(([k, v]) => (
                <div key={k} className="panel" style={{ padding: 12 }}>
                  <div className="metric-label" style={{ fontSize: 9 }}>
                    {k.replace('_prediction', '').toUpperCase()}
                  </div>
                  <div className="metric-value mt-1" style={{ fontSize: 18 }}>
                    {typeof v === 'number' ? v.toFixed(4) : v}
                  </div>
                </div>
              ))}
          </div>
          {(run.summary.features_unmatched as string[] | undefined)?.length ? (
            <div
              className="text-[11px] px-3 py-2 rounded-md flex items-start gap-2"
              style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}
            >
              <AlertCircle size={12} className="mt-0.5 shrink-0" />
              <span>
                {String((run.summary.features_unmatched as string[]).length)} feature(s) had no match in the input:{' '}
                <code>{(run.summary.features_unmatched as string[]).join(', ')}</code>. They contributed only the intercept.
              </span>
            </div>
          ) : null}

          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="section-title" style={{ marginBottom: 0 }}>Prediction Path</div>
              <button
                onClick={() => onAskAgent(`Interpret the analytics run "${run.name}" — model output by horizon.`)}
                className="text-[11px] flex items-center gap-1"
                style={{ color: 'var(--accent)', fontWeight: 600 }}
              >
                <Sparkles size={11} /> Interpret
              </button>
            </div>
            <div className="panel" style={{ padding: 14 }}>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={run.series} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="prediction" stroke={COLORS[0]} strokeWidth={3} dot={{ r: 3 }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {driverKeys.length > 0 && (
            <div>
              <div className="section-title">
                {run.input_kind === 'scenario' ? 'Macro Drivers' : 'Input Features'}
              </div>
              <div className="panel" style={{ padding: 14 }}>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={run.series} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                    <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {driverKeys.map((k, i) => (
                      <Line key={k} type="monotone" dataKey={k} stroke={COLORS[(i + 1) % COLORS.length]} strokeWidth={2} dot={{ r: 2 }} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div>
            <div className="section-title">Series ({run.series.length} rows)</div>
            <div
              className="overflow-auto rounded-lg"
              style={{ border: '1px solid var(--border)', maxHeight: 260 }}
            >
              <table className="w-full text-xs font-mono">
                <thead style={{ background: 'var(--bg-elevated)', position: 'sticky', top: 0 }}>
                  <tr>
                    {['month', 'prediction', ...driverKeys].map((k) => (
                      <th key={k} className="text-left py-2 px-3 whitespace-nowrap" style={{
                        fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                        textTransform: 'uppercase', color: 'var(--text-secondary)',
                        borderBottom: '1px solid var(--border)',
                      }}>
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {run.series.map((row, i) => (
                    <tr key={i}>
                      {['month', 'prediction', ...driverKeys].map((k) => (
                        <td key={k} className="py-1.5 px-3" style={{
                          borderBottom: '1px solid var(--border-subtle)',
                          color: k === 'prediction' ? 'var(--accent)' : undefined,
                          fontWeight: k === 'prediction' ? 600 : 400,
                        }}>
                          {typeof row[k] === 'number' ? row[k].toFixed(4) : String(row[k] ?? '—')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {run.notes && (
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              <strong>Notes:</strong> {run.notes}
            </div>
          )}
        </>
      )}
    </SidePanel>
  )
}

// ── Shared UI ──────────────────────────────────────────────────────────
function SidePanel({
  title, subtitle, onClose, children,
}: {
  title: string
  subtitle?: string
  onClose: () => void
  children: React.ReactNode
}) {
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
            <div className="font-display text-base font-semibold" style={{ color: '#fff' }}>{title}</div>
            {subtitle && (
              <div className="font-mono" style={{ fontSize: 11, color: 'rgba(255,255,255,0.75)' }}>{subtitle}</div>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg" style={{ color: 'rgba(255,255,255,0.85)' }}>
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">{children}</div>
      </div>
    </>
  )
}

function Field({ label, children, className = '' }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
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

const tooltipStyle = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  fontSize: 11,
  fontFamily: 'JetBrains Mono, monospace',
  color: 'var(--text-primary)',
}
