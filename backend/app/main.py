from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.insight_service import InsightService

app = FastAPI(
    title="Kovalent API",
    description="AI-assisted Kubernetes pod intelligence and root-cause insights.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = InsightService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "kovalent-api"}


@app.get("/api/snapshot")
def snapshot() -> dict:
    return service.build_snapshot().model_dump()


@app.get("/api/status")
def api_status() -> dict:
    return {
        "mode": service.settings.mode,
        "prometheus_url": service.settings.prometheus_url,
        "loki_configured": service.settings.loki_url is not None,
        "namespace_regex": service.settings.namespace_regex,
        "query_window": service.settings.query_window,
        "live_fallback_enabled": service.settings.live_fallback_enabled,
    }


@app.get("/api/insights")
def insights() -> dict:
    snapshot_data = service.build_snapshot()
    return {"insights": [insight.model_dump() for insight in snapshot_data.insights]}


@app.get("/api/topology")
def topology() -> dict:
    snapshot_data = service.build_snapshot()
    return snapshot_data.topology.model_dump()
