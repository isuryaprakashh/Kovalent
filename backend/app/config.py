from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    prometheus_url: str = "http://localhost:9090"
    loki_url: str | None = None
    namespace_regex: str = ".+"
    query_window: str = "5m"
    request_timeout_seconds: float = 8.0
    live_fallback_enabled: bool = True
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
        dependencies_json=os.getenv("KOVALENT_DEPENDENCIES"),
    )
