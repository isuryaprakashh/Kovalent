from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(StrEnum):
    OK = "OK"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class PodMetric(BaseModel):
    namespace: str
    pod: str
    service: str
    cpu_millicores: float = Field(ge=0)
    cpu_limit_millicores: float = Field(gt=0)
    memory_mb: float = Field(ge=0)
    memory_limit_mb: float = Field(gt=0)
    network_rx_kbps: float = Field(ge=0)
    network_tx_kbps: float = Field(ge=0)
    pvc_name: str | None = None
    pvc_latency_ms: float | None = Field(default=None, ge=0)
    pvc_iops: float | None = Field(default=None, ge=0)
    error_rate_per_minute: float = Field(default=0, ge=0)
    restart_count: int = Field(default=0, ge=0)
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


class Topology(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]


class ClusterSnapshot(BaseModel):
    generated_at: datetime
    source: Literal["demo", "live", "live-fallback"] = "demo"
    metrics: list[PodMetric]
    findings: list[AgentFinding]
    insights: list[Insight]
    topology: Topology
