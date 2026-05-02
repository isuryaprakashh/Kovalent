from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx


class KubernetesCollectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class KubernetesCollectorConfig:
    discovery_mode: str = "auto"
    namespace_regex: str = ".+"
    timeout_seconds: float = 8.0
    event_limit: int = 250


@dataclass(frozen=True)
class KubernetesEvent:
    namespace: str
    name: str
    reason: str | None
    message: str | None
    type: str | None
    involved_kind: str | None
    involved_name: str | None
    first_seen: str | None
    last_seen: str | None
    count: int = 1


@dataclass(frozen=True)
class KubernetesPod:
    namespace: str
    name: str
    service: str
    owner_kind: str | None
    owner_name: str | None
    workload_kind: str | None
    workload_name: str | None
    node_name: str | None
    pvc_mounts: list[str]
    restart_count: int
    restart_reason: str | None
    last_termination_reason: str | None
    waiting_reason: str | None
    oom_killed: bool
    phase: str | None
    events: list[KubernetesEvent] = field(default_factory=list)


@dataclass(frozen=True)
class KubernetesDiscovery:
    pods: dict[tuple[str, str], KubernetesPod]
    namespaces: list[str]
    events: list[KubernetesEvent]
    status: dict[str, Any]


class KubernetesDiscoveryCollector:
    """Discovers pod metadata through kubectl with graceful failure semantics."""

    def __init__(self, config: KubernetesCollectorConfig) -> None:
        self.config = config
        self._namespace_pattern = re.compile(config.namespace_regex)

    async def collect(self) -> KubernetesDiscovery:
        if self.config.discovery_mode == "disabled":
            return self._empty("disabled", "Kubernetes discovery disabled by configuration.")
        try:
            source, payloads = await asyncio.to_thread(self._load_payloads)
            namespaces = parse_namespaces(payloads["namespaces"])
            events = parse_events(payloads["events"], self.config.event_limit)
            pods = parse_pods(payloads["pods"], events)
            pods = {
                key: pod
                for key, pod in pods.items()
                if self._namespace_pattern.fullmatch(pod.namespace)
            }
            return KubernetesDiscovery(
                pods=pods,
                namespaces=[ns for ns in namespaces if self._namespace_pattern.fullmatch(ns)],
                events=[
                    event
                    for event in events
                    if event.namespace and self._namespace_pattern.fullmatch(event.namespace)
                ],
                status={
                    "available": True,
                    "source": source,
                    "pod_count": len(pods),
                    "namespace_count": len(namespaces),
                    "event_count": len(events),
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            if isinstance(exc, KubernetesCollectionError):
                message = str(exc)
            else:
                message = f"Kubernetes discovery failed: {exc}"
            return self._empty("unavailable", message)

    def _empty(self, source: str, message: str) -> KubernetesDiscovery:
        return KubernetesDiscovery(
            pods={},
            namespaces=[],
            events=[],
            status={
                "available": False,
                "source": source,
                "message": message,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _load_payloads(self) -> tuple[str, dict[str, dict[str, Any]]]:
        mode = self.config.discovery_mode
        if mode not in {"auto", "in_cluster", "kubeconfig", "kubectl"}:
            raise KubernetesCollectionError(f"Unsupported Kubernetes discovery mode: {mode}")

        if mode == "in_cluster" or (mode == "auto" and os.getenv("KUBERNETES_SERVICE_HOST")):
            return "in_cluster", self._load_in_cluster()
        return "kubectl", self._load_with_kubectl()

    def _load_in_cluster(self) -> dict[str, dict[str, Any]]:
        host = os.getenv("KUBERNETES_SERVICE_HOST")
        port = os.getenv("KUBERNETES_SERVICE_PORT", "443")
        token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        if not host or not os.path.exists(token_path):
            raise KubernetesCollectionError("Kubernetes service account credentials are unavailable.")

        with open(token_path, "r", encoding="utf-8") as token_file:
            token = token_file.read().strip()
        verify: str | bool = ca_path if os.path.exists(ca_path) else True
        base_url = f"https://{host}:{port}"
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=self.config.timeout_seconds, verify=verify, headers=headers) as client:
            return {
                "pods": self._api_json(client, base_url, "/api/v1/pods"),
                "namespaces": self._api_json(client, base_url, "/api/v1/namespaces"),
                "events": self._api_json(client, base_url, "/api/v1/events"),
            }

    def _api_json(self, client: httpx.Client, base_url: str, path: str) -> dict[str, Any]:
        try:
            response = client.get(f"{base_url}{path}")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise KubernetesCollectionError(f"Kubernetes API request failed for {path}: {exc}") from exc

    def _load_with_kubectl(self) -> dict[str, dict[str, Any]]:
        return {
            "pods": self._kubectl_json("get", "pods", "-A", "-o", "json"),
            "namespaces": self._kubectl_json("get", "namespaces", "-o", "json"),
            "events": self._kubectl_json(
                "get",
                "events",
                "-A",
                "--sort-by=.lastTimestamp",
                "-o",
                "json",
            ),
        }

    def _kubectl_json(self, *args: str) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                ["kubectl", *args],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.config.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise KubernetesCollectionError("kubectl is not installed or not on PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise KubernetesCollectionError(f"kubectl timed out after {self.config.timeout_seconds}s.") from exc

        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            raise KubernetesCollectionError(f"kubectl {' '.join(args)} failed: {stderr}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise KubernetesCollectionError("kubectl returned invalid JSON.") from exc


def parse_namespaces(payload: dict[str, Any]) -> list[str]:
    return sorted(
        item.get("metadata", {}).get("name")
        for item in payload.get("items", [])
        if item.get("metadata", {}).get("name")
    )


def parse_events(payload: dict[str, Any], limit: int = 250) -> list[KubernetesEvent]:
    parsed: list[KubernetesEvent] = []
    for item in payload.get("items", [])[-limit:]:
        metadata = item.get("metadata", {})
        involved = item.get("involvedObject", {})
        parsed.append(
            KubernetesEvent(
                namespace=metadata.get("namespace") or involved.get("namespace") or "default",
                name=metadata.get("name", ""),
                reason=item.get("reason"),
                message=item.get("message"),
                type=item.get("type"),
                involved_kind=involved.get("kind"),
                involved_name=involved.get("name"),
                first_seen=item.get("firstTimestamp") or item.get("eventTime"),
                last_seen=item.get("lastTimestamp") or item.get("eventTime"),
                count=int(item.get("count") or 1),
            )
        )
    return parsed


def parse_pods(
    payload: dict[str, Any],
    events: list[KubernetesEvent] | None = None,
) -> dict[tuple[str, str], KubernetesPod]:
    events_by_pod: dict[tuple[str, str], list[KubernetesEvent]] = {}
    for event in events or []:
        if event.involved_kind == "Pod" and event.involved_name:
            events_by_pod.setdefault((event.namespace, event.involved_name), []).append(event)

    pods: dict[tuple[str, str], KubernetesPod] = {}
    for item in payload.get("items", []):
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        namespace = metadata.get("namespace", "default")
        name = metadata.get("name")
        if not name:
            continue

        owner_kind, owner_name = _first_owner(metadata)
        workload_kind, workload_name = _workload_owner(owner_kind, owner_name)
        restart = _restart_summary(status.get("containerStatuses", []))
        pvc_mounts = _pvc_mounts(spec.get("volumes", []))
        service = _service_name(metadata.get("labels", {}), workload_name or name)
        key = (namespace, name)
        pods[key] = KubernetesPod(
            namespace=namespace,
            name=name,
            service=service,
            owner_kind=owner_kind,
            owner_name=owner_name,
            workload_kind=workload_kind,
            workload_name=workload_name,
            node_name=spec.get("nodeName"),
            pvc_mounts=pvc_mounts,
            restart_count=restart["restart_count"],
            restart_reason=restart["restart_reason"],
            last_termination_reason=restart["last_termination_reason"],
            waiting_reason=restart["waiting_reason"],
            oom_killed=restart["oom_killed"],
            phase=status.get("phase"),
            events=events_by_pod.get(key, []),
        )
    return pods


def _first_owner(metadata: dict[str, Any]) -> tuple[str | None, str | None]:
    owners = metadata.get("ownerReferences") or []
    controller = next((owner for owner in owners if owner.get("controller")), None)
    owner = controller or (owners[0] if owners else {})
    return owner.get("kind"), owner.get("name")


def _workload_owner(kind: str | None, name: str | None) -> tuple[str | None, str | None]:
    if not kind or not name:
        return None, None
    if kind == "ReplicaSet":
        deployment = re.match(r"^(?P<name>.+)-[a-f0-9]{5,10}$", name)
        if deployment:
            return "Deployment", deployment.group("name")
    if kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"}:
        return kind, name
    return kind, name


def _restart_summary(container_statuses: list[dict[str, Any]]) -> dict[str, Any]:
    restart_count = 0
    restart_reason = None
    last_termination_reason = None
    waiting_reason = None
    oom_killed = False

    for status in container_statuses:
        restart_count += int(status.get("restartCount") or 0)
        state = status.get("state") or {}
        last_state = status.get("lastState") or {}
        waiting = state.get("waiting") or {}
        terminated = state.get("terminated") or {}
        last_terminated = last_state.get("terminated") or {}

        waiting_reason = waiting.get("reason") or waiting_reason
        last_termination_reason = (
            last_terminated.get("reason")
            or terminated.get("reason")
            or last_termination_reason
        )
        restart_reason = waiting_reason or last_termination_reason or restart_reason
        oom_killed = oom_killed or last_termination_reason == "OOMKilled"

    return {
        "restart_count": restart_count,
        "restart_reason": restart_reason,
        "last_termination_reason": last_termination_reason,
        "waiting_reason": waiting_reason,
        "oom_killed": oom_killed,
    }


def _pvc_mounts(volumes: list[dict[str, Any]]) -> list[str]:
    claims = []
    for volume in volumes:
        claim = (volume.get("persistentVolumeClaim") or {}).get("claimName")
        if claim:
            claims.append(claim)
    return sorted(set(claims))


def _service_name(labels: dict[str, str], fallback: str) -> str:
    return (
        labels.get("app.kubernetes.io/name")
        or labels.get("app")
        or labels.get("k8s-app")
        or labels.get("component")
        or fallback
    )
