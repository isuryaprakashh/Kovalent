from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.models import EvidencePacket, OrchestratorReport, Recommendation, RunbookStep

logger = logging.getLogger(__name__)

# System prompt enforces tool-gated pattern: LLM never sees raw metrics,
# only the structured evidence packet.
_SYSTEM_PROMPT = """\
You are the Kovalent Intelligence Engine — an expert Kubernetes SRE assistant.

You will receive a structured evidence packet containing:
- trigger_pod: the pod that initially triggered the anomaly
- anomaly_type: the type of anomaly detected
- anomaly_score: a 0-1 score of severity
- causal_chain: ranked list of upstream pods with causal scores and lag
- agent_findings: deterministic findings from specialized agents
- graph_snapshot: the current dependency graph

Your task:
1. Analyze the evidence to identify the most likely root cause.
2. Explain the propagation path from root cause to the trigger pod.
3. Provide actionable recommendations (never suggest destructive actions without caveats).
4. Estimate your confidence (0 to 1) based on the evidence quality.

Respond ONLY with valid JSON matching this schema:
{
  "summary": "string — 1-2 sentence executive summary",
  "root_cause_pod": "string — the pod most likely causing the issue",
  "confidence": number,
  "explanation": "string — detailed causal explanation",
  "propagation_path": ["pod_a", "pod_b", "pod_c"],
  "recommendations": [{"action": "string", "target": "string", "rationale": "string"}]
}
"""


class LlmClient:
    """Google Gemini API wrapper for LLM-synthesized incident reports.

    Falls back to deterministic template when GOOGLE_API_KEY is not set.
    """

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key
        self.model = model
        self._client: Any | None = None
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._client = genai.GenerativeModel(
                    model_name=model,
                    system_instruction=_SYSTEM_PROMPT,
                )
                logger.info("LlmClient: Gemini API configured with model %s.", model)
            except Exception as exc:
                logger.warning("LlmClient: Failed to initialize Gemini — %s. Using deterministic mode.", exc)
                self._client = None
        else:
            logger.info("LlmClient: No GOOGLE_API_KEY — running in deterministic demo mode.")

    async def analyze(self, evidence: EvidencePacket) -> dict[str, Any]:
        """Send the evidence packet to the LLM and return a parsed response."""
        if self._client is not None:
            return await self._call_gemini(evidence)
        return self._deterministic_report(evidence)

    async def _call_gemini(self, evidence: EvidencePacket) -> dict[str, Any]:
        """Call Google Gemini API with the evidence packet."""
        prompt = (
            "Analyze this Kubernetes incident evidence and respond with the JSON schema described in your instructions.\n\n"
            f"```json\n{evidence.model_dump_json(indent=2)}\n```"
        )
        try:
            response = self._client.generate_content(prompt)
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines)
            return json.loads(text)
        except Exception as exc:
            logger.error("Gemini API call failed: %s. Falling back to deterministic mode.", exc)
            return self._deterministic_report(evidence)

    def _deterministic_report(self, evidence: EvidencePacket) -> dict[str, Any]:
        """Generate a structured report without an LLM, using the evidence packet."""
        trigger = evidence.trigger_pod
        chain = evidence.causal_chain
        top_cause = chain[0].pod if chain else trigger
        propagation = [entry.pod for entry in chain[:5]]
        if trigger not in propagation:
            propagation.append(trigger)

        # Build explanation from findings
        finding_summaries = [f.message for f in evidence.agent_findings[:5]]
        explanation = (
            f"The primary anomaly ({evidence.anomaly_type}) was detected on {trigger} "
            f"with a severity score of {evidence.anomaly_score:.2f}. "
            f"Causal analysis traces the root cause to {top_cause}. "
        )
        if finding_summaries:
            explanation += "Supporting evidence: " + "; ".join(finding_summaries) + "."

        recommendations: list[dict[str, str]] = []
        _runbook = _RUNBOOKS.get(evidence.anomaly_type, _RUNBOOKS["default"])
        for step in _runbook:
            recommendations.append({
                "action": step["action"],
                "target": top_cause,
                "rationale": step["rationale"],
            })

        confidence = min(0.95, 0.4 + evidence.anomaly_score * 0.3 + len(chain) * 0.05)

        return {
            "summary": f"{evidence.anomaly_type.replace('_', ' ').title()} detected on {trigger}, "
                       f"likely caused by {top_cause}.",
            "root_cause_pod": top_cause,
            "confidence": round(confidence, 2),
            "explanation": explanation,
            "propagation_path": propagation,
            "recommendations": recommendations,
        }


