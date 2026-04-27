/**
 * Workflow shared logic — used by Canvas, Steps, and Spec views.
 *
 * Single source of truth: an array of ReactFlow Nodes (model/dataset/scenario
 * /destination) plus an array of Edges. Each view edits these and the others
 * stay in sync.
 *
 * - `computeSteps(nodes, edges)` — topo-sort model nodes for the Steps view
 * - `serializeSpec(nodes, edges, horizon)` / `parseSpec(yaml, available)` —
 *   YAML round-trip for the Spec view
 */
import { Node as RFNode, Edge, MarkerType } from '@xyflow/react'
import yaml from 'js-yaml'
import type { Dataset, AnalyticsRun, Scenario, TrainedModel, DestinationKind } from '@/types'

export interface NodeData extends Record<string, unknown> {
  kind: 'dataset' | 'scenario' | 'model' | 'destination'
  ref_id: string
  title: string
  subtitle: string
  color: string
  config?: Record<string, any>
  status?: 'idle' | 'running' | 'completed' | 'failed' | 'skipped'
}

export interface StepInfo {
  number: number              // 1-indexed display order
  nodeId: string              // the model node's id
  modelRefId: string          // mdl-...
  modelTitle: string
  inputs: RFNode<NodeData>[]
  destinations: RFNode<NodeData>[]
}

// ── topo-sort ─────────────────────────────────────────────────────────
export function computeSteps(nodes: RFNode<NodeData>[], edges: Edge[]): StepInfo[] {
  const incomingByTarget = new Map<string, string[]>()
  const outgoingBySource = new Map<string, string[]>()
  for (const e of edges) {
    if (!incomingByTarget.has(e.target)) incomingByTarget.set(e.target, [])
    if (!outgoingBySource.has(e.source)) outgoingBySource.set(e.source, [])
    incomingByTarget.get(e.target)!.push(e.source)
    outgoingBySource.get(e.source)!.push(e.target)
  }

  const modelNodes = nodes.filter((n) => n.data.kind === 'model')
  const depth = new Map<string, number>()
  const visiting = new Set<string>()

  function depthOf(id: string): number {
    if (depth.has(id)) return depth.get(id)!
    if (visiting.has(id)) return 0     // cycle — give up gracefully
    visiting.add(id)
    const inc = incomingByTarget.get(id) || []
    let d = 0
    for (const src of inc) {
      const srcNode = nodes.find((n) => n.id === src)
      if (!srcNode) continue
      // Only model dependencies bump depth — datasets/scenarios are level 0
      if (srcNode.data.kind === 'model') {
        d = Math.max(d, depthOf(src) + 1)
      }
    }
    visiting.delete(id)
    depth.set(id, d)
    return d
  }

  const sorted = [...modelNodes].sort((a, b) => {
    const da = depthOf(a.id), db = depthOf(b.id)
    if (da !== db) return da - db
    return a.id.localeCompare(b.id)
  })

  return sorted.map((n, i) => {
    const incomingIds = incomingByTarget.get(n.id) || []
    const outgoingIds = outgoingBySource.get(n.id) || []
    const inputs = incomingIds
      .map((id) => nodes.find((x) => x.id === id))
      .filter((x): x is RFNode<NodeData> => !!x)
    const destinations = outgoingIds
      .map((id) => nodes.find((x) => x.id === id))
      .filter((x): x is RFNode<NodeData> => !!x && x.data.kind === 'destination')
    return {
      number: i + 1,
      nodeId: n.id,
      modelRefId: n.data.ref_id,
      modelTitle: n.data.title,
      inputs,
      destinations,
    }
  })
}

// ── helpers for state mutations ─────────────────────────────────────
export function makeNodeId(kind: NodeData['kind'], refId: string): string {
  return `${kind}-${refId}-${Math.random().toString(36).slice(2, 7)}`
}

export function findOrCreateInputNode(
  nodes: RFNode<NodeData>[],
  kind: 'dataset' | 'scenario',
  refId: string,
  resolveTitle: () => { title: string; subtitle: string; color: string },
  position?: { x: number; y: number },
): { nodes: RFNode<NodeData>[]; nodeId: string } {
  // Reuse existing if present (one node per ref)
  const existing = nodes.find((n) => n.data.kind === kind && n.data.ref_id === refId)
  if (existing) return { nodes, nodeId: existing.id }
  const meta = resolveTitle()
  const id = makeNodeId(kind, refId)
  const newNode: RFNode<NodeData> = {
    id, type: kind,
    position: position || { x: 80, y: 80 + nodes.length * 70 },
    data: { kind, ref_id: refId, title: meta.title, subtitle: meta.subtitle, color: meta.color, status: 'idle' },
  }
  return { nodes: [...nodes, newNode], nodeId: id }
}

