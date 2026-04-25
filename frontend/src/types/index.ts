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

export interface ChatMessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
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
  input_kind: 'scenario' | 'dataset'
  horizon_months: number
  status: 'completed' | 'failed' | 'running'
  summary: Record<string, any>
  series: Record<string, any>[]
  notes?: string | null
  error?: string | null
  created_at: string
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
}

export interface ToolTestResponse {
  ok: boolean
  result?: any
  error?: string | null
  traceback?: string | null
  duration_ms: number
}

export interface PlotConfig {
  id: string
  name: string
  chart_type: 'line' | 'bar' | 'area' | 'pie' | 'scatter' | 'stacked_bar'
  data_source_id?: string | null
  x_field: string
  y_fields: string[]
  aggregation: 'sum' | 'avg' | 'count' | 'min' | 'max' | 'none'
  filters: Record<string, any>[]
  description?: string | null
}
