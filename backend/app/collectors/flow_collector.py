from __future__ import annotations

import random
from datetime import datetime, timezone

from app.models import FlowRecord


class MockFlowCollector:
    """Returns synthetic eBPF-like flow data for demo mode."""

    _FLOWS = [
        ("frontend-5c6b", "payments", "checkout-api-7d9f", "payments"),
        ("checkout-api-7d9f", "payments", "orders-db-0", "payments"),
        ("frontend-5c6b", "payments", "auth-api-86b4", "platform"),
    ]

    async def collect(self) -> list[FlowRecord]:
        now = datetime.now(timezone.utc)
        records: list[FlowRecord] = []
        for src_pod, src_ns, dst_pod, dst_ns in self._FLOWS:
            records.append(
                FlowRecord(
                    source_pod=src_pod,
                    source_namespace=src_ns,
                    dest_pod=dst_pod,
                    dest_namespace=dst_ns,
                    bytes_per_sec=random.uniform(800, 5000),
                    call_count=random.randint(10, 200),
                    observed_at=now,
                )
            )
        return records


class HubbleFlowCollector:
    """Collects real eBPF flow data from Cilium Hubble Observe API.

    Falls back to empty list when Hubble is not reachable.
    """

    def __init__(self, hubble_url: str) -> None:
        self.hubble_url = hubble_url.rstrip("/")

    async def collect(self) -> list[FlowRecord]:
        import httpx

        now = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.hubble_url}/v1/flows", params={"last": 100})
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []

        records: list[FlowRecord] = []
        for flow in payload.get("flows", []):
            source = flow.get("source", {})
            destination = flow.get("destination", {})
            src_pod = source.get("pod_name", "")
            dst_pod = destination.get("pod_name", "")
            if not src_pod or not dst_pod:
                continue
            l7 = flow.get("l7", {})
            records.append(
                FlowRecord(
                    source_pod=src_pod,
                    source_namespace=source.get("namespace", "default"),
                    dest_pod=dst_pod,
                    dest_namespace=destination.get("namespace", "default"),
                    bytes_per_sec=float(flow.get("traffic", {}).get("bytes", 0)),
                    call_count=int(l7.get("request_count", 1)),
                    observed_at=now,
                )
            )
        return records
