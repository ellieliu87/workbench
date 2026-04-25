"""Pydantic schemas for the CMA Workbench API."""
from typing import Any, Literal
from pydantic import BaseModel, Field


# ── Auth ────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    department: str


class UserInfo(BaseModel):
    username: str
    role: str
    department: str


# ── Business Functions ──────────────────────────────────────────────────────
class BusinessFunction(BaseModel):
    id: str
    name: str
    short_name: str
    description: str
    icon: str
    color: str
    category: str
    default_views: list[str]
    sample_metrics: list[str]


# ── Workspace / Views ───────────────────────────────────────────────────────
class KpiCard(BaseModel):
    label: str
    value: str
    delta: str | None = None
    delta_dir: Literal["up", "down", "flat"] | None = None
    sublabel: str | None = None


class TableSpec(BaseModel):
    title: str
    columns: list[str]
    rows: list[list[Any]]


class ChartPoint(BaseModel):
    x: Any
    y: float
    series: str | None = None


class ChartSpec(BaseModel):
    id: str
    title: str
    type: Literal["line", "bar", "area", "pie", "scatter", "stacked_bar"]
    data: list[dict[str, Any]]
    x_key: str
    y_keys: list[str]
    description: str | None = None


class WorkspaceData(BaseModel):
    function_id: str
    function_name: str
    kpis: list[KpiCard]
    charts: list[ChartSpec]
    tables: list[TableSpec]
    insights: list[str]


# ── Chat ────────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    message: str
    function_id: str | None = None
    agent_id: str = "orchestrator"
    context: str | None = None


class ChatResponse(BaseModel):
    response: str
    agent_id: str
    agent_name: str


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    color: str


# ── Data Sources ────────────────────────────────────────────────────────────
class DataSource(BaseModel):
    id: str
    name: str
    type: Literal["snowflake", "onelake", "file_upload", "rest_api", "postgres", "s3"]
    status: Literal["connected", "disconnected", "pending", "error"]
    connection_string: str | None = None
    last_synced: str | None = None
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class DataSourceCreate(BaseModel):
    name: str
    type: Literal["snowflake", "onelake", "file_upload", "rest_api", "postgres", "s3"]
    description: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


# ── Agent Skills ────────────────────────────────────────────────────────────
class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    category: Literal["analytical", "reporting", "data", "risk", "custom"]
    enabled: bool
    instructions: str | None = None
    tools: list[str] = Field(default_factory=list)


class AgentSkillCreate(BaseModel):
    name: str
    description: str
    category: Literal["analytical", "reporting", "data", "risk", "custom"]
    instructions: str | None = None
    tools: list[str] = Field(default_factory=list)


class AgentSkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: Literal["analytical", "reporting", "data", "risk", "custom"] | None = None
    instructions: str | None = None
    tools: list[str] | None = None
    enabled: bool | None = None


# ── Python Tools ────────────────────────────────────────────────────────────
class ToolParameter(BaseModel):
    name: str
    type: Literal["string", "number", "integer", "boolean", "object", "array"] = "string"
    description: str | None = None
    required: bool = True


class PythonTool(BaseModel):
    id: str
    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)
    python_source: str
    function_name: str
    enabled: bool = True
    last_test_result: dict[str, Any] | None = None


class PythonToolCreate(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)
    python_source: str
    function_name: str


class PythonToolUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parameters: list[ToolParameter] | None = None
    python_source: str | None = None
    function_name: str | None = None
    enabled: bool | None = None


class ToolTestRequest(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)


class ToolTestResponse(BaseModel):
    ok: bool
    result: Any = None
    error: str | None = None
    traceback: str | None = None
    duration_ms: float = 0.0


# ── Datasets ────────────────────────────────────────────────────────────────
class DatasetColumn(BaseModel):
    name: str
    dtype: str  # pandas dtype string (e.g. 'int64', 'float64', 'object')
    nullable: bool = True


class Dataset(BaseModel):
    id: str
    function_id: str
    name: str
    description: str | None = None
    source_kind: Literal["upload", "sql_table"]
    data_source_id: str | None = None
    table_ref: str | None = None
    file_path: str | None = None
    file_format: Literal["csv", "parquet", "xlsx", "xls", "json"] | None = None
    columns: list[DatasetColumn] = Field(default_factory=list)
    row_count: int | None = None
    size_bytes: int | None = None
    created_at: str
    last_synced: str | None = None