/** Build a styled edge for ReactFlow consistency across views. */
export function makeEdge(source: string, target: string): Edge {
  return {
    id: `e-${source}-${target}-${Math.random().toString(36).slice(2, 6)}`,
    source, target,
    animated: true,
    markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--accent)' },
    style: { stroke: 'var(--accent)', strokeWidth: 1.5 },
  }
}

/** Remove a node + all incident edges; if any input nodes become orphaned, remove them too. */
export function removeNodeAndCleanup(
  nodes: RFNode<NodeData>[],
  edges: Edge[],
  nodeId: string,
): { nodes: RFNode<NodeData>[]; edges: Edge[] } {
  const filteredEdges = edges.filter((e) => e.source !== nodeId && e.target !== nodeId)
  let filteredNodes = nodes.filter((n) => n.id !== nodeId)

  // Find inputs (datasets/scenarios) that no longer have any consumer
  const stillUsed = new Set<string>()
  for (const e of filteredEdges) stillUsed.add(e.source)
  filteredNodes = filteredNodes.filter((n) => {
    if (n.data.kind === 'dataset' || n.data.kind === 'scenario') {
      return stillUsed.has(n.id)
    }
    return true
  })
  return { nodes: filteredNodes, edges: filteredEdges }
}

// ── Spec (YAML) round-trip ────────────────────────────────────────────
export interface WorkflowSpec {
  horizon_months?: number
  inputs?: { id: string; kind: 'dataset' | 'scenario'; ref: string }[]
  steps?: {
    id: string
    model: string                // model ref id (mdl-...)
    name?: string
    inputs?: string[]            // logical ids of inputs or earlier steps
    destinations?: {
      kind: DestinationKind
      [key: string]: any
    }[]
  }[]
}

export function serializeSpec(
  nodes: RFNode<NodeData>[],
  edges: Edge[],
  horizon: number,
): string {
  const steps = computeSteps(nodes, edges)
  const inputs: WorkflowSpec['inputs'] = []
  const inputAlias = new Map<string, string>()  // node.id -> logical id
  let datasetIdx = 1
  let scenarioIdx = 1

  function alias(nodeId: string, kind: 'dataset' | 'scenario'): string {
    if (inputAlias.has(nodeId)) return inputAlias.get(nodeId)!
    const node = nodes.find((n) => n.id === nodeId)!
    const baseName = (node.data.title || `${kind}-${nodeId}`)
      .toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
    let logical = baseName
    // Avoid collisions
    const existingIds = new Set([...(inputs || []).map((i) => i.id), ...steps.map((s) => `step${s.number}`)])
    let n = 2
    while (existingIds.has(logical)) {
      logical = `${baseName}_${n}`; n++
    }
    inputAlias.set(nodeId, logical)
    inputs!.push({ id: logical, kind, ref: node.data.ref_id })
    if (kind === 'dataset') datasetIdx++
    else scenarioIdx++
    return logical
  }

  // Pre-assign step logical ids (step1, step2, …)
  const stepAlias = new Map<string, string>()
  steps.forEach((s) => stepAlias.set(s.nodeId, `step${s.number}`))

  const stepDocs = steps.map((s) => {
    const logical = stepAlias.get(s.nodeId)!
    const inputIds: string[] = []
    for (const i of s.inputs) {
      if (i.data.kind === 'dataset' || i.data.kind === 'scenario') {
        inputIds.push(alias(i.id, i.data.kind))
      } else if (i.data.kind === 'model') {
        const a = stepAlias.get(i.id)
        if (a) inputIds.push(a)
      }
    }
    const dests = s.destinations.map((d) => ({
      kind: d.data.ref_id as DestinationKind,
      ...((d.data.config || {}) as Record<string, any>),
    }))
    const out: any = { id: logical, model: s.modelRefId, name: s.modelTitle }
    if (inputIds.length) out.inputs = inputIds
    if (dests.length) out.destinations = dests
    return out
  })

  const spec: WorkflowSpec = { horizon_months: horizon, inputs, steps: stepDocs }
  return yaml.dump(spec, { lineWidth: 120, noRefs: true, sortKeys: false })
}

export interface ParseAvailable {
  models: TrainedModel[]
  datasets: Dataset[]
  scenarios: Scenario[]
}

export interface ParseResult {
  nodes: RFNode<NodeData>[]
  edges: Edge[]
  horizon: number
  warnings: string[]
}