# ---------------------------------------------------------------------------
# Runbook templates per root cause type
# ---------------------------------------------------------------------------

_RUNBOOKS: dict[str, list[dict[str, str]]] = {
    "cpu_saturation": [
        {"action": "Check current CPU requests/limits", "rationale": "Verify the pod isn't being throttled by Kubernetes CFS quota."},
        {"action": "Review recent deployments and traffic spikes", "rationale": "A code change or traffic surge may have increased CPU demand."},
        {"action": "Scale horizontally or increase CPU limits", "rationale": "If load is legitimate, add replicas or raise the limit to prevent throttling."},
    ],
    "memory_pressure": [
        {"action": "Inspect heap dumps and memory profiles", "rationale": "Identify memory leaks or unbounded cache growth."},
        {"action": "Review recent code changes affecting allocation", "rationale": "A new feature or dependency may have increased memory footprint."},
        {"action": "Increase memory limits or add OOM kill protection", "rationale": "Prevent cascading OOM kills that destabilize the node."},
    ],
    "pvc_latency": [
        {"action": "Check storage provisioner IOPS and latency metrics", "rationale": "The underlying disk may be saturated or degraded."},
        {"action": "Inspect database query patterns for hot keys", "rationale": "A poorly optimized query may be causing excessive I/O."},
        {"action": "Migrate to faster storage class or add read replicas", "rationale": "Reduce I/O pressure on the primary PVC."},
    ],
    "application_errors": [
        {"action": "Check application logs for error patterns", "rationale": "Identify the specific error class (5xx, connection refused, timeout)."},
        {"action": "Verify downstream dependency health", "rationale": "Errors may cascade from a failing database or external API."},
        {"action": "Roll back recent deployments if error rate correlates", "rationale": "A bad deploy is the most common cause of sudden error spikes."},
    ],
    "network_saturation": [
        {"action": "Check network policies and bandwidth limits", "rationale": "Network policies or CNI limits may be throttling traffic."},
        {"action": "Identify the top talkers with flow data", "rationale": "A single connection may be consuming disproportionate bandwidth."},
        {"action": "Scale out or add network load balancing", "rationale": "Distribute traffic across more endpoints to reduce per-pod load."},
    ],
    "default": [
        {"action": "Review recent changes to the affected workload", "rationale": "Most incidents correlate with a recent configuration or code change."},
        {"action": "Check resource utilization and limits", "rationale": "Resource pressure is the most common root cause category."},
        {"action": "Inspect dependency health and network connectivity", "rationale": "Cascading failures often originate from a downstream service."},
    ],
}


def build_runbook(anomaly_type: str, target_pod: str) -> list[RunbookStep]:
    """Generate a 3-step remediation runbook for the given root cause type."""
    template = _RUNBOOKS.get(anomaly_type, _RUNBOOKS["default"])
    return [
        RunbookStep(step=i + 1, action=step["action"], target=target_pod, rationale=step["rationale"])
        for i, step in enumerate(template[:3])
    ]


def build_report(
    incident_id: str,
    llm_response: dict[str, Any],
    anomaly_type: str,
) -> OrchestratorReport:
    """Assemble the final OrchestratorReport from the LLM response."""
    root_pod = llm_response.get("root_cause_pod", "unknown")
    recs = [
        Recommendation(
            action=r.get("action", ""),
            rationale=r.get("rationale", ""),
            priority="high" if i == 0 else "medium",
        )
        for i, r in enumerate(llm_response.get("recommendations", []))
    ]
    runbook = build_runbook(anomaly_type, root_pod)

    return OrchestratorReport(
        incident_id=incident_id,
        summary=llm_response.get("summary", ""),
        root_cause_pod=root_pod,
        confidence=llm_response.get("confidence", 0.5),
        explanation=llm_response.get("explanation", ""),
        propagation_path=llm_response.get("propagation_path", []),
        recommendations=recs,
        runbook=runbook,
        generated_at=datetime.now(timezone.utc),
    )
