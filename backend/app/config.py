from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend directory (one level up from app/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path, override=True)


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    prometheus_url: str = "http://localhost:9090"
    loki_url: str | None = None
    namespace_regex: str = ".+"
    query_window: str = "5m"
    request_timeout_seconds: float = 8.0
    live_fallback_enabled: bool = True
    kubernetes_discovery_mode: str = "auto"
    kubernetes_event_limit: int = 250
    dependencies_json: str | None = None
    # M4 — Live Graph
    redis_url: str = "redis://localhost:6379"
    hubble_url: str | None = None
    graph_rebuild_interval: int = 5
    # M5 — Causal Engine
    causal_retrain_interval: int = 60
    causal_window_size: int = 60
    causal_threshold: float = 0.15
    # M6 — LLM
    google_api_key: str | None = None


def get_settings() -> Settings:
    return Settings(
        mode=os.getenv("KOVALENT_MODE", "demo").lower(),
        prometheus_url=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
        loki_url=os.getenv("LOKI_URL") or None,
        namespace_regex=os.getenv("KOVALENT_NAMESPACE_REGEX", ".+"),
        query_window=os.getenv("KOVALENT_QUERY_WINDOW", "5m"),
        request_timeout_seconds=float(os.getenv("KOVALENT_REQUEST_TIMEOUT_SECONDS", "8")),
        live_fallback_enabled=os.getenv("KOVALENT_LIVE_FALLBACK", "true").lower() in {"1", "true", "yes"},
        kubernetes_discovery_mode=os.getenv("KOVALENT_KUBERNETES_DISCOVERY_MODE", "auto").lower(),
        kubernetes_event_limit=int(os.getenv("KOVALENT_KUBERNETES_EVENT_LIMIT", "250")),
        dependencies_json=os.getenv("KOVALENT_DEPENDENCIES"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
        hubble_url=os.getenv("HUBBLE_URL") or None,
        graph_rebuild_interval=int(os.getenv("KOVALENT_GRAPH_REBUILD_INTERVAL", "5")),
        causal_retrain_interval=int(os.getenv("KOVALENT_CAUSAL_RETRAIN_INTERVAL", "60")),
        causal_window_size=int(os.getenv("KOVALENT_CAUSAL_WINDOW_SIZE", "60")),
        causal_threshold=float(os.getenv("KOVALENT_CAUSAL_THRESHOLD", "0.15")),
        google_api_key=os.getenv("GOOGLE_API_KEY") or None,
    )

