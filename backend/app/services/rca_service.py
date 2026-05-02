from __future__ import annotations

from collections import Counter

from app.models import (
    DependencyEdge,
    EvidenceItem,
    Incident,
    LlmIncidentContext,
    RankedRootCauseCandidate,
    RcaAnalysis,
    ResourceGraph,
    RootCauseCandidate,
    RootCauseScoreBreakdown,
)
from app.services.graph_service import GraphService
from app.services.incident_service import IncidentService


class RcaService:
    """Ranks root-cause candidates and builds LLM-ready incident context."""

    def __init__(self, incident_service: IncidentService, graph_service: GraphService) -> None:
        self.incident_service = incident_service
        self.graph_service = graph_service

    async def build_analyses(self) -> list[RcaAnalysis]:
        incidents = await self.incident_service.build_incidents()
        graph = await self.graph_service.build_graph()
        return [self.from_incident(incident, graph) for incident in incidents]

    async def get_analysis(self, incident_id: str) -> RcaAnalysis | None:
        analyses = await self.build_analyses()
        return next((analysis for analysis in analyses if analysis.incident_id == incident_id), None)

    def from_incident(self, incident: Incident, graph: ResourceGraph) -> RcaAnalysis:
        candidates = self._rank_candidates(incident, graph)
        winning = candidates[0]
        llm_context = self._llm_context(incident, candidates, graph)
        return RcaAnalysis(
            incident_id=incident.id,
            winning_candidate=winning,
            candidates=candidates,
            llm_context=llm_context,
        )

    def _rank_candidates(self, incident: Incident, graph: ResourceGraph) -> list[RankedRootCauseCandidate]:
        service_count = len({node.label for node in graph.nodes if node.kind == "service"}) or 1
        centrality = self._service_centrality(graph)
        earliest = min((item.observed_at for item in incident.evidence), default=incident.started_at)
        recurrence_by_key = Counter((item.service, item.signal) for item in incident.evidence)
        candidates: list[RankedRootCauseCandidate] = []

        for evidence in incident.evidence:
            if not evidence.signal:
                continue
            candidate = self._candidate_from_evidence(evidence, incident)
            anomaly_strength = self._anomaly_strength(evidence)
            dependency_centrality = centrality.get(evidence.service, 0)
            temporal_precedence = 1.0 if evidence.observed_at == earliest else 0.55
            blast_radius = min(1.0, len(incident.affected_services) / service_count)
            recurrence = min(1.0, recurrence_by_key[(evidence.service, evidence.signal)] / 3)
            final_score = (
                anomaly_strength * 0.35
                + dependency_centrality * 0.20
                + temporal_precedence * 0.25
                + blast_radius * 0.10
                + recurrence * 0.10
            )
            breakdown = RootCauseScoreBreakdown(
                anomaly_strength=round(anomaly_strength, 2),
                dependency_centrality=round(dependency_centrality, 2),
                temporal_precedence=round(temporal_precedence, 2),
                blast_radius=round(blast_radius, 2),
                recurrence=round(recurrence, 2),
                final_score=round(final_score, 2),
            )
            candidate.score = breakdown.final_score
            candidate.confidence = self._confidence(breakdown)
            candidates.append(
                RankedRootCauseCandidate(
                    candidate=candidate,
                    breakdown=breakdown,
                    evidence_ids=[evidence.id],
                    explanation=self._explanation(evidence, breakdown),
                )
            )

        if not candidates:
            candidates.append(self._fallback_candidate(incident))

        candidates.sort(key=lambda item: (self._signal_priority(item.candidate.kind), item.breakdown.final_score), reverse=True)
        return candidates

    def _candidate_from_evidence(self, evidence: EvidenceItem, incident: Incident) -> RootCauseCandidate:
        resource = None
        if evidence.signal == incident.root_cause.kind and evidence.service == incident.root_cause.service:
            resource = incident.root_cause.resource
        return RootCauseCandidate(
            kind=evidence.signal or "unknown",
            service=evidence.service,
            pod=evidence.pod,
            resource=resource,
            confidence=0.5,
            score=0.5,
        )

    def _anomaly_strength(self, evidence: EvidenceItem) -> float:
        if evidence.threshold and evidence.threshold > 0 and evidence.value is not None:
            return min(1.0, evidence.value / (evidence.threshold * 2))
        return 0.45

    def _service_centrality(self, graph: ResourceGraph) -> dict[str, float]:
        degree: Counter[str] = Counter()
        for edge in graph.edges:
            for node_id in (edge.source, edge.target):
                kind, label = node_id.split(":", 1)
                if kind == "svc":
                    degree[label] += 1
        max_degree = max(degree.values(), default=1)
        return {service: count / max_degree for service, count in degree.items()}

    def _confidence(self, breakdown: RootCauseScoreBreakdown) -> float:
        confidence = 0.35 + breakdown.final_score * 0.5
        if breakdown.temporal_precedence >= 0.9:
            confidence += 0.05
        return round(min(0.95, confidence), 2)

    def _explanation(self, evidence: EvidenceItem, breakdown: RootCauseScoreBreakdown) -> str:
        return (
            f"{evidence.service} is ranked because {evidence.signal} has anomaly strength "
            f"{breakdown.anomaly_strength:.2f}, dependency centrality {breakdown.dependency_centrality:.2f}, "
            f"and final RCA score {breakdown.final_score:.2f}."
        )

    def _fallback_candidate(self, incident: Incident) -> RankedRootCauseCandidate:
        breakdown = RootCauseScoreBreakdown(
            anomaly_strength=0.2,
            dependency_centrality=0.0,
            temporal_precedence=0.0,
            blast_radius=0.0,
            recurrence=0.0,
            final_score=0.2,
        )
        return RankedRootCauseCandidate(
            candidate=incident.root_cause,
            breakdown=breakdown,
            evidence_ids=[],
            explanation="No structured evidence was available, so the incident root cause was retained as a fallback.",
        )

    def _llm_context(
        self,
        incident: Incident,
        candidates: list[RankedRootCauseCandidate],
        graph: ResourceGraph,
    ) -> LlmIncidentContext:
        relevant_edges = self._relevant_edges(incident, graph)
        return LlmIncidentContext(
            incident_id=incident.id,
            task="Explain the incident, justify the ranked root cause, and recommend safe operator actions.",
            guardrails=[
                "Use only the provided structured evidence.",
                "Do not claim certainty beyond the confidence scores.",
                "Do not recommend destructive cluster changes without human approval.",
                "Prefer verification steps before remediation steps.",
            ],
            incident=incident,
            ranked_candidates=candidates,
            dependency_edges=relevant_edges,
            evidence_summary=[
                f"{item.title}: {item.message} value={item.value} threshold={item.threshold}"
                for item in incident.evidence
            ],
            output_schema={
                "summary": "string",
                "likely_root_cause": "string",
                "confidence": "number between 0 and 1",
                "evidence": ["string"],
                "recommended_actions": ["string"],
                "risk_notes": ["string"],
            },
        )

    def _relevant_edges(self, incident: Incident, graph: ResourceGraph) -> list[DependencyEdge]:
        affected_ids = {f"svc:{service}" for service in incident.affected_services}
        return [
            edge
            for edge in graph.edges
            if edge.source in affected_ids or edge.target in affected_ids or edge.evidence_ids
        ][:20]

    def _signal_priority(self, signal: str) -> int:
        return {
            "pvc_latency": 4,
            "memory_pressure": 3,
            "cpu_saturation": 2,
            "application_errors": 1,
        }.get(signal, 0)
