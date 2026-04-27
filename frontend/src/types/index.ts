export interface BusinessFunction {
  id: string
  name: string
  short_name: string
  description: string
  icon: string
  color: string
  category: string
  default_views: string[]
  sample_metrics: string[]
}

export interface KpiCard {
  label: string
  value: string
  delta?: string | null
  delta_dir?: 'up' | 'down' | 'flat' | null
  sublabel?: string | null
}

export interface ChartSpec {
  id: string
  title: string
  type: 'line' | 'bar' | 'area' | 'pie' | 'scatter' | 'stacked_bar'
  data: Record<string, any>[]
  x_key: string
  y_keys: string[]
  description?: string | null
}

export interface TableSpec {
  title: string
  columns: string[]
  rows: (string | number | null)[][]
}

export interface WorkspaceData {
  function_id: string
  function_name: string
  kpis: KpiCard[]
  charts: ChartSpec[]
  tables: TableSpec[]
  insights: string[]
}

export interface AgentInfo {
  id: string
  name: string
  description: string
  icon: string
  color: string
}

export type ChatActionKind = 'apply_filter' | 'open_tab' | 'run_validation' | 'troubleshoot' | 'noop'

export interface ChatAction {
  kind: ChatActionKind
  label: string
  target?: string | null
  payload?: Record<string, any> | null
}

export interface ChatMessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  agent_id?: string
  agent_name?: string
  agent_color?: string | null
  agent_icon?: string | null
  actions?: ChatAction[]
}

export interface WorkflowValidationIssue {
  severity: 'error' | 'warning' | 'info'
  message: string
  node_id?: string | null
}

export interface WorkflowValidationResult {
  ok: boolean
  issues: WorkflowValidationIssue[]
}

export interface DataSource {
  id: string
  name: string
  type: 'snowflake' | 'onelake' | 'file_upload' | 'rest_api' | 'postgres' | 's3'
  status: 'connected' | 'disconnected' | 'pending' | 'error'
  connection_string?: string | null
  last_synced?: string | null
  description?: string | null
  config: Record<string, any>
}

export interface AgentSkill {
  id: string
  name: string
  description: string
  category: 'analytical' | 'reporting' | 'data' | 'risk' | 'custom'
  enabled: boolean
  instructions?: string | null
  tools: string[]
  source?: 'builtin' | 'user' | 'pack'
  pack_id?: string | null
}

export interface DatasetColumn {
  name: string
  dtype: string
  nullable: boolean
}

export interface Dataset {
  id: string
  function_id: string
  name: string
  description?: string | null
  source_kind: 'upload' | 'sql_table'
  data_source_id?: string | null
  table_ref?: string | null
  file_path?: string | null
  file_format?: 'csv' | 'parquet' | 'xlsx' | 'xls' | 'json' | null
  columns: DatasetColumn[]
  row_count?: number | null
  size_bytes?: number | null
  created_at: string
  last_synced?: string | null
}

export interface DatasetPreview {
  dataset_id: string
  columns: DatasetColumn[]
  sample_rows: Record<string, any>[]
  total_rows?: number | null
  truncated: boolean
}

export interface DataSourceTable {
  ref: string
  columns: { name: string; dtype: string }[]
}

export interface ModelMetric {
  name: string
  value: number
  asof: string
}

export interface TrainedModel {
  id: string
  function_id: string
  name: string
  description?: string | null
  source_kind: 'upload' | 'regression' | 'uri'
  model_type: 'ols' | 'logistic' | 'uploaded' | 'external'
  target_column?: string | null
  feature_columns: string[]
  coefficients?: Record<string, number> | null
  intercept?: number | null
  train_metrics: Record<string, number>
  monitoring_metrics: ModelMetric[]
  dataset_id?: string | null
  artifact_path?: string | null
  artifactory_uri?: string | null
  file_format?: string | null
  size_bytes?: number | null
  created_at: string
  last_run?: string | null
}

export interface ModelMetricsResponse {
  model_id: string
  series: Record<string, { asof: string; value: number }[]>
  train_metrics: Record<string, number>
}

