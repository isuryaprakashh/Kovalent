import asyncio
from typing import Any

import httpx

from app.collectors.kubernetes_collector import KubernetesDiscovery, KubernetesPod
from app.collectors.prometheus_collector import CollectorConfig, PrometheusTelemetryCollector
from app.models import LogErrorSignature


class FakeLiveCollector(PrometheusTelemetryCollector):
    async def _prometheus_vector(
        self,
        client: httpx.AsyncClient,
        name: str,
        query: str,
        required: bool = True,
    ) -> dict[tuple[str, str], float]:
        values = {
            "cpu_usage": 820,
            "cpu_limits": 1000,
            "memory_usage": 512,
            "memory_limits": 1024,
            "network_rx": 120,
            "network_tx": 140,
            "cpu_throttling": 7,
            "network_rx_drops": 1,
            "network_tx_drops": 2,
            "restarts": 2,
            "pvc_read": 32,
            "pvc_write": 64,
            "pvc_latency": 130,
            "pvc_iops": 60,
        }
        value = values.get(name)
        if value is None:
            return {}
        return {("payments", "checkout-api-7d9f"): value}

    async def _prometheus_labels(
        self,
        client: httpx.AsyncClient,
        required: bool,
    ) -> dict[tuple[str, str], str]:
        return {("payments", "checkout-api-7d9f"): "checkout-api"}

    async def _pvc_claims(
        self,
        client: httpx.AsyncClient,
        required: bool,
    ) -> dict[tuple[str, str], str]:
        return {("payments", "checkout-api-7d9f"): "checkout-data"}

    async def _loki_error_rates(
        self,
        client: httpx.AsyncClient,
        required: bool,
    ) -> dict[tuple[str, str], float]:
        return {("payments", "checkout-api-7d9f"): 12}

    async def _loki_error_signatures(
        self,
        client: httpx.AsyncClient,
        required: bool,
    ) -> dict[tuple[str, str], list[LogErrorSignature]]:
        return {
            ("payments", "checkout-api-7d9f"): [
                LogErrorSignature(
                    signature="error checkout failed for order <num>",
                    count=2,
                    first_seen="2026-05-02T00:00:00Z",
                    last_seen="2026-05-02T00:01:00Z",
                    sample="error checkout failed for order 42",
                )
            ]
        }

    def _vector(self, pod: str, value: float) -> dict[str, Any]:
        return {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"namespace": "payments", "pod": pod},
                        "value": [0, str(value)],
                    }
                ]
            },
        }


def test_live_collector_maps_prometheus_and_loki_payloads() -> None:
    collector = FakeLiveCollector(
        CollectorConfig(
            prometheus_url="http://prometheus.test",
            loki_url="http://loki.test",
        )
    )

    metrics = asyncio.run(collector.collect())

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.namespace == "payments"
    assert metric.pod == "checkout-api-7d9f"
    assert metric.service == "checkout-api"
    assert metric.cpu_millicores == 820
    assert metric.memory_limit_mb == 1024
    assert metric.cpu_throttled_percent == 7
    assert metric.network_rx_drops_per_second == 1
    assert metric.pvc_name == "checkout-data"
    assert metric.pvc_read_kbps == 32
    assert metric.pvc_write_kbps == 64
    assert metric.pvc_latency_ms == 130
    assert metric.error_rate_per_minute == 12
    assert metric.error_signatures[0].signature == "error checkout failed for order <num>"
    assert metric.restart_count == 2


def test_live_collector_merges_kubernetes_discovery_metadata() -> None:
    class FakeKubernetesCollector:
        async def collect(self) -> KubernetesDiscovery:
            return KubernetesDiscovery(
                pods={
                    ("payments", "checkout-api-7d9f"): KubernetesPod(
                        namespace="payments",
                        name="checkout-api-7d9f",
                        service="checkout-api",
                        owner_kind="ReplicaSet",
                        owner_name="checkout-api-7d9f4c8c6f",
                        workload_kind="Deployment",
                        workload_name="checkout-api",
                        node_name="minikube",
                        pvc_mounts=["checkout-data"],
                        restart_count=5,
                        restart_reason="CrashLoopBackOff",
                        last_termination_reason="OOMKilled",
                        waiting_reason="CrashLoopBackOff",
                        oom_killed=True,
                        phase="Running",
                    )
                },
                namespaces=["payments"],
                events=[],
                status={"available": True},
            )

    collector = FakeLiveCollector(
        CollectorConfig(prometheus_url="http://prometheus.test"),
        kubernetes_collector=FakeKubernetesCollector(),
    )

    metric = asyncio.run(collector.collect())[0]

    assert metric.owner_kind == "Deployment"
    assert metric.owner_name == "checkout-api"
    assert metric.node_name == "minikube"
    assert metric.pvc_mounts == ["checkout-data"]
    assert metric.restart_count == 5
    assert metric.waiting_reason == "CrashLoopBackOff"
    assert metric.oom_killed is True
