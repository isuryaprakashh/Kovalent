from __future__ import annotations

from datetime import datetime, timezone

from app.models import PodMetric


class MockTelemetryCollector:
    """Provides deterministic sample telemetry for local demos and tests."""

    def collect(self) -> list[PodMetric]:
        now = datetime.now(timezone.utc)
        return [
            PodMetric(
                namespace="payments",
                pod="checkout-api-7d9f",
                service="checkout-api",
                cpu_millicores=820,
                cpu_limit_millicores=1000,
                memory_mb=610,
                memory_limit_mb=1024,
                network_rx_kbps=920,
                network_tx_kbps=1340,
                pvc_name=None,
                error_rate_per_minute=4,
                restart_count=0,
                observed_at=now,
            ),
            PodMetric(
                namespace="payments",
                pod="orders-db-0",
                service="orders-db",
                cpu_millicores=710,
                cpu_limit_millicores=1500,
                memory_mb=1840,
                memory_limit_mb=2048,
                network_rx_kbps=560,
                network_tx_kbps=460,
                pvc_name="orders-data",
                pvc_latency_ms=165,
                pvc_iops=920,
                error_rate_per_minute=1,
                restart_count=0,
                observed_at=now,
            ),
            PodMetric(
                namespace="payments",
                pod="frontend-5c6b",
                service="frontend",
                cpu_millicores=210,
                cpu_limit_millicores=500,
                memory_mb=212,
                memory_limit_mb=512,
                network_rx_kbps=1480,
                network_tx_kbps=730,
                pvc_name=None,
                error_rate_per_minute=18,
                restart_count=1,
                observed_at=now,
            ),
            PodMetric(
                namespace="platform",
                pod="auth-api-86b4",
                service="auth-api",
                cpu_millicores=180,
                cpu_limit_millicores=750,
                memory_mb=320,
                memory_limit_mb=768,
                network_rx_kbps=330,
                network_tx_kbps=290,
                pvc_name=None,
                error_rate_per_minute=0,
                restart_count=0,
                observed_at=now,
            ),
        ]

