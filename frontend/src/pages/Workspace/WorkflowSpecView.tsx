import { useEffect, useMemo, useState } from 'react'
import { Node as RFNode, Edge } from '@xyflow/react'
import { Save, RotateCcw, AlertCircle, CheckCircle2, Copy, Download } from 'lucide-react'
import type { Dataset, Scenario, TrainedModel } from '@/types'
import { type NodeData, parseSpec, serializeSpec } from './workflowSpec'

interface Props {
  nodes: RFNode<NodeData>[]
  edges: Edge[]
  horizon: number
  models: TrainedModel[]
  datasets: Dataset[]
  scenarios: Scenario[]
  onApply: (next: { nodes: RFNode<NodeData>[]; edges: Edge[]; horizon: number }) => void
}

export default function WorkflowSpecView({
  nodes, edges, horizon, models, datasets, scenarios, onApply,
}: Props) {
  const baseline = useMemo(
    () => serializeSpec(nodes, edges, horizon),
    [nodes, edges, horizon],
  )
  const [text, setText] = useState(baseline)
  const [warnings, setWarnings] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [applied, setApplied] = useState(false)

  // Refresh editor when the underlying state changes (e.g. user switched to Steps,
  // edited there, came back). Only refresh if the editor matches the prior baseline.
  const [lastBaseline, setLastBaseline] = useState(baseline)
  useEffect(() => {
    if (text === lastBaseline && baseline !== lastBaseline) {
      setText(baseline)
      setLastBaseline(baseline)
    } else if (baseline !== lastBaseline) {
      // user has unsaved edits — leave the editor alone, but update lastBaseline
      // so the next sync round-trip works. Show a notice so they know.
      setLastBaseline(baseline)
    }
  }, [baseline]) // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = text !== baseline

  const apply = () => {
    setError(null); setWarnings([]); setApplied(false)
    try {
      const result = parseSpec(text, { models, datasets, scenarios })
      setWarnings(result.warnings)
      onApply({ nodes: result.nodes, edges: result.edges, horizon: result.horizon })
      setApplied(true)
      setTimeout(() => setApplied(false), 2500)
    } catch (e: any) {
      setError(String(e.message || e))
    }
  }

  const reset = () => {
    setText(baseline); setError(null); setWarnings([])
  }

  const copy = () => {
    navigator.clipboard?.writeText(text).catch(() => {})
  }

  const download = () => {
    const blob = new Blob([text], { type: 'application/x-yaml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `workflow-${new Date().toISOString().slice(0, 10)}.yml`
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
          Edit the workflow as YAML. <strong>Apply</strong> replaces the current canvas / steps state.
          Switching to Steps or Canvas while there are unsaved YAML edits keeps your edits in this tab; the views diverge until you Apply or Reset.
        </div>
        <div className="flex gap-1.5 shrink-0">
          <button
            onClick={copy}
            className="px-2 py-1.5 rounded-md text-[11px] flex items-center gap-1"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            title="Copy to clipboard"
          >
            <Copy size={11} /> Copy
          </button>
          <button
            onClick={download}
            className="px-2 py-1.5 rounded-md text-[11px] flex items-center gap-1"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            title="Download as .yml"
          >
            <Download size={11} /> Download
          </button>
          <button
            onClick={reset}
            disabled={!dirty}
            className="px-2 py-1.5 rounded-md text-[11px] flex items-center gap-1 disabled:opacity-40"
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            title="Discard unsaved edits"
          >
            <RotateCcw size={11} /> Reset
          </button>
          <button
            onClick={apply}
            disabled={!dirty}
            className="px-2.5 py-1.5 rounded-md text-[11px] font-semibold flex items-center gap-1 disabled:opacity-40"
            style={{ background: 'var(--accent)', color: '#fff' }}
            title="Parse YAML and replace state"
          >
            <Save size={11} /> Apply
          </button>
        </div>
      </div>

      <div
        className="rounded-lg overflow-hidden"
        style={{ border: `1px solid ${error ? 'var(--error)' : 'var(--border)'}` }}
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          spellCheck={false}
          className="w-full"
          style={{
            display: 'block',
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 12,
            lineHeight: 1.55,
            padding: 12,
            minHeight: 460,
            border: 'none',
            outline: 'none',
            resize: 'vertical',
            tabSize: 2,
          }}
        />
      </div>

      {error && (
        <div
          className="mt-2 px-3 py-2 rounded-md text-xs flex items-start gap-2"
          style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
        >
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <div>
            <div className="font-semibold mb-0.5">Could not apply spec</div>
            <code style={{ fontSize: 11 }}>{error}</code>
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div
          className="mt-2 px-3 py-2 rounded-md text-xs"
          style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}
        >
          <div className="flex items-start gap-2">
            <AlertCircle size={13} className="mt-0.5 shrink-0" />
            <div className="flex-1">
              <div className="font-semibold mb-0.5">{warnings.length} warning{warnings.length === 1 ? '' : 's'}</div>
              <ul className="space-y-0.5 font-mono">
                {warnings.map((w, i) => (
                  <li key={i}>· {w}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {applied && !error && warnings.length === 0 && (
        <div
          className="mt-2 px-3 py-2 rounded-md text-xs flex items-center gap-2"
          style={{ background: 'var(--success-bg)', color: 'var(--success)' }}
        >
          <CheckCircle2 size={13} /> Applied — Steps and Canvas updated.
        </div>
      )}
    </div>
  )
}