export interface Scenario {
  id: string
  function_id?: string | null
  name: string
  description?: string | null
  severity: 'base' | 'adverse' | 'severely_adverse' | 'outlook' | 'custom'
  source_kind: 'upload' | 'sql_table' | 'builtin'
  dataset_id?: string | null
  variables: string[]
  horizon_months?: number | null
  created_at: string
}

export interface AnalyticsRun {
  id: string
  function_id: string
  name: string
  model_id: string
  scenario_id?: string | null
  dataset_id?: string | null
  input_kind: 'scenario' | 'dataset' | 'workflow'
  workflow_id?: string | null
  workflow_step_index?: number | null
  input_node_ids?: string[]
  horizon_months: number
  status: 'completed' | 'failed' | 'running'
  summary: Record<string, any>
  series: Record<string, any>[]
  notes?: string | null
  error?: string | null
  created_at: string
  duration_ms: number
}

export interface WorkflowNode {
  id: string
  kind: 'dataset' | 'scenario' | 'model' | 'destination'
  ref_id: string
  config?: Record<string, any>
}

export interface WorkflowEdge {
  source: string
  target: string
}

export type DestinationKind = 'snowflake_table' | 'onelake_table' | 's3' | 'csv'

export interface DestinationWrite {
  node_id: string
  kind: DestinationKind
  target: string
  upstream_model_id: string
  upstream_run_id: string
  rows_written: number
  status: 'written' | 'failed'
  note?: string | null
  csv_filename?: string | null
  csv_data?: Record<string, any>[] | null
}

export type NodeRunStatus = 'idle' | 'running' | 'completed' | 'failed' | 'skipped'

export interface WorkflowResult {
  workflow_id: string
  status: 'completed' | 'failed' | 'partial'
  runs: AnalyticsRun[]
  destinations: DestinationWrite[]
  node_status: Record<string, NodeRunStatus>
  error?: string | null
  duration_ms: number
}

export interface ToolParameter {
  name: string
  type: 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array'
  description?: string | null
  required: boolean
}

export interface PythonTool {
  id: string
  name: string
  description: string
  parameters: ToolParameter[]
  python_source: string
  function_name: string
  enabled: boolean
  last_test_result?: Record<string, any> | null
  source?: 'builtin' | 'user' | 'pack'
  pack_id?: string | null
}

export interface ToolDraftResponse {
  name: string
  description: string
  function_name: string
  parameters: ToolParameter[]
  python_source: string
  notes?: string | null
}

// ── Self-serve Analytics ─────────────────────────────────────────────────
export type AnalyticKind = 'aggregate' | 'compare' | 'custom_python'
export type AggFn =
  | 'sum' | 'avg' | 'count' | 'min' | 'max'
  | 'median' | 'p25' | 'p75' | 'p90' | 'p99'
  | 'weighted_avg' | 'stddev'

export interface AnalyticInputs {
  dataset_id?: string | null
  dataset_id_b?: string | null
  dataset_ids?: string[]
  run_id?: string | null
  scenario_id?: string | null
}

export interface AggregateMeasure {
  column: string
  agg: AggFn
  alias?: string | null
  weight_by?: string | null
}

export interface AggregateSpec {
  group_by: string[]
  measures: AggregateMeasure[]
  filters: { column: string; op: string; value: any }[]
  sort_by?: string | null
  sort_desc: boolean
  limit?: number | null
}

export interface CompareSpec {
  group_by: string[]
  measure: AggregateMeasure
  label_a: string
  label_b: string
  show_pct_change: boolean
}

export interface CustomPythonSpec {
  function_name: string
  python_source: string
}

export interface AnalyticOutput {
  chart_type: 'bar' | 'line' | 'area' | 'stacked_bar' | 'scatter' | 'pie' | 'table' | 'kpi'
  x_field?: string | null
  y_fields: string[]
  description?: string | null
}

export interface AnalyticDefinition {
  id: string
  function_id: string
  name: string
  description: string
  kind: AnalyticKind
  inputs: AnalyticInputs
  aggregate_spec?: AggregateSpec | null
  compare_spec?: CompareSpec | null
  custom_python_spec?: CustomPythonSpec | null
  output: AnalyticOutput
  parameters: Record<string, any>
  created_at: string
  updated_at?: string | null
  created_by?: string | null
}

