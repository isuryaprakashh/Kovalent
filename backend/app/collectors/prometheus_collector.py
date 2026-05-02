import asyncio
import httpx
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.collectors.kubernetes_collector import KubernetesDiscoveryCollector
from app.collectors.log_pattern_collector import group_loki_error_signatures
from app.models import LogErrorSignature, PodMetric


class TelemetryCollectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CollectorConfig:
    prometheus_url: str
    loki_url: str | None = None
    namespace_regex: str = ".+"
    query_window: str = "5m"
    timeout_seconds: float = 8.0


class PrometheusTelemetryCollector:
    """Collects live pod metrics from Prometheus and log error rates from Loki asynchronously."""

    def __init__(
        self,
        config: CollectorConfig,
        kubernetes_collector: KubernetesDiscoveryCollector | None = None,
    ) -> None:
        self.config = config
        self.prometheus_url = config.prometheus_url.rstrip("/")
        self.loki_url = config.loki_url.rstrip("/") if config.loki_url else None
        self.kubernetes_collector = kubernetes_collector
        self.status: dict[str, Any] = {"available": None, "optional_errors": []}

    async def collect(self) -> list[PodMetric]:
        self.status = {"available": None, "optional_errors": []}
        kubernetes_task = (
            asyncio.create_task(self.kubernetes_collector.collect())
            if self.kubernetes_collector
            else None
        )
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                # Fire all queries in parallel
                tasks = [
                    self._prometheus_vector(client, "cpu_usage", f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) * 1000'),
                    self._prometheus_vector(client, "cpu_limits", f'sum by (namespace, pod) (kube_pod_container_resource_limits{{namespace=~"{self.config.namespace_regex}",resource="cpu",unit="core"}}) * 1000'),
                    self._prometheus_vector(client, "cpu_requests", f'sum by (namespace, pod) (kube_pod_container_resource_requests{{namespace=~"{self.config.namespace_regex}",resource="cpu",unit="core"}}) * 1000', required=False),
                    # CFS throttle (classic) — may be empty on cgroup v2 / containerd
                    self._prometheus_vector(client, "cpu_throttling", f'(sum by (namespace, pod) (rate(container_cpu_cfs_throttled_periods_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / clamp_min(sum by (namespace, pod) (rate(container_cpu_cfs_periods_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])), 1)) * 100', required=False),
                    # PSI CPU pressure fallback — available on cgroup v2 kernels
                    self._prometheus_vector(client, "cpu_pressure", f'sum by (namespace, pod) (rate(container_pressure_cpu_waiting_seconds_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) * 100', required=False),
                    self._prometheus_vector(client, "memory_usage", f'sum by (namespace, pod) (container_memory_working_set_bytes{{namespace=~"{self.config.namespace_regex}",pod!=""}}) / 1024 / 1024'),
                    self._prometheus_vector(client, "memory_limits", f'sum by (namespace, pod) (kube_pod_container_resource_limits{{namespace=~"{self.config.namespace_regex}",resource="memory",unit="byte"}}) / 1024 / 1024'),
                    self._prometheus_vector(client, "memory_requests", f'sum by (namespace, pod) (kube_pod_container_resource_requests{{namespace=~"{self.config.namespace_regex}",resource="memory",unit="byte"}}) / 1024 / 1024', required=False),
                    # Container-level network (may be empty on some runtimes)
                    self._prometheus_vector(client, "network_rx", f'sum by (namespace, pod) (rate(container_network_receive_bytes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / 1024', required=False),
                    self._prometheus_vector(client, "network_tx", f'sum by (namespace, pod) (rate(container_network_transmit_bytes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / 1024', required=False),
                    # Process-level network fallback
                    self._prometheus_vector(client, "process_network_rx", f'sum by (namespace, pod) (rate(process_network_receive_bytes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / 1024', required=False),
                    self._prometheus_vector(client, "process_network_tx", f'sum by (namespace, pod) (rate(process_network_transmit_bytes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / 1024', required=False),
                    self._prometheus_vector(client, "network_rx_drops", f'sum by (namespace, pod) (rate(container_network_receive_packets_dropped_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}]))', required=False),
                    self._prometheus_vector(client, "network_tx_drops", f'sum by (namespace, pod) (rate(container_network_transmit_packets_dropped_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}]))', required=False),
                    self._prometheus_vector(client, "restarts", f'sum by (namespace, pod) (kube_pod_container_status_restarts_total{{namespace=~"{self.config.namespace_regex}"}})', required=False),
                    self._prometheus_labels(client, required=False),
                    self._pvc_claims(client, required=False),
                    self._pvc_read_throughput(client, required=False),
                    self._pvc_write_throughput(client, required=False),
                    self._pvc_latency(client, required=False),
                    self._pvc_iops(client, required=False),
                    self._loki_error_rates(client, required=False),
                    self._loki_error_signatures(client, required=False),
                ]

                results = await asyncio.gather(*tasks)

                (cpu_usage, cpu_limits, cpu_requests, cpu_throttling, cpu_pressure,
                 memory_usage, memory_limits, memory_requests,
                 network_rx, network_tx, process_network_rx, process_network_tx,
                 network_rx_drops, network_tx_drops, restarts, pod_labels, pvc_by_pod,
                 pvc_read, pvc_write, pvc_latency, pvc_iops, error_rates, error_signatures) = results

                # Merge fallbacks: prefer CFS throttle, fall back to PSI CPU pressure
                if not cpu_throttling and cpu_pressure:
                    cpu_throttling = cpu_pressure
                # Merge fallbacks: prefer container network, fall back to process network
                if not network_rx and process_network_rx:
                    network_rx = process_network_rx
                if not network_tx and process_network_tx:
                    network_tx = process_network_tx

            except (httpx.HTTPError, asyncio.TimeoutError, ValueError) as exc:
                if kubernetes_task:
                    kubernetes_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await kubernetes_task
                self.status["available"] = False
                self.status["message"] = f"Unable to collect live telemetry: {exc}"
                raise TelemetryCollectionError(f"Unable to collect live telemetry: {exc}") from exc

        kubernetes = await kubernetes_task if kubernetes_task else None
        if kubernetes:
            self.status["kubernetes"] = kubernetes.status
        observed_at = datetime.now(timezone.utc)
        kubernetes_pods = kubernetes.pods if kubernetes else {}
        keys = set(cpu_usage) | set(memory_usage) | set(network_rx) | set(network_tx) | set(kubernetes_pods)
        metrics: list[PodMetric] = []
        for key in sorted(keys):
            namespace, pod = key
            kubernetes_pod = kubernetes_pods.get(key)
            service = pod_labels.get(key) or (kubernetes_pod.service if kubernetes_pod else None) or self._service_from_pod_name(pod)
            pvc_name = pvc_by_pod.get(key)
            pvc_mounts = kubernetes_pod.pvc_mounts if kubernetes_pod else []
            if not pvc_name and pvc_mounts:
                pvc_name = pvc_mounts[0]
            metrics.append(
                PodMetric(
                    namespace=namespace,
                    pod=pod,
                    service=service,
                    owner_kind=kubernetes_pod.workload_kind if kubernetes_pod else None,
                    owner_name=kubernetes_pod.workload_name if kubernetes_pod else None,
                    node_name=kubernetes_pod.node_name if kubernetes_pod else None,
                    cpu_millicores=cpu_usage.get(key, 0),
                    cpu_limit_millicores=self._capacity_for(cpu_usage.get(key, 0), cpu_limits.get(key), cpu_requests.get(key), 1000),
                    cpu_request_millicores=cpu_requests.get(key),
                    cpu_throttled_percent=cpu_throttling.get(key),
                    memory_mb=memory_usage.get(key, 0),
                    memory_limit_mb=self._capacity_for(memory_usage.get(key, 0), memory_limits.get(key), memory_requests.get(key), 512),
                    memory_request_mb=memory_requests.get(key),
                    network_rx_kbps=network_rx.get(key, 0),
                    network_tx_kbps=network_tx.get(key, 0),
                    network_rx_drops_per_second=network_rx_drops.get(key),
                    network_tx_drops_per_second=network_tx_drops.get(key),
                    pvc_name=pvc_name,
                    pvc_mounts=pvc_mounts,
                    pvc_read_kbps=pvc_read.get(key) if pvc_name else pvc_read.get(key),
                    pvc_write_kbps=pvc_write.get(key) if pvc_name else pvc_write.get(key),
                    pvc_latency_ms=pvc_latency.get(key) if pvc_name else pvc_latency.get(key),
                    pvc_iops=pvc_iops.get(key) if pvc_name else pvc_iops.get(key),
                    error_rate_per_minute=error_rates.get(key, 0),
                    error_signatures=error_signatures.get(key, []),
                    restart_count=max(int(restarts.get(key, 0)), kubernetes_pod.restart_count if kubernetes_pod else 0),
                    restart_reason=kubernetes_pod.restart_reason if kubernetes_pod else None,
                    last_termination_reason=kubernetes_pod.last_termination_reason if kubernetes_pod else None,
                    waiting_reason=kubernetes_pod.waiting_reason if kubernetes_pod else None,
                    oom_killed=kubernetes_pod.oom_killed if kubernetes_pod else False,
                    observed_at=observed_at,
                )
            )

        if not metrics:
            self.status["available"] = False
            self.status["message"] = "Prometheus returned no pod metrics for the configured namespace selector."
            raise TelemetryCollectionError("Prometheus returned no pod metrics for the configured namespace selector.")
        self.status["available"] = True
        self.status["pod_count"] = len(metrics)
        return metrics

    async def _prometheus_vector(self, client: httpx.AsyncClient, name: str, query: str, required: bool = True) -> dict[tuple[str, str], float]:
        try:
            response = await client.get(f"{self.prometheus_url}/api/v1/query", params={"query": query})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if required: raise
            self._record_optional_error(name, exc)
            return {}

        if payload.get("status") != "success":
            if required: raise TelemetryCollectionError(f"Prometheus query failed for {name}: {payload}")
            self._record_optional_error(name, payload)
            return {}
        return self._vector_to_pod_map(payload.get("data", {}).get("result", []))

    async def _prometheus_labels(self, client: httpx.AsyncClient, required: bool) -> dict[tuple[str, str], str]:
        query = f'kube_pod_labels{{namespace=~"{self.config.namespace_regex}",pod!=""}}'
        try:
            response = await client.get(f"{self.prometheus_url}/api/v1/query", params={"query": query})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if required: raise
            self._record_optional_error("pod_labels", exc)
            return {}

        labels: dict[tuple[str, str], str] = {}
        for item in payload.get("data", {}).get("result", []):
            metric = item.get("metric", {})
            key = self._pod_key(metric)
            if key is None: continue
            service = metric.get("label_app_kubernetes_io_name") or metric.get("label_app") or metric.get("label_k8s_app") or metric.get("label_component")
            if service: labels[key] = service
        return labels

    async def _pvc_claims(self, client: httpx.AsyncClient, required: bool) -> dict[tuple[str, str], str]:
        query = f'kube_pod_spec_volumes_persistentvolumeclaims_info{{namespace=~"{self.config.namespace_regex}",pod!=""}}'
        try:
            response = await client.get(f"{self.prometheus_url}/api/v1/query", params={"query": query})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if required: raise
            self._record_optional_error("pvc_claims", exc)
            return {}

        claims: dict[tuple[str, str], str] = {}
        for item in payload.get("data", {}).get("result", []):
            metric = item.get("metric", {})
            key = self._pod_key(metric)
            claim = metric.get("persistentvolumeclaim")
            if key and claim: claims[key] = claim
        return claims

    async def _pvc_latency(self, client: httpx.AsyncClient, required: bool) -> dict[tuple[str, str], float]:
        query = (
            f'(sum by (namespace, pod) (rate(container_fs_io_time_seconds_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) '
            f'/ clamp_min(sum by (namespace, pod) (rate(container_fs_reads_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}]) '
            f'+ rate(container_fs_writes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])), 1)) * 1000'
        )
        return await self._prometheus_vector(client, "pvc_latency", query, required=required)

    async def _pvc_read_throughput(self, client: httpx.AsyncClient, required: bool) -> dict[tuple[str, str], float]:
        query = f'sum by (namespace, pod) (rate(container_fs_reads_bytes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / 1024'
        return await self._prometheus_vector(client, "pvc_read", query, required=required)

    async def _pvc_write_throughput(self, client: httpx.AsyncClient, required: bool) -> dict[tuple[str, str], float]:
        query = f'sum by (namespace, pod) (rate(container_fs_writes_bytes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / 1024'
        return await self._prometheus_vector(client, "pvc_write", query, required=required)

    async def _pvc_iops(self, client: httpx.AsyncClient, required: bool) -> dict[tuple[str, str], float]:
        query = (
            f'sum by (namespace, pod) (rate(container_fs_reads_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}]) '
            f'+ rate(container_fs_writes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}]))'
        )
        return await self._prometheus_vector(client, "pvc_iops", query, required=required)

    async def _loki_error_rates(self, client: httpx.AsyncClient, required: bool) -> dict[tuple[str, str], float]:
        if not self.loki_url: return {}
        query = (
            f'sum by (namespace, pod) (count_over_time({{namespace=~"{self.config.namespace_regex}",pod=~".+"}} '
            f'|~ "(?i)(error|exception|panic|failed|timeout|oom|out of memory|connection refused|5xx|5[0-9]{{2}})" [{self.config.query_window}]))'
        )
        try:
            response = await client.get(f"{self.loki_url}/loki/api/v1/query", params={"query": query})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if required: raise
            self._record_optional_error("loki_error_rates", exc)
            return {}
        if payload.get("status") != "success":
            self._record_optional_error("loki_error_rates", payload)
            return {}
        return self._vector_to_pod_map(payload.get("data", {}).get("result", []))

    async def _loki_error_signatures(self, client: httpx.AsyncClient, required: bool) -> dict[tuple[str, str], list[LogErrorSignature]]:
        if not self.loki_url:
            return {}
        query = (
            f'{{namespace=~"{self.config.namespace_regex}",pod=~".+"}} '
            f'|~ "(?i)(error|exception|panic|failed|timeout|oom|out of memory|connection refused|5xx|5[0-9]{{2}})"'
        )
        try:
            response = await client.get(
                f"{self.loki_url}/loki/api/v1/query_range",
                params={"query": query, "limit": 1000, "direction": "backward"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if required:
                raise
            self._record_optional_error("loki_error_signatures", exc)
            return {}
        if payload.get("status") != "success":
            self._record_optional_error("loki_error_signatures", payload)
            return {}
        return group_loki_error_signatures(payload.get("data", {}).get("result", []))

    def _vector_to_pod_map(self, result: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
        values: dict[tuple[str, str], float] = {}
        for item in result:
            metric = item.get("metric", {})
            key = self._pod_key(metric)
            if key is None:
                continue
            value = item.get("value", [None, 0])[1]
            try:
                values[key] = max(float(value), 0)
            except (TypeError, ValueError):
                continue
        return values

    def _pod_key(self, metric: dict[str, str]) -> tuple[str, str] | None:
        namespace = metric.get("namespace")
        pod = metric.get("pod") or metric.get("pod_name")
        if not namespace or not pod:
            return None
        return namespace, pod

    def _service_from_pod_name(self, pod: str) -> str:
        stateful = re.match(r"^(?P<name>.+)-\d+$", pod)
        if stateful:
            return stateful.group("name")
        replica = re.match(r"^(?P<name>.+)-[a-f0-9]{5,10}-[a-z0-9]{4,6}$", pod)
        if replica:
            return replica.group("name")
        return pod

    def _capacity_for(self, usage: float, limit: float | None, request: float | None, default_floor: float) -> float:
        if limit and limit > 0:
            return limit
        if request and request > 0:
            return max(request * 2, usage * 2, 1)
        return max(default_floor, usage * 4, 1)

    def _record_optional_error(self, source: str, error: Any) -> None:
        self.status.setdefault("optional_errors", []).append(
            {"source": source, "message": str(error)[:500]}
        )
