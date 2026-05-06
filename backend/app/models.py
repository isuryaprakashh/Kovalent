from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Severity(StrEnum):
    OK = "OK"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class LogErrorSignature(BaseModel):
    signature: str
    count: int = Field(ge=1)
    first_seen: datetime
    last_seen: datetime
    sample: str


class PodMetric(BaseModel):
    namespace: str
    pod: str
    service: str
    owner_kind: str | None = None
    owner_name: str | None = None
    node_name: str | None = None
    cpu_millicores: float = Field(ge=0)
    cpu_limit_millicores: float = Field(gt=0)
    cpu_request_millicores: float | None = Field(default=None, ge=0)
    cpu_throttled_percent: float | None = Field(default=None, ge=0)
    memory_mb: float = Field(ge=0)
    memory_limit_mb: float = Field(gt=0)
    memory_request_mb: float | None = Field(default=None, ge=0)
    network_rx_kbps: float = Field(ge=0)
    network_tx_kbps: float = Field(ge=0)
    network_rx_drops_per_second: float | None = Field(default=None, ge=0)
    network_tx_drops_per_second: float | None = Field(default=None, ge=0)
    pvc_name: str | None = None
    pvc_mounts: list[str] = Field(default_factory=list)
    pvc_read_kbps: float | None = Field(default=None, ge=0)
    pvc_write_kbps: float | None = Field(default=None, ge=0)
    pvc_latency_ms: float | None = Field(default=None, ge=0)
    pvc_iops: float | None = Field(default=None, ge=0)
    error_rate_per_minute: float = Field(default=0, ge=0)
    error_signatures: list[LogErrorSignature] = Field(default_factory=list)
    restart_count: int = Field(default=0, ge=0)
    restart_reason: str | None = None
    last_termination_reason: str | None = None
    waiting_reason: str | None = None
    oom_killed: bool = False
    observed_at: datetime

    @property
    def cpu_ratio(self) -> float:
        return self.cpu_millicores / self.cpu_limit_millicores

    @property
    def memory_ratio(self) -> float:
        return self.memory_mb / self.memory_limit_mb


class AgentFinding(BaseModel):
    agent: str
    status: Severity
    pod: str
    service: str
    signal: str
    message: str
    value: float
    threshold: float


class WorkloadIdentity(BaseModel):
    namespace: str
    service: str
    pod: str | None = None
    node: str | None = None


class Anomaly(BaseModel):
    signal: str
    status: Severity
    workload: WorkloadIdentity
    value: float
    threshold: float | None = None
    baseline: float | None = None
    score: float = Field(ge=0, le=1)
    observed_at: datetime


class EvidenceItem(BaseModel):
    id: str
    kind: Literal["metric", "log", "event", "topology", "recommendation"]
    title: str
    message: str
    service: str
    namespace: str | None = None
    pod: str | None = None
    signal: str | None = None
    value: float | None = None
    threshold: float | None = None
    observed_at: datetime


class RootCauseCandidate(BaseModel):
    kind: str
    service: str
    pod: str | None = None
    resource: str | None = None
    confidence: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)


class RootCauseScoreBreakdown(BaseModel):
    anomaly_strength: float = Field(ge=0, le=1)
    dependency_centrality: float = Field(ge=0, le=1)
    temporal_precedence: float = Field(ge=0, le=1)
    blast_radius: float = Field(ge=0, le=1)
    recurrence: float = Field(ge=0, le=1)
    final_score: float = Field(ge=0, le=1)


class RankedRootCauseCandidate(BaseModel):
    candidate: RootCauseCandidate
    breakdown: RootCauseScoreBreakdown
    evidence_ids: list[str]
    explanation: str


class Recommendation(BaseModel):
    action: str
    rationale: str
    priority: Literal["low", "medium", "high"]


class Incident(BaseModel):
    id: str
    status: Severity
    title: str
    summary: str
    root_cause: RootCauseCandidate
    affected_services: list[str]
    evidence: list[EvidenceItem]
    recommendations: list[Recommendation]
    started_at: datetime
    updated_at: datetime


