import { useEffect, useMemo, useState } from 'react'
import {
  Plus, X, Trash2, Database, FlaskConical, Boxes, ArrowRight,
  Snowflake, Cloud, HardDrive, FileText, Settings as Cog,
  AlertCircle, GripVertical, Sparkles,
} from 'lucide-react'
import { Node as RFNode, Edge } from '@xyflow/react'
import type {
  Dataset, AnalyticsRun, Scenario, TrainedModel, DestinationKind,
} from '@/types'
import {
  type NodeData, type StepInfo,
  computeSteps, findOrCreateInputNode, makeEdge, makeNodeId,
  removeNodeAndCleanup, destSubtitle, destColor,
} from './workflowSpec'

const DEST_KINDS: { kind: DestinationKind; label: string; icon: any }[] = [
  { kind: 'snowflake_table', label: 'Snowflake Table', icon: Snowflake },
  { kind: 'onelake_table',   label: 'OneLake Table',   icon: Cloud },
  { kind: 's3',              label: 'S3 Bucket',       icon: HardDrive },
  { kind: 'csv',             label: 'CSV File',        icon: FileText },
]

interface Props {
  nodes: RFNode<NodeData>[]
  edges: Edge[]
  models: TrainedModel[]
  datasets: Dataset[]
  scenarios: Scenario[]
  runs: AnalyticsRun[]
  setNodes: (updater: (n: RFNode<NodeData>[]) => RFNode<NodeData>[]) => void
  setEdges: (updater: (e: Edge[]) => Edge[]) => void
  onConfigureDestination: (nodeId: string, kind: DestinationKind) => void
}

