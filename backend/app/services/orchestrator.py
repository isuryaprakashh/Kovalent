from __future__ import annotations

import logging
import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.models import (
    AgentFinding,
    CausalEdge,
    ClusterSnapshot,
    EvidencePacket,
    Incident,
    OrchestratorReport,
    RootCauseChainEntry,
)
from app.services.causal_engine import CausalEngine
from app.services.incident_service import IncidentService
from app.services.kpi_buffer import KpiBuffer
from app.services.live_graph import LiveGraphBuilder
from app.services.llm_client import LlmClient, build_report
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central intelligence orchestrator.

    - Collects agent findings from InsightService.
    - Queries the causal graph for root cause chain.
    - Assembles structured evidence packets.
    - Sends to Gemini LLM for synthesis (or uses deterministic mode).
    - Caches the last 50 incident reports.
    """

    def __init__(
        self,
        settings: Settings,
        incident_service: IncidentService,
        live_graph: LiveGraphBuilder,
        causal_engine: CausalEngine,
        kpi_buffer: KpiBuffer,
    ) -> None:
        self.settings = settings
        self.incident_service = incident_service
        self.live_graph = live_graph
        self.causal_engine = causal_engine
        self.kpi_buffer = kpi_buffer
        self.llm_client = LlmClient(api_key=settings.google_api_key)
        self._report_cache: deque[OrchestratorReport] = deque(maxlen=50)
        self.memory_service = MemoryService(api_key=settings.google_api_key)
        self._redis: Any | None = None
        self._init_redis()
        
        # M3 — Subscribe to AgentBus
        from app.services.agent_bus import agent_bus
        agent_bus.subscribe(self._on_agent_finding)

    def _on_agent_finding(self, finding: AgentFinding) -> None:
        """Handle real-time anomaly events from the specialist agents."""
        logger.info("Orchestrator: received finding from bus: %s [%s] on %s",
                    finding.agent, finding.signal, finding.pod)
        # This can trigger proactive actions or store events for future reports

    def _init_redis(self) -> None:
        try:
            import redis
            self._redis = redis.Redis.from_url(
                self.settings.redis_url, decode_responses=True, socket_connect_timeout=2,
            )
            self._redis.ping()
        except Exception:
            self._redis = None

    async def generate_report(self, incident_id: str) -> OrchestratorReport | None:
        """Build and cache a full LLM-synthesized report for an incident."""
        # Check cache first
        for report in self._report_cache:
            if report.incident_id == incident_id:
                return report

        # Check Redis
        if self._redis:
            try:
                cached_data = self._redis.get(f"kovalent:report:{incident_id}")
                if cached_data:
                    import json
                    data = json.loads(cached_data)
                    report = OrchestratorReport(**data)
                    self._report_cache.append(report)
                    logger.info("Orchestrator: Loaded report %s from Redis cache (LLM bypassed)", incident_id)
                    return report
            except Exception as e:
                logger.warning("Redis cache read failed: %s", e)

        # No cache or Redis — build from scratch with LLM
        logger.info("Orchestrator: generating new LLM report for incident %s", incident_id)
        incident = await self.incident_service.get_incident(incident_id)
        if incident is None:
            logger.warning("Orchestrator: incident %s no longer exists, skipping report.", incident_id)
            return None

        evidence_packet = self._assemble_evidence(incident)
        try:
            llm_response = await self.llm_client.analyze(evidence_packet)
            is_validated = len(evidence_packet.historical_context) > 0
            # FIX: pass kind as anomaly_type, not service
            report = build_report(
                incident_id, 
                llm_response, 
                incident.root_cause.kind, 
                is_historically_validated=is_validated,
                causal_chain=evidence_packet.causal_chain,
                historical_context=evidence_packet.historical_context
            )

            # RAG: Save incident to memory
            self.memory_service.add_incident(report)

            # Cache in memory
            self._report_cache.append(report)
            logger.info("Orchestrator: successfully generated report for %s", incident_id)
            return report
        except Exception as e:
            logger.error("Orchestrator: failed to generate report for %s: %s", incident_id, str(e))
            return None

        # Cache in Redis
        if self._redis:
            try:
                import json
                key = f"kovalent:report:{incident_id}"
                self._redis.setex(key, 3600, report.model_dump_json())
                # Maintain list of last 50
                self._redis.lpush("kovalent:reports", incident_id)
                self._redis.ltrim("kovalent:reports", 0, 49)
            except Exception:
                pass

        return report

    async def get_all_reports(self) -> list[OrchestratorReport]:
        """Return cached reports (most recent first)."""
        return list(reversed(self._report_cache))

    async def generate_all_reports(self) -> list[OrchestratorReport]:
        """Generate reports for all current incidents."""
        logger.info("Orchestrator: generating reports for all current incidents...")
        incidents = await self.incident_service.build_incidents()
        logger.info("Orchestrator: found %d current incidents.", len(incidents))
        
        # Parallelize report generation to avoid browser timeouts
        tasks = [self.generate_report(incident.id) for incident in incidents]
        reports = await asyncio.gather(*tasks)
        
        # Filter out failed/None reports
        final_reports = [r for r in reports if r is not None]
        logger.info("Orchestrator: successfully generated %d reports.", len(final_reports))
        return final_reports

    async def chat(self, user_message: str) -> str:
        """Handle a chat query from the user using LLM + RAG."""
        logger.info("Orchestrator: processing chat query: %s", user_message)
        
        # 1. Get current cluster state
        incidents = await self.incident_service.build_incidents()
        
        # 2. RAG: Search for historical context relevant to the user query
        historical = self.memory_service.search_similar(user_message)
        
        # 3. Build context string
        context = f"Current Incidents: {len(incidents)}\n"
        for inc in incidents[:5]:
            context += f"- {inc.title}: {inc.summary} (Status: {inc.status})\n"
        
        if historical:
            context += "\nRelevant Historical Context from RAG Memory:\n"
            for h in historical[:3]:
                context += f"- {h}\n"
                
        # 4. Call LLM
        response = await self.llm_client.chat(user_message, context)
        return response

    def ingest_snapshot(self, snapshot: ClusterSnapshot) -> None:
        """Feed the latest snapshot into the KPI buffer for causal analysis."""
        self.kpi_buffer.ingest(snapshot.metrics)

    def retrain_causal(self) -> None:
        """Trigger a causal engine retrain cycle."""
        if self.kpi_buffer.is_ready():
            self.causal_engine.retrain(self.kpi_buffer)
            logger.info("Orchestrator: causal retrain complete — %d edges.",
                        len(self.causal_engine.causal_graph.edges))
        else:
            fill = self.kpi_buffer.filled_fraction()
            logger.info("Orchestrator: buffer %.0f%% full, skipping retrain.", fill * 100)

    def _assemble_evidence(self, incident: Incident) -> EvidencePacket:
        """Build the structured evidence packet for the LLM."""
        trigger_pod = incident.root_cause.pod or incident.root_cause.service
        anomaly_type = incident.root_cause.kind

        # Get causal chain from the causal engine
        causal_chain = self.causal_engine.get_root_cause_chain(trigger_pod)

        # Convert evidence to agent findings format
        agent_findings: list[AgentFinding] = []
        for ev in incident.evidence:
            agent_findings.append(AgentFinding(
                agent="evidence",
                status=incident.status,
                pod=ev.pod or trigger_pod,
                service=ev.service,
                signal=ev.signal or anomaly_type,
                message=ev.message,
                value=ev.value or 0,
                threshold=ev.threshold or 0,
            ))

        # Get graph snapshot
        graph_data = self.live_graph.to_json()

        # RAG Memory Search
        query = f"Anomaly: {anomaly_type} on {trigger_pod}. Evidence: " + " ".join([f.message for f in agent_findings[:3]])
        historical_context = self.memory_service.search_similar(query)

        return EvidencePacket(
            trigger_pod=trigger_pod,
            anomaly_type=anomaly_type,
            anomaly_score=incident.root_cause.score,
            causal_chain=causal_chain,
            agent_findings=agent_findings,
            graph_snapshot=graph_data,
            historical_context=historical_context,
        )

    def get_causal_edges(self) -> list[CausalEdge]:
        """Return current causal graph edges."""
        return self.causal_engine.get_causal_edges()

    def get_root_cause_chain(self, pod_id: str) -> list[RootCauseChainEntry]:
        """Query the causal graph for root cause chain from a pod."""
        return self.causal_engine.get_root_cause_chain(pod_id)
