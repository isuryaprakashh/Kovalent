from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.models import EvidencePacket, OrchestratorReport, Recommendation, RunbookStep, RootCauseChainEntry

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
- historical_context: retrieved past incidents similar to this one (if any)

Your task:
1. Analyze the evidence to identify the most likely root cause.
2. Explain the propagation path from root cause to the trigger pod.
3. If historical_context is provided, reference how it was solved before.
4. Provide actionable recommendations (never suggest destructive actions without caveats).
5. Estimate your confidence (0 to 1) based on the evidence quality.

Respond ONLY with valid JSON matching this schema:
{
  "recommendations": [{"action": "string", "target": "string", "rationale": "string"}]
}
"""

_CHAT_SYSTEM_PROMPT = """\
You are the Kovalent Intelligence Engine. You are helping a Kubernetes SRE analyze their cluster.
You have access to current cluster incidents and historical context.

Answer the user's questions clearly and concisely. 
If they ask about incidents, refer to the provided context. 
If historical data is provided, use it to explain how similar issues were handled.
Keep your tone professional, technical, and helpful.
"""


class LlmClient:
    """Google Gemini API wrapper for LLM-synthesized incident reports.

    Falls back to deterministic template when GOOGLE_API_KEY is not set.
    """

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash-lite") -> None:
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
        """Call Google Gemini API with the evidence packet (with persistent caching)."""
        import hashlib
        import os
        
        # Build a deterministic signature for this incident type and context
        root_cause = evidence.causal_chain[0].pod if evidence.causal_chain else 'unknown'
        signature = f"{evidence.anomaly_type}_{evidence.trigger_pod}_{root_cause}"
        cache_key = hashlib.md5(signature.encode()).hexdigest()
        cache_file = f".llm_cache_{cache_key}.json"
        
        # Check persistent disk cache first
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    logger.info("LlmClient: Returning cached LLM response for %s", signature)
                    return json.load(f)
            except Exception:
                pass

        prompt = (
            "Analyze this Kubernetes incident evidence and respond with the JSON schema described in your instructions.\n\n"
            f"```json\n{evidence.model_dump_json(indent=2)}\n```"
        )
        try:
            try:
                response = self._client.generate_content(prompt)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    logger.warning("Gemini quota hit, falling back to gemini-3.1-flash-lite...")
                    import google.generativeai as genai
                    fallback_client = genai.GenerativeModel(model_name="gemini-3.1-flash-lite", system_instruction=_SYSTEM_PROMPT)
                    response = fallback_client.generate_content(prompt)
                else:
                    raise e
                    
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines)
            
            result_json = json.loads(text)
            
            # Save to persistent cache
            try:
                with open(cache_file, "w") as f:
                    json.dump(result_json, f)
            except Exception as e:
                logger.warning("Failed to write LLM cache: %s", e)
                
            return result_json
        except Exception as exc:
            logger.error("Gemini API call failed: %s. Falling back to deterministic mode.", exc)
            return self._deterministic_report(evidence)

    async def chat(self, user_message: str, context: str) -> str:
        """Handle a general chat query using Gemini."""
        if self._client is None:
            return "I'm running in deterministic mode without a Gemini API key. I can see the cluster state, but I can't engage in complex reasoning. Please provide a GOOGLE_API_KEY to enable full chat capabilities."

        prompt = (
            f"Context:\n{context}\n\n"
            f"User Question: {user_message}\n\n"
            "Response:"
        )
        try:
            # We use a separate model instance with the chat system prompt
            import google.generativeai as genai
            chat_model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=_CHAT_SYSTEM_PROMPT,
            )
            response = chat_model.generate_content(prompt)
            return response.text.strip()
        except Exception as exc:
            logger.error("Gemini Chat failed: %s", exc)
            return f"I encountered an error while processing your request: {str(exc)}"

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
        {"action": "Check current CPU requests/limits", "rationale": "Verify the pod isn't being throttled by Kubernetes CFS quota.", "cli_command": "kubectl describe pod {target} | grep -A 5 Limits"},
        {"action": "Review recent deployments and traffic spikes", "rationale": "A code change or traffic surge may have increased CPU demand.", "cli_command": "kubectl get hpa,deployments -l app={target}"},
        {"action": "Scale horizontally or increase CPU limits", "rationale": "If load is legitimate, add replicas or raise the limit to prevent throttling.", "cli_command": "kubectl scale deployment {target} --replicas=3"},
    ],
    "memory_pressure": [
        {"action": "Inspect heap dumps and memory profiles", "rationale": "Identify memory leaks or unbounded cache growth.", "cli_command": "kubectl top pod {target}"},
        {"action": "Review recent code changes affecting allocation", "rationale": "A new feature or dependency may have increased memory footprint.", "cli_command": "kubectl logs {target} --tail=100 | grep -i oom"},
        {"action": "Increase memory limits or add OOM kill protection", "rationale": "Prevent cascading OOM kills that destabilize the node.", "cli_command": "kubectl set resources deployment {target} --limits=memory=2Gi"},
    ],
    "pvc_latency": [
        {"action": "Check storage provisioner IOPS and latency metrics", "rationale": "The underlying disk may be saturated or degraded.", "cli_command": "kubectl describe pvc -l app={target}"},
        {"action": "Inspect database query patterns for hot keys", "rationale": "A poorly optimized query may be causing excessive I/O.", "cli_command": "kubectl logs {target} --tail=100 | grep -i slow"},
        {"action": "Migrate to faster storage class or add read replicas", "rationale": "Reduce I/O pressure on the primary PVC.", "cli_command": "kubectl scale statefulset {target} --replicas=3"},
    ],
    "application_errors": [
        {"action": "Check application logs for error patterns", "rationale": "Identify the specific error class (5xx, connection refused, timeout).", "cli_command": "kubectl logs {target} --tail=500 | grep -i error"},
        {"action": "Verify downstream dependency health", "rationale": "Errors may cascade from a failing database or external API.", "cli_command": "kubectl get pods -n default"},
        {"action": "Roll back recent deployments if error rate correlates", "rationale": "A bad deploy is the most common cause of sudden error spikes.", "cli_command": "kubectl rollout undo deployment {target}"},
    ],
    "pod_restarts": [
        {"action": "Check pod events and exit codes", "rationale": "Identify whether restarts are due to OOMKilled, liveness probe failures, or application crashes.", "cli_command": "kubectl describe pod {target} | grep -A 10 'Last State'"},
        {"action": "Review container logs from previous instance", "rationale": "The previous container's logs often reveal the crash root cause.", "cli_command": "kubectl logs {target} --previous --tail=200"},
        {"action": "Adjust resource limits or fix liveness probes", "rationale": "If OOM or probe timeouts are the cause, tuning limits or probe parameters prevents the restart loop.", "cli_command": "kubectl get pod {target} -o jsonpath='{.spec.containers[*].resources}'"},
    ],
    "network_saturation": [
        {"action": "Check network policies and bandwidth limits", "rationale": "Network policies or CNI limits may be throttling traffic.", "cli_command": "kubectl get networkpolicy -n default"},
        {"action": "Identify the top talkers with flow data", "rationale": "A single connection may be consuming disproportionate bandwidth.", "cli_command": "kubectl top pods --sort-by=network"},
        {"action": "Scale out or add network load balancing", "rationale": "Distribute traffic across more endpoints to reduce per-pod load.", "cli_command": "kubectl scale deployment {target} --replicas=3"},
    ],
    "default": [
        {"action": "Review recent changes to the affected workload", "rationale": "Most incidents correlate with a recent configuration or code change.", "cli_command": "kubectl rollout history deployment {target}"},
        {"action": "Check resource utilization and limits", "rationale": "Resource pressure is the most common root cause category.", "cli_command": "kubectl top pod {target}"},
        {"action": "Inspect dependency health and network connectivity", "rationale": "Cascading failures often originate from a downstream service.", "cli_command": "kubectl get events --sort-by='.metadata.creationTimestamp'"},
    ],
}


def build_runbook(anomaly_type: str, target_pod: str) -> list[RunbookStep]:
    """Generate a 3-step remediation runbook for the given root cause type."""
    base_target = "-".join(target_pod.split("-")[:-1]) if "-" in target_pod else target_pod
    if not base_target: base_target = target_pod
    
    template = _RUNBOOKS.get(anomaly_type, _RUNBOOKS["default"])
    return [
        RunbookStep(
            step=i + 1, 
            action=step["action"], 
            target=target_pod, 
            rationale=step["rationale"],
            cli_command=step.get("cli_command", "").replace("{target}", base_target) if step.get("cli_command") else None
        )
        for i, step in enumerate(template[:3])
    ]


def build_report(
    incident_id: str,
    llm_response: dict[str, Any],
    anomaly_type: str,
    is_historically_validated: bool = False,
    causal_chain: list[RootCauseChainEntry] | None = None,
    historical_context: list[str] | None = None,
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
        summary=llm_response.get("summary", llm_response.get("executive_summary", "")),
        root_cause_pod=root_pod,
        confidence=llm_response.get("confidence", 0.5),
        explanation=llm_response.get("explanation", ""),
        propagation_path=llm_response.get("propagation_path", []),
        recommendations=recs,
        runbook=runbook,
        causal_chain=causal_chain or [],
        historical_context=historical_context or [],
        is_historically_validated=is_historically_validated,
        generated_at=datetime.now(timezone.utc),
    )