class LlmIncidentContext(BaseModel):
    incident_id: str
    task: str
    guardrails: list[str]
    incident: Incident
    ranked_candidates: list[RankedRootCauseCandidate]
    dependency_edges: list[DependencyEdge]
    evidence_summary: list[str]
    output_schema: dict


class RcaAnalysis(BaseModel):
    incident_id: str
    winning_candidate: RankedRootCauseCandidate
    candidates: list[RankedRootCauseCandidate]
    llm_context: LlmIncidentContext


class Insight(BaseModel):
    status: Severity
    event: str
    root_cause: str
    correlation: str
    recommendation: str
    affected_services: list[str]
    evidence: list[AgentFinding]


class TopologyNode(BaseModel):
    id: str
    label: str
    namespace: str
    kind: Literal["service", "pod", "pvc"]
    status: Severity


class TopologyEdge(BaseModel):
    source: str
    target: str
    relationship: Literal["owns", "calls", "mounts"]


class DependencyEdge(BaseModel):
    source: str
    target: str
    relationship: Literal["owns", "calls", "mounts", "co_located", "correlated_with", "temporal_influence"]
    score: float = Field(default=1, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class ResourceGraph(BaseModel):
    nodes: list[TopologyNode]
    edges: list[DependencyEdge]


class Topology(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]


class AnalysisContext(BaseModel):
    generated_at: datetime
    source: Literal["demo", "live", "live-fallback"] = "demo"
    metrics: list[PodMetric]
    findings: list[AgentFinding]
    topology: Topology


class ClusterSnapshot(BaseModel):
    generated_at: datetime
    source: Literal["demo", "live", "live-fallback"] = "demo"
    metrics: list[PodMetric]
    findings: list[AgentFinding]
    insights: list[Insight]
    topology: Topology


# ---------------------------------------------------------------------------
# M4 — Live Graph / Flow
# ---------------------------------------------------------------------------


class FlowRecord(BaseModel):
    """A single observed network flow from eBPF (Hubble/Tetragon) or mock."""
    source_pod: str
    source_namespace: str
    dest_pod: str
    dest_namespace: str
    bytes_per_sec: float = Field(ge=0)
    call_count: int = Field(ge=0)
    observed_at: datetime


class GraphSnapshot(BaseModel):
    """Serializable representation of a timestamped NetworkX graph."""
    timestamp: datetime
    node_link_data: dict[str, Any]


# ---------------------------------------------------------------------------
# M5 — Causal Engine
# ---------------------------------------------------------------------------


class CausalEdge(BaseModel):
    """A directed Granger-causal edge between two KPI series."""
    source_pod: str
    source_kpi: str
    target_pod: str
    target_kpi: str
    causal_strength: float = Field(ge=0, le=1)
    lag_seconds: float = Field(ge=0)


class RootCauseChainEntry(BaseModel):
    """One entry in a ranked root-cause chain from random walk with restart."""
    pod: str
    score: float = Field(ge=0, le=1)
    lag_seconds: float = Field(ge=0)


# ---------------------------------------------------------------------------
# M6 — Orchestrator / LLM
# ---------------------------------------------------------------------------


class EvidencePacket(BaseModel):
    """Structured evidence bundle sent to the LLM."""
    trigger_pod: str
    anomaly_type: str
    anomaly_score: float
    causal_chain: list[RootCauseChainEntry]
    agent_findings: list[AgentFinding]
    graph_snapshot: dict[str, Any]
    historical_context: list[str] = Field(default_factory=list)


class RunbookStep(BaseModel):
    """One step in a remediation runbook."""
    step: int
    action: str
    target: str
    rationale: str
    cli_command: str | None = None


class OrchestratorReport(BaseModel):
    """Final LLM-synthesized incident report."""
    incident_id: str
    summary: str
    root_cause_pod: str
    confidence: float = Field(ge=0, le=1)
    explanation: str
    propagation_path: list[str]
    recommendations: list[Recommendation]
    runbook: list[RunbookStep]
    causal_chain: list[RootCauseChainEntry] = Field(default_factory=list)
    historical_context: list[str] = Field(default_factory=list)
    is_historically_validated: bool = False
    generated_at: datetime