export function parseSpec(text: string, available: ParseAvailable): ParseResult {
  const warnings: string[] = []
  let parsed: any
  try {
    parsed = yaml.load(text)
  } catch (e: any) {
    throw new Error(`YAML parse failed: ${e.message}`)
  }
  if (parsed == null || typeof parsed !== 'object') {
    throw new Error('Spec must be a YAML mapping with `inputs` and `steps`.')
  }

  const horizon = Number(parsed.horizon_months ?? 12)
  const inputs = Array.isArray(parsed.inputs) ? parsed.inputs : []
  const steps = Array.isArray(parsed.steps) ? parsed.steps : []

  // Build logical-id → node-id map as we materialize
  const logical: Map<string, string> = new Map()
  const nodes: RFNode<NodeData>[] = []
  const edges: Edge[] = []
  let yPos = 80

  for (const inp of inputs) {
    const id = String(inp.id)
    const kind = inp.kind === 'scenario' ? 'scenario' : 'dataset'
    const ref = String(inp.ref)
    let title = ref, subtitle = '', color = kind === 'scenario' ? '#0891B2' : '#059669'
    if (kind === 'dataset') {
      const d = available.datasets.find((x) => x.id === ref)
      if (!d) {
        warnings.push(`Dataset \`${ref}\` not found — referenced as input \`${id}\``)
        continue
      }
      title = d.name; subtitle = `${d.source_kind} · ${d.columns.length} cols`
    } else {
      const s = available.scenarios.find((x) => x.id === ref)
      if (!s) {
        warnings.push(`Scenario \`${ref}\` not found — referenced as input \`${id}\``)
        continue
      }
      title = s.name; subtitle = `${s.severity} · ${s.variables.length} vars`
    }
    const nodeId = makeNodeId(kind, ref)
    nodes.push({
      id: nodeId, type: kind,
      position: { x: 80, y: yPos },
      data: { kind, ref_id: ref, title, subtitle, color, status: 'idle' },
    })
    yPos += 80
    logical.set(id, nodeId)
  }

  // Steps (and destinations within them)
  let xPos = 360
  for (const st of steps) {
    if (!st.id) {
      warnings.push('Skipped a step that had no `id`.')
      continue
    }
    if (!st.model) {
      warnings.push(`Step \`${st.id}\` has no \`model\`.`)
      continue
    }
    const m = available.models.find((x) => x.id === st.model)
    if (!m) {
      warnings.push(`Model \`${st.model}\` not found — step \`${st.id}\` will fail at run time.`)
    }
    const stepTitle = st.name || (m?.name ?? st.id)
    const stepSubtitle = m?.model_type?.toUpperCase() || 'MODEL'
    const stepNodeId = makeNodeId('model', st.model)
    nodes.push({
      id: stepNodeId, type: 'model',
      position: { x: xPos, y: 80 + (steps.indexOf(st) * 100) },
      data: {
        kind: 'model', ref_id: st.model,
        title: stepTitle, subtitle: stepSubtitle,
        color: '#7C3AED', status: 'idle',
      },
    })
    logical.set(st.id, stepNodeId)
    xPos += 240

    // Inputs → edges
    for (const inputId of st.inputs || []) {
      const srcNodeId = logical.get(String(inputId))
      if (!srcNodeId) {
        warnings.push(`Step \`${st.id}\` references input \`${inputId}\` which isn't declared.`)
        continue
      }
      edges.push(makeEdge(srcNodeId, stepNodeId))
    }

    // Destinations
    for (const dest of st.destinations || []) {
      if (!dest.kind) continue
      const config = { ...dest }; delete (config as any).kind
      const destNodeId = makeNodeId('destination', dest.kind)
      const destSubtitle =
        dest.kind === 'snowflake_table' || dest.kind === 'onelake_table' ? `${(config as any).table || '?'}`
        : dest.kind === 's3' ? `s3://${(config as any).bucket || '?'}`
        : dest.kind === 'csv' ? `${(config as any).filename || 'output.csv'}`
        : 'unconfigured'
      const destColor =
        dest.kind === 'snowflake_table' ? '#29B5E8'
        : dest.kind === 'onelake_table' ? '#0078D4'
        : dest.kind === 's3' ? '#D97706'
        : '#7C3AED'
      nodes.push({
        id: destNodeId, type: 'destination',
        position: { x: xPos + 100, y: 80 + (steps.indexOf(st) * 100) + 40 * (st.destinations || []).indexOf(dest) },
        data: {
          kind: 'destination', ref_id: dest.kind,
          title: dest.kind, subtitle: destSubtitle,
          color: destColor, config, status: 'idle',
        },
      })
      edges.push(makeEdge(stepNodeId, destNodeId))
    }
  }

  return { nodes, edges, horizon, warnings }
}

// ── small helpers used across views ─────────────────────────────────
export function destSubtitle(kind: DestinationKind, config: Record<string, any>): string {
  if (kind === 'snowflake_table' || kind === 'onelake_table') {
    return `${config.table || '?'} · ${config.mode || 'append'}`
  }
  if (kind === 's3') return `s3://${config.bucket || '?'} · ${config.format || 'parquet'}`
  if (kind === 'csv') return config.filename || 'output.csv'
  return 'unconfigured'
}

export function destColor(kind: DestinationKind): string {
  return {
    snowflake_table: '#29B5E8',
    onelake_table:   '#0078D4',
    s3:              '#D97706',
    csv:             '#7C3AED',
  }[kind]
}
