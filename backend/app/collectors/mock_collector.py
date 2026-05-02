import random
from datetime import datetime, timezone

from app.models import PodMetric


class MockTelemetryCollector:
    """Provides dynamic sample telemetry for local demos and tests."""

    async def collect(self) -> list[PodMetric]:
        now = datetime.now(timezone.utc)
        return [
            PodMetric(
                namespace="payments",
                pod="checkout-api-7d9f",
                service="checkout-api",
                cpu_millicores=850 + random.uniform(-30, 30),
                cpu_limit_millicores=1000,
                memory_mb=610 + random.uniform(-10, 10),
                memory_limit_mb=1024,
                network_rx_kbps=920 + random.uniform(-100, 100),
                network_tx_kbps=1340 + random.uniform(-100, 100),
                pvc_name=None,
                error_rate_per_minute=max(0, 4 + random.randint(-1, 2)),
                restart_count=0,
                observed_at=now,
            ),
            PodMetric(
                namespace="payments",
                pod="orders-db-0",
                service="orders-db",
                cpu_millicores=710 + random.uniform(-30, 30),
                cpu_limit_millicores=1500,
                memory_mb=1840 + random.uniform(-5, 5),
                memory_limit_mb=2048,
                network_rx_kbps=560 + random.uniform(-50, 50),
                network_tx_kbps=460 + random.uniform(-50, 50),
                pvc_name="orders-data",
                pvc_latency_ms=165 + random.uniform(-20, 20),
                pvc_iops=920 + random.uniform(-100, 100),
                error_rate_per_minute=max(0, 1 + random.randint(-1, 1)),
                restart_count=0,
                observed_at=now,
            ),
            PodMetric(
                namespace="payments",
                pod="frontend-5c6b",
                service="frontend",
                cpu_millicores=210 + random.uniform(-20, 20),
                cpu_limit_millicores=500,
                memory_mb=212 + random.uniform(-10, 10),
                memory_limit_mb=512,
                network_rx_kbps=1480 + random.uniform(-200, 200),
                network_tx_kbps=730 + random.uniform(-100, 100),
                pvc_name=None,
                error_rate_per_minute=max(0, 18 + random.randint(-5, 5)),
                restart_count=1,
                observed_at=now,
            ),
            PodMetric(
                namespace="platform",
                pod="auth-api-86b4",
                service="auth-api",
                cpu_millicores=180 + random.uniform(-10, 10),
                cpu_limit_millicores=750,
                memory_mb=320 + random.uniform(-5, 5),
                memory_limit_mb=768,
                network_rx_kbps=330 + random.uniform(-30, 30),
                network_tx_kbps=290 + random.uniform(-30, 30),
                pvc_name=None,
                error_rate_per_minute=0,
                restart_count=0,
                observed_at=now,
            ),
        ]