export default function WorkflowStepsView({
  nodes, edges, models, datasets, scenarios,
  setNodes, setEdges, onConfigureDestination,
}: Props) {
  const steps = useMemo(() => computeSteps(nodes, edges), [nodes, edges])
  const [adding, setAdding] = useState(false)
  const [pendingModel, setPendingModel] = useState<string>(models[0]?.id || '')

  // Models load async — keep `pendingModel` in sync when the list arrives
  // or changes, so the dropdown's visible first option matches state and
  // the Add button is enabled the moment the list is non-empty.
  useEffect(() => {
    if (models.length === 0) return
    if (!pendingModel || !models.some((m) => m.id === pendingModel)) {
      setPendingModel(models[0].id)
    }
  }, [models, pendingModel])

  // ── Operations ───────────────────────────────────────────────────
  const addStep = (modelId: string) => {
    const m = models.find((x) => x.id === modelId)
    if (!m) return
    const id = makeNodeId('model', modelId)
    setNodes((ns) => [
      ...ns,
      {
        id, type: 'model',
        position: { x: 360 + Math.random() * 60, y: 80 + ns.length * 80 },
        data: {
          kind: 'model', ref_id: modelId,
          title: m.name, subtitle: m.model_type.toUpperCase(),
          color: '#7C3AED', status: 'idle',
        },
      },
    ])
    setAdding(false)
  }

  const removeStep = (nodeId: string) => {
    if (!confirm('Remove this step?')) return
    const next = removeNodeAndCleanup(nodes, edges, nodeId)
    // Also drop any orphaned destinations that were attached to this step
    const stillUsed = new Set<string>()
    for (const e of next.edges) stillUsed.add(e.target)
    const cleanedNodes = next.nodes.filter((n) => {
      if (n.data.kind === 'destination') return stillUsed.has(n.id)
      return true
    })
    setNodes(() => cleanedNodes)
    setEdges(() => next.edges)
  }

  const addInput = (stepNodeId: string, kind: 'dataset' | 'scenario' | 'step', refId: string) => {
    if (kind === 'step') {
      // refId here is the upstream model node id (already exists)
      if (refId === stepNodeId) return
      // Avoid creating cycles
      if (wouldCreateCycle(stepNodeId, refId, edges)) {
        alert('That edge would create a cycle.')
        return
      }
      // Avoid duplicate edges
      if (edges.some((e) => e.source === refId && e.target === stepNodeId)) return
      setEdges((es) => [...es, makeEdge(refId, stepNodeId)])
      return
    }
    // Dataset or scenario: find-or-create then add edge
    const resolveTitle = () => {
      if (kind === 'dataset') {
        const d = datasets.find((x) => x.id === refId)
        return d
          ? { title: d.name, subtitle: `${d.source_kind} · ${d.columns.length} cols`, color: '#059669' }
          : { title: refId, subtitle: 'dataset', color: '#059669' }
      }
      const s = scenarios.find((x) => x.id === refId)
      return s
        ? { title: s.name, subtitle: `${s.severity} · ${s.variables.length} vars`, color: '#0891B2' }
        : { title: refId, subtitle: 'scenario', color: '#0891B2' }
    }
    const result = findOrCreateInputNode(nodes, kind, refId, resolveTitle)
    setNodes(() => result.nodes)
    if (!edges.some((e) => e.source === result.nodeId && e.target === stepNodeId)) {
      setEdges((es) => [...es, makeEdge(result.nodeId, stepNodeId)])
    }
  }

  const removeInput = (stepNodeId: string, sourceNodeId: string) => {
    const newEdges = edges.filter((e) => !(e.source === sourceNodeId && e.target === stepNodeId))
    const stillUsed = new Set<string>()
    for (const e of newEdges) stillUsed.add(e.source)
    const newNodes = nodes.filter((n) => {
      if (n.data.kind === 'dataset' || n.data.kind === 'scenario') {
        return stillUsed.has(n.id)
      }
      return true
    })
    setNodes(() => newNodes)
    setEdges(() => newEdges)
  }

  const addDestination = (stepNodeId: string, kind: DestinationKind) => {
    const id = makeNodeId('destination', kind)
    setNodes((ns) => [
      ...ns,
      {
        id, type: 'destination',
        position: { x: 800, y: 80 + ns.length * 60 },
        data: {
          kind: 'destination', ref_id: kind,
          title: DEST_KINDS.find((d) => d.kind === kind)?.label || kind,
          subtitle: 'unconfigured',
          color: destColor(kind), config: {}, status: 'idle',
        },
      },
    ])
    setEdges((es) => [...es, makeEdge(stepNodeId, id)])
    // Open the config modal immediately
    setTimeout(() => onConfigureDestination(id, kind), 50)
  }

  const removeDestination = (destNodeId: string) => {
    const next = removeNodeAndCleanup(nodes, edges, destNodeId)
    setNodes(() => next.nodes)
    setEdges(() => next.edges)
  }

  const replaceStepModel = (stepNodeId: string, newModelId: string) => {
    const m = models.find((x) => x.id === newModelId)
    if (!m) return
    setNodes((ns) => ns.map((n) =>
      n.id === stepNodeId
        ? {
            ...n,
            data: {
              ...n.data, ref_id: newModelId,
              title: m.name, subtitle: m.model_type.toUpperCase(),
            },
          }
        : n,
    ))
  }

  // The model picker shows whenever `adding` is true, regardless of whether
  // we already have steps. Without this, clicking "Add First Step" set state
  // but the picker UI was gated on `steps.length > 0` and never appeared.
  const renderPicker = () => (
    <div className="flex items-center gap-2 panel" style={{ padding: 8 }}>
      <select
        className="input"
        value={pendingModel}
        onChange={(e) => setPendingModel(e.target.value)}
        style={{ width: 320 }}
      >
        {models.length === 0 && <option value="">No models registered</option>}
        {models.map((m) => (
          <option key={m.id} value={m.id}>{m.name} ({m.model_type})</option>
        ))}
      </select>
      <button
        onClick={() => addStep(pendingModel)}
        disabled={!pendingModel}
        className="px-2 py-1.5 rounded-md text-xs font-semibold disabled:opacity-40"
        style={{ background: 'var(--accent)', color: '#fff' }}
      >
        Add
      </button>
      <button
        onClick={() => setAdding(false)}
        className="px-2 py-1.5 rounded-md text-xs"
        style={{ color: 'var(--text-muted)' }}
      >
        Cancel
      </button>
    </div>
  )

  return (
    <div>
      {steps.length === 0 ? (
        adding ? (
          <div className="mt-1">{renderPicker()}</div>
        ) : (
          <div
            className="panel text-center"
            style={{ padding: '40px 20px', borderStyle: 'dashed' }}
          >
            <Boxes size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
            <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              No steps yet
            </div>
            <div className="text-xs mt-1 mb-4" style={{ color: 'var(--text-muted)' }}>
              Add a step — pick a model, then wire its inputs and destination.
            </div>
            {models.length === 0 ? (
              <div className="text-[11px]" style={{ color: 'var(--warning)' }}>
                No models registered. Build or upload a model on the Models tab first.
              </div>
            ) : (
              <button
                onClick={() => setAdding(true)}
                className="px-3 py-2 rounded-lg text-xs font-semibold"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                <Plus size={13} className="inline mr-1" /> Add First Step
              </button>
            )}
          </div>
        )
      ) : (
        <div className="space-y-3">
          {steps.map((s) => (
            <StepCard
              key={s.nodeId}
              step={s}
              allSteps={steps}
              downstreamSteps={steps.filter((other) =>
                other.inputs.some((inp) => inp.id === s.nodeId)
              )}
              models={models}
              datasets={datasets}
              scenarios={scenarios}
              onAddInput={(kind, refId) => addInput(s.nodeId, kind, refId)}
              onRemoveInput={(srcNodeId) => removeInput(s.nodeId, srcNodeId)}
              onAddDestination={(kind) => addDestination(s.nodeId, kind)}
              onRemoveDestination={(destNodeId) => removeDestination(destNodeId)}
              onConfigureDestination={(destNodeId) => {
                const node = nodes.find((n) => n.id === destNodeId)
                if (node) onConfigureDestination(destNodeId, node.data.ref_id as DestinationKind)
              }}
              onReplaceModel={(modelId) => replaceStepModel(s.nodeId, modelId)}
              onRemoveStep={() => removeStep(s.nodeId)}
            />
          ))}
        </div>
      )}

      {steps.length > 0 && (
        <div className="mt-3 flex items-center gap-2">
          {!adding ? (
            <button
              onClick={() => setAdding(true)}
              disabled={models.length === 0}
              className="px-3 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              <Plus size={13} /> Add Step
            </button>
          ) : (
            renderPicker()
          )}
        </div>
      )}

      <style>{`
        .input {
          padding: 6px 10px; border-radius: 8px; font-size: 12px;
          background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);
        }
      `}</style>
    </div>
  )
}

