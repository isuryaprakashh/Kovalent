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
    )