class DatasetCreateFromTable(BaseModel):
    function_id: str
    name: str
    description: str | None = None
    data_source_id: str
    table_ref: str


class DatasetPreview(BaseModel):
    dataset_id: str
    columns: list[DatasetColumn]
    sample_rows: list[dict[str, Any]]
    total_rows: int | None = None
    truncated: bool = False


# ── Models ──────────────────────────────────────────────────────────────────
class ModelMetric(BaseModel):
    name: str
    value: float
    asof: str


class TrainedModel(BaseModel):
    id: str
    function_id: str
    name: str
    description: str | None = None
    source_kind: Literal["upload", "regression", "uri"]
    model_type: Literal["ols", "logistic", "uploaded", "external"]
    target_column: str | None = None
    feature_columns: list[str] = Field(default_factory=list)
    coefficients: dict[str, float] | None = None
    intercept: float | None = None
    train_metrics: dict[str, float] = Field(default_factory=dict)
    monitoring_metrics: list[ModelMetric] = Field(default_factory=list)
    dataset_id: str | None = None
    artifact_path: str | None = None
    artifactory_uri: str | None = None
    file_format: str | None = None
    size_bytes: int | None = None
    created_at: str
    last_run: str | None = None


class RegressionRequest(BaseModel):
    function_id: str
    name: str
    description: str | None = None
    dataset_id: str
    target_column: str
    feature_columns: list[str]
    model_type: Literal["ols", "logistic"] = "ols"


class FromUriRequest(BaseModel):
    function_id: str
    name: str
    description: str | None = None
    artifactory_uri: str
    model_type: Literal["uploaded", "external"] = "external"


# ── Scenarios & Analytics Runs ──────────────────────────────────────────────
class Scenario(BaseModel):
    id: str
    function_id: str | None = None  # None = global / org-wide
    name: str
    description: str | None = None
    severity: Literal["base", "adverse", "severely_adverse", "outlook", "custom"] = "custom"
    source_kind: Literal["upload", "sql_table", "builtin"]
    dataset_id: str | None = None  # for upload / sql_table
    variables: list[str] = Field(default_factory=list)  # macro variables present
    horizon_months: int | None = None
    created_at: str


class ScenarioCreateFromDataset(BaseModel):
    function_id: str | None = None
    name: str
    description: str | None = None
    severity: Literal["base", "adverse", "severely_adverse", "outlook", "custom"] = "custom"
    dataset_id: str


class AnalyticsRun(BaseModel):
    id: str
    function_id: str
    name: str
    model_id: str
    scenario_id: str | None = None
    dataset_id: str | None = None
    input_kind: Literal["scenario", "dataset"] = "scenario"
    horizon_months: int = 12
    status: Literal["completed", "failed", "running"]
    summary: dict[str, Any] = Field(default_factory=dict)
    series: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None
    error: str | None = None
    created_at: str
    duration_ms: float = 0.0


class RunRequest(BaseModel):
    function_id: str
    name: str | None = None
    model_id: str
    scenario_id: str | None = None
    dataset_id: str | None = None
    horizon_months: int = 12
    notes: str | None = None


# ── Plot Builder ────────────────────────────────────────────────────────────
class PlotConfig(BaseModel):
    id: str
    function_id: str | None = None
    name: str
    chart_type: Literal["line", "bar", "area", "pie", "scatter", "stacked_bar"]
    data_source_id: str | None = None
    dataset_id: str | None = None
    run_id: str | None = None
    x_field: str
    y_fields: list[str]
    aggregation: Literal["sum", "avg", "count", "min", "max", "none"] = "none"
    filters: list[dict[str, Any]] = Field(default_factory=list)
    description: str | None = None


class PlotConfigCreate(BaseModel):
    function_id: str | None = None
    name: str
    chart_type: Literal["line", "bar", "area", "pie", "scatter", "stacked_bar"]
    data_source_id: str | None = None
    dataset_id: str | None = None
    run_id: str | None = None
    x_field: str
    y_fields: list[str]
    aggregation: Literal["sum", "avg", "count", "min", "max", "none"] = "none"
    filters: list[dict[str, Any]] = Field(default_factory=list)
    description: str | None = None
