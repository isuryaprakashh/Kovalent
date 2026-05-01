from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.models import PodMetric


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
    """Collects live pod metrics from Prometheus and log error rates from Loki."""

    def __init__(self, config: CollectorConfig) -> None:
        self.config = config
        self.prometheus_url = config.prometheus_url.rstrip("/")
        self.loki_url = config.loki_url.rstrip("/") if config.loki_url else None

    def collect(self) -> list[PodMetric]:
        try:
            cpu_usage = self._prometheus_vector(
                "cpu_usage",
                f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) * 1000',
            )
            cpu_limits = self._prometheus_vector(
                "cpu_limits",
                f'sum by (namespace, pod) (kube_pod_container_resource_limits{{namespace=~"{self.config.namespace_regex}",resource="cpu",unit="core"}}) * 1000',
            )
            cpu_requests = self._prometheus_vector(
                "cpu_requests",
                f'sum by (namespace, pod) (kube_pod_container_resource_requests{{namespace=~"{self.config.namespace_regex}",resource="cpu",unit="core"}}) * 1000',
                required=False,
            )
            memory_usage = self._prometheus_vector(
                "memory_usage",
                f'sum by (namespace, pod) (container_memory_working_set_bytes{{namespace=~"{self.config.namespace_regex}",pod!=""}}) / 1024 / 1024',
            )
            memory_limits = self._prometheus_vector(
                "memory_limits",
                f'sum by (namespace, pod) (kube_pod_container_resource_limits{{namespace=~"{self.config.namespace_regex}",resource="memory",unit="byte"}}) / 1024 / 1024',
            )
            memory_requests = self._prometheus_vector(
                "memory_requests",
                f'sum by (namespace, pod) (kube_pod_container_resource_requests{{namespace=~"{self.config.namespace_regex}",resource="memory",unit="byte"}}) / 1024 / 1024',
                required=False,
            )
            network_rx = self._prometheus_vector(
                "network_rx",
                f'sum by (namespace, pod) (rate(container_network_receive_bytes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / 1024',
            )
            network_tx = self._prometheus_vector(
                "network_tx",
                f'sum by (namespace, pod) (rate(container_network_transmit_bytes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) / 1024',
            )
            restarts = self._prometheus_vector(
                "restarts",
                f'sum by (namespace, pod) (kube_pod_container_status_restarts_total{{namespace=~"{self.config.namespace_regex}"}})',
                required=False,
            )
            pod_labels = self._prometheus_labels(required=False)
            pvc_by_pod = self._pvc_claims(required=False)
            pvc_latency = self._pvc_latency(required=False)
            pvc_iops = self._pvc_iops(required=False)
            error_rates = self._loki_error_rates(required=False)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise TelemetryCollectionError(f"Unable to collect live telemetry: {exc}") from exc

        observed_at = datetime.now(timezone.utc)
        keys = set(cpu_usage) | set(memory_usage) | set(network_rx) | set(network_tx)
        metrics: list[PodMetric] = []
        for key in sorted(keys):
            namespace, pod = key
            service = pod_labels.get(key) or self._service_from_pod_name(pod)
            pvc_name = pvc_by_pod.get(key)
            metrics.append(
                PodMetric(
                    namespace=namespace,
                    pod=pod,
                    service=service,
                    cpu_millicores=cpu_usage.get(key, 0),
                    cpu_limit_millicores=self._capacity_for(cpu_usage.get(key, 0), cpu_limits.get(key), cpu_requests.get(key), 1000),
                    memory_mb=memory_usage.get(key, 0),
                    memory_limit_mb=self._capacity_for(memory_usage.get(key, 0), memory_limits.get(key), memory_requests.get(key), 512),
                    network_rx_kbps=network_rx.get(key, 0),
                    network_tx_kbps=network_tx.get(key, 0),
                    pvc_name=pvc_name,
                    pvc_latency_ms=pvc_latency.get(key) if pvc_name else None,
                    pvc_iops=pvc_iops.get(key) if pvc_name else None,
                    error_rate_per_minute=error_rates.get(key, 0),
                    restart_count=int(restarts.get(key, 0)),
                    observed_at=observed_at,
                )
            )

        if not metrics:
            raise TelemetryCollectionError("Prometheus returned no pod metrics for the configured namespace selector.")
        return metrics

    def _prometheus_vector(self, name: str, query: str, required: bool = True) -> dict[tuple[str, str], float]:
        try:
            payload = self._get_json(f"{self.prometheus_url}/api/v1/query", {"query": query})
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            if required:
                raise
            return {}
        if payload.get("status") != "success":
            if required:
                raise TelemetryCollectionError(f"Prometheus query failed for {name}: {payload}")
            return {}
        return self._vector_to_pod_map(payload.get("data", {}).get("result", []))

    def _prometheus_labels(self, required: bool) -> dict[tuple[str, str], str]:
        query = (
            f'kube_pod_labels{{namespace=~"{self.config.namespace_regex}",pod!=""}}'
        )
        try:
            payload = self._get_json(f"{self.prometheus_url}/api/v1/query", {"query": query})
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            if required:
                raise
            return {}

        labels: dict[tuple[str, str], str] = {}
        for item in payload.get("data", {}).get("result", []):
            metric = item.get("metric", {})
            key = self._pod_key(metric)
            if key is None:
                continue
            service = (
                metric.get("label_app_kubernetes_io_name")
                or metric.get("label_app")
                or metric.get("label_k8s_app")
                or metric.get("label_component")
            )
            if service:
                labels[key] = service
        return labels

    def _pvc_claims(self, required: bool) -> dict[tuple[str, str], str]:
        query = f'kube_pod_spec_volumes_persistentvolumeclaims_info{{namespace=~"{self.config.namespace_regex}",pod!=""}}'
        try:
            payload = self._get_json(f"{self.prometheus_url}/api/v1/query", {"query": query})
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            if required:
                raise
            return {}

        claims: dict[tuple[str, str], str] = {}
        for item in payload.get("data", {}).get("result", []):
            metric = item.get("metric", {})
            key = self._pod_key(metric)
            claim = metric.get("persistentvolumeclaim")
            if key and claim:
                claims[key] = claim
        return claims

    def _pvc_latency(self, required: bool) -> dict[tuple[str, str], float]:
        query = (
            f'(sum by (namespace, pod) (rate(container_fs_io_time_seconds_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])) '
            f'/ clamp_min(sum by (namespace, pod) (rate(container_fs_reads_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}]) '
            f'+ rate(container_fs_writes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}])), 1)) * 1000'
        )
        return self._prometheus_vector("pvc_latency", query, required=required)

    def _pvc_iops(self, required: bool) -> dict[tuple[str, str], float]:
        query = (
            f'sum by (namespace, pod) (rate(container_fs_reads_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}]) '
            f'+ rate(container_fs_writes_total{{namespace=~"{self.config.namespace_regex}",pod!=""}}[{self.config.query_window}]))'
        )
        return self._prometheus_vector("pvc_iops", query, required=required)

    def _loki_error_rates(self, required: bool) -> dict[tuple[str, str], float]:
        if not self.loki_url:
            return {}
        query = (
            f'sum by (namespace, pod) (count_over_time({{namespace=~"{self.config.namespace_regex}",pod=~".+"}} '
            f'|~ "(?i)(error|exception|panic|failed| 5[0-9]{{2}} )" [{self.config.query_window}]))'
        )
        try:
            payload = self._get_json(f"{self.loki_url}/loki/api/v1/query", {"query": query})
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            if required:
                raise
            return {}
        if payload.get("status") != "success":
            return {}
        return self._vector_to_pod_map(payload.get("data", {}).get("result", []))

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        request_url = f"{url}?{urlencode(params)}"
        request = Request(request_url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=self.config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)

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