export interface AnalyticResultTable {
  columns: string[]
  rows: any[][]
}

export interface AnalyticResultChart {
  type: string
  x_field?: string | null
  y_fields: string[]
  data: Record<string, any>[]
}

export interface AnalyticResultKpi {
  label: string
  value: string
  sublabel?: string | null
}

export interface AnalyticResult {
  table?: AnalyticResultTable | null
  chart?: AnalyticResultChart | null
  kpis: AnalyticResultKpi[]
}

export interface AnalyticDefinitionRun {
  id: string
  definition_id: string
  function_id: string
  name: string
  kind: AnalyticKind
  status: 'completed' | 'failed'
  result?: AnalyticResult | null
  narrative?: string | null
  error?: string | null
  created_at: string
  duration_ms: number
}

export interface AnalyticDraftResponse {
  name: string
  description: string
  kind: AnalyticKind
  inputs: AnalyticInputs
  aggregate_spec?: AggregateSpec | null
  compare_spec?: CompareSpec | null
  custom_python_spec?: CustomPythonSpec | null
  output: AnalyticOutput
  notes?: string | null
}

export interface ToolTestResponse {
  ok: boolean
  result?: any
  error?: string | null
  traceback?: string | null
  duration_ms: number
}

// ── Playbooks ──────────────────────────────────────────────────────────
export interface PlaybookPhaseInput {
  kind: 'dataset' | 'scenario' | 'phase_output' | 'prompt'
  ref_id?: string | null
  text?: string | null
}

export interface PlaybookPhase {
  id: string
  name: string
  skill_name: string
  instructions?: string | null
  inputs: PlaybookPhaseInput[]
  gate: boolean
}

export interface Playbook {
  id: string
  function_id: string
  name: string
  description?: string | null
  phases: PlaybookPhase[]
  created_at: string
  updated_at?: string | null
}

export interface TraceStep {
  kind: 'tool_call' | 'tool_output' | 'message' | 'reasoning' | 'handoff' | 'info'
  label: string
  detail?: string | null
  tool_name?: string | null
  agent_name?: string | null
  truncated?: boolean
  at?: string | null
}

export interface PhaseExecution {
  phase_id: string
  phase_name: string
  skill_name: string
  status: 'idle' | 'running' | 'awaiting_gate' | 'completed' | 'rejected' | 'failed'
  output?: string | null
  agent_id?: string | null
  gate_decision?: 'approve' | 'modify' | 'reject' | null
  gate_notes?: string | null
  duration_ms: number
  error?: string | null
  started_at?: string | null
  completed_at?: string | null
  trace?: TraceStep[]
}

export interface PlaybookRun {
  id: string
  playbook_id: string
  playbook_name: string
  function_id: string
  status: 'running' | 'awaiting_gate' | 'completed' | 'rejected' | 'failed'
  phases: PhaseExecution[]
  current_phase_idx: number
  final_report?: string | null
  created_at: string
  completed_at?: string | null
}

export interface PublishedReport {
  id: string
  function_id: string
  playbook_id: string
  playbook_name: string
  run_id: string
  title: string
  body_markdown: string
  published_by: string
  published_at: string
}

export interface PlaybookSkill {
  name: string
  description: string
  source: 'builtin' | 'user' | 'pack'
  pack_id?: string | null
  color?: string | null
  icon?: string | null
}

export interface PlotConfig {
  id: string
  function_id?: string | null
  name: string
  tile_type: 'plot' | 'table'
  chart_type: 'line' | 'bar' | 'area' | 'pie' | 'scatter' | 'stacked_bar'
  data_source_id?: string | null
  dataset_id?: string | null
  run_id?: string | null
  pinned_to_overview?: boolean
  table_columns?: string[] | null
  table_default_sort?: string | null
  table_default_sort_desc?: boolean
  x_field: string
  y_fields: string[]
  aggregation: 'sum' | 'avg' | 'count' | 'min' | 'max' | 'none'
  filters: Record<string, any>[]
  description?: string | null
}
