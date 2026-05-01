import asyncio
from typing import Any

import httpx

from app.collectors.prometheus_collector import CollectorConfig, PrometheusTelemetryCollector


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
            "restarts": 2,
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
    assert metric.pvc_name == "checkout-data"
    assert metric.pvc_latency_ms == 130
    assert metric.error_rate_per_minute == 12
    assert metric.restart_count == 2