// ── single step card ──────────────────────────────────────────────────
function StepCard({
  step, allSteps, downstreamSteps, models, datasets, scenarios,
  onAddInput, onRemoveInput, onAddDestination, onRemoveDestination,
  onConfigureDestination, onReplaceModel, onRemoveStep,
}: {
  step: StepInfo
  allSteps: StepInfo[]
  downstreamSteps: StepInfo[]
  models: TrainedModel[]
  datasets: Dataset[]
  scenarios: Scenario[]
  onAddInput: (kind: 'dataset' | 'scenario' | 'step', refId: string) => void
  onRemoveInput: (sourceNodeId: string) => void
  onAddDestination: (kind: DestinationKind) => void
  onRemoveDestination: (destNodeId: string) => void
  onConfigureDestination: (destNodeId: string) => void
  onReplaceModel: (modelId: string) => void
  onRemoveStep: () => void
}) {
  const [showInputPicker, setShowInputPicker] = useState(false)
  const [showDestPicker, setShowDestPicker] = useState(false)

  const usedInputIds = new Set(step.inputs.map((i) => i.id))
  const earlierSteps = allSteps.filter((s) => s.number < step.number)
  const status = step.inputs.length === 0 ? 'warning' : 'ok'

  return (
    <div
      className="panel"
      style={{
        padding: 14,
        borderColor: status === 'warning' ? 'var(--warning)' : 'var(--border)',
      }}
    >
      <div className="flex items-start gap-3">
        {/* Step number badge */}
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 font-mono text-sm font-bold"
          style={{
            background: 'var(--accent-light)',
            color: 'var(--accent)',
            border: '1px solid var(--accent)',
          }}
          title={`Step ${step.number}`}
        >
          {step.number}
        </div>

        {/* Body */}
        <div className="flex-1 min-w-0">
          {/* Header line: model selector + remove */}
          <div className="flex items-center gap-2 mb-2">
            <Boxes size={13} style={{ color: '#7C3AED', flexShrink: 0 }} />
            <select
              className="input flex-1"
              value={step.modelRefId}
              onChange={(e) => onReplaceModel(e.target.value)}
              style={{ minWidth: 0 }}
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.name} ({m.model_type})</option>
              ))}
            </select>
            <button
              onClick={onRemoveStep}
              className="p-1.5 rounded-md transition-colors"
              style={{ color: 'var(--text-muted)' }}
              title="Remove step"
              onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--error)')}
              onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
            >
              <Trash2 size={13} />
            </button>
          </div>

          {/* Inputs row */}
          <div className="flex items-start gap-2 mb-2">
            <div className="text-[10px] font-semibold uppercase tracking-widest pt-1.5 shrink-0" style={{ color: 'var(--text-secondary)', width: 70 }}>
              INPUTS
            </div>
            <div className="flex-1 flex flex-wrap items-center gap-1.5">
              {step.inputs.length === 0 && (
                <span className="text-[11px] flex items-center gap-1" style={{ color: 'var(--warning)' }}>
                  <AlertCircle size={11} /> No inputs — step won't run
                </span>
              )}
              {step.inputs.map((i) => (
                <InputChip
                  key={i.id}
                  node={i}
                  earlierSteps={earlierSteps}
                  onRemove={() => onRemoveInput(i.id)}
                />
              ))}
              {!showInputPicker ? (
                <button
                  onClick={() => setShowInputPicker(true)}
                  className="text-[11px] px-2 py-0.5 rounded-md flex items-center gap-1"
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                >
                  <Plus size={10} /> add input
                </button>
              ) : (
                <InputPicker
                  datasets={datasets}
                  scenarios={scenarios}
                  earlierSteps={earlierSteps}
                  excludeIds={usedInputIds}
                  onPick={(kind, refId) => { onAddInput(kind, refId); setShowInputPicker(false) }}
                  onClose={() => setShowInputPicker(false)}
                />
              )}
            </div>
          </div>

          {/* Destinations row */}
          <div className="flex items-start gap-2">
            <div className="text-[10px] font-semibold uppercase tracking-widest pt-1.5 shrink-0" style={{ color: 'var(--text-secondary)', width: 70 }}>
              WRITE TO
            </div>
            <div className="flex-1 flex flex-wrap items-center gap-1.5">
              {/* Downstream consumers — when other steps use this step's output */}
              {downstreamSteps.length > 0 && (
                <>
                  {downstreamSteps.map((ds) => (
                    <span
                      key={ds.nodeId}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px]"
                      style={{
                        background: 'rgba(124,58,237,0.10)',
                        color: '#7C3AED',
                        border: '1px solid #7C3AED40',
                      }}
                      title="This step's output feeds the listed downstream step"
                    >
                      <ArrowRight size={10} />
                      <span className="font-medium">Step {ds.number}: {ds.modelTitle}</span>
                    </span>
                  ))}
                </>
              )}
              {step.destinations.length === 0 && downstreamSteps.length === 0 && (
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  Terminal step — output stays in the run record (no destination, no downstream consumer).
                </span>
              )}
              {step.destinations.length === 0 && downstreamSteps.length > 0 && (
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  (no external destination — output flows to the step{downstreamSteps.length > 1 ? 's' : ''} above)
                </span>
              )}
              {step.destinations.map((d) => (
                <DestinationChip
                  key={d.id}
                  node={d}
                  onConfigure={() => onConfigureDestination(d.id)}
                  onRemove={() => onRemoveDestination(d.id)}
                />
              ))}
              {!showDestPicker ? (
                <button
                  onClick={() => setShowDestPicker(true)}
                  className="text-[11px] px-2 py-0.5 rounded-md flex items-center gap-1"
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                >
                  <Plus size={10} /> add destination
                </button>
              ) : (
                <div className="flex gap-1 flex-wrap">
                  {DEST_KINDS.map(({ kind, label, icon: I }) => (
                    <button
                      key={kind}
                      onClick={() => { onAddDestination(kind); setShowDestPicker(false) }}
                      className="text-[11px] px-2 py-1 rounded-md flex items-center gap-1"
                      style={{ background: `${destColor(kind)}1A`, color: destColor(kind), border: `1px solid ${destColor(kind)}` }}
                    >
                      <I size={11} /> {label}
                    </button>
                  ))}
                  <button
                    onClick={() => setShowDestPicker(false)}
                    className="text-[11px] px-1.5 py-0.5"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Chips ─────────────────────────────────────────────────────────────
function InputChip({
  node, earlierSteps, onRemove,
}: {
  node: RFNode<NodeData>
  earlierSteps: StepInfo[]
  onRemove: () => void
}) {
  const isModel = node.data.kind === 'model'
  const stepRef = isModel ? earlierSteps.find((s) => s.nodeId === node.id) : null
  const Icon = node.data.kind === 'dataset' ? Database
    : node.data.kind === 'scenario' ? FlaskConical
    : Boxes
  const labelText = stepRef ? `Step ${stepRef.number}: ${node.data.title}` : node.data.title
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px]"
      style={{
        background: `${node.data.color}1A`, color: node.data.color,
        border: `1px solid ${node.data.color}40`,
      }}
    >
      <Icon size={10} />
      <span className="font-medium">{labelText}</span>
      <button
        onClick={onRemove}
        className="ml-0.5"
        title="Remove input"
        style={{ color: node.data.color, opacity: 0.6 }}
      >
        <X size={10} />
      </button>
    </span>
  )
}

function DestinationChip({
  node, onConfigure, onRemove,
}: {
  node: RFNode<NodeData>
  onConfigure: () => void
  onRemove: () => void
}) {
  const kind = node.data.ref_id as DestinationKind
  const meta = DEST_KINDS.find((d) => d.kind === kind)
  const Icon = meta?.icon || Cog
  const sub = destSubtitle(kind, node.data.config || {})
  const unconfigured = sub === 'unconfigured'
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px]"
      style={{
        background: `${destColor(kind)}1A`, color: destColor(kind),
        border: `1px solid ${unconfigured ? 'var(--warning)' : destColor(kind) + '60'}`,
      }}
    >
      <Icon size={10} />
      <button onClick={onConfigure} className="font-medium" title="Configure target">
        {meta?.label || kind}: {sub}
      </button>
      <button
        onClick={onRemove}
        title="Remove destination"
        style={{ color: destColor(kind), opacity: 0.6 }}
      >
        <X size={10} />
      </button>
    </span>
  )
}

// ── Input picker ──────────────────────────────────────────────────────
function InputPicker({
  datasets, scenarios, earlierSteps, excludeIds, onPick, onClose,
}: {
  datasets: Dataset[]
  scenarios: Scenario[]
  earlierSteps: StepInfo[]
  excludeIds: Set<string>
  onPick: (kind: 'dataset' | 'scenario' | 'step', refId: string) => void
  onClose: () => void
}) {
  return (
    <div
      className="rounded-lg p-2"
      style={{
        background: 'var(--bg-card)', border: '1px solid var(--accent)',
        boxShadow: '0 6px 20px rgba(0,0,0,0.08)',
        minWidth: 320,
      }}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>
          Pick input
        </span>
        <button onClick={onClose} className="p-0.5" style={{ color: 'var(--text-muted)' }}>
          <X size={11} />
        </button>
      </div>

      {earlierSteps.length > 0 && (
        <Group label="Earlier steps">
          {earlierSteps.filter((s) => !excludeIds.has(s.nodeId)).map((s) => (
            <PickRow
              key={s.nodeId} icon={Boxes} color="#7C3AED"
              title={`Step ${s.number}: ${s.modelTitle}`}
              onClick={() => onPick('step', s.nodeId)}
            />
          ))}
        </Group>
      )}
      <Group label={`Datasets (${datasets.length})`}>
        {datasets.length === 0 && <Empty>None bound. Use the Data tab.</Empty>}
        {datasets.filter((d) => !Array.from(excludeIds).some((id) => id.includes(d.id))).map((d) => (
          <PickRow
            key={d.id} icon={Database} color="#059669"
            title={d.name}
            sub={`${d.source_kind} · ${d.columns.length} cols`}
            onClick={() => onPick('dataset', d.id)}
          />
        ))}
      </Group>
      <Group label={`Scenarios (${scenarios.length})`}>
        {scenarios.length === 0 && <Empty>None available.</Empty>}
        {scenarios.filter((s) => !Array.from(excludeIds).some((id) => id.includes(s.id))).map((s) => (
          <PickRow
            key={s.id} icon={FlaskConical} color="#0891B2"
            title={s.name}
            sub={`${s.severity} · ${s.variables.length} vars`}
            onClick={() => onPick('scenario', s.id)}
          />
        ))}
      </Group>
    </div>
  )
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-1">
      <div className="text-[9px] font-bold uppercase tracking-widest px-1 py-0.5" style={{ color: 'var(--text-muted)' }}>
        {label}
      </div>
      <div className="space-y-0.5 max-h-40 overflow-y-auto">{children}</div>
    </div>
  )
}

function PickRow({
  icon: I, color, title, sub, onClick,
}: { icon: any; color: string; title: string; sub?: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2 px-2 py-1 rounded-md text-left transition-colors"
      style={{ background: 'transparent' }}
      onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = 'var(--bg-elevated)')}
      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
    >
      <I size={11} style={{ color, flexShrink: 0 }} />
      <div className="min-w-0 flex-1">
        <div className="text-[12px] font-medium truncate" style={{ color: 'var(--text-primary)' }}>{title}</div>
        {sub && <div className="text-[10px] truncate" style={{ color: 'var(--text-muted)' }}>{sub}</div>}
      </div>
    </button>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="text-[10px] px-2 py-1" style={{ color: 'var(--text-muted)' }}>{children}</div>
}

// ── helpers ───────────────────────────────────────────────────────────
function wouldCreateCycle(targetId: string, sourceId: string, edges: Edge[]): boolean {
  // Cycle test: is there already a path from target → source?
  const adj = new Map<string, string[]>()
  for (const e of edges) {
    if (!adj.has(e.source)) adj.set(e.source, [])
    adj.get(e.source)!.push(e.target)
  }
  const visited = new Set<string>()
  const stack = [targetId]
  while (stack.length) {
    const v = stack.pop()!
    if (v === sourceId) return true
    if (visited.has(v)) continue
    visited.add(v)
    for (const n of adj.get(v) || []) stack.push(n)
  }
  return false
}
