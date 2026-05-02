from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.models import LogErrorSignature


ERROR_KEYWORD_PATTERN = re.compile(
    r"(error|exception|panic|failed|timeout|oom|out of memory|connection refused|5xx|5[0-9]{2})",
    re.IGNORECASE,
)
HEX_PATTERN = re.compile(r"\b0x[0-9a-f]+\b", re.IGNORECASE)
UUID_PATTERN = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")
WHITESPACE_PATTERN = re.compile(r"\s+")
STACK_FRAME_PATTERN = re.compile(r"^\s*(at\s+|File \"|Traceback \(most recent call last\)|\S+Error:)")


def group_loki_error_signatures(
    result: list[dict[str, Any]],
    top_n: int = 3,
) -> dict[tuple[str, str], list[LogErrorSignature]]:
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}

    for stream in result:
        labels = stream.get("stream", {})
        namespace = labels.get("namespace")
        pod = labels.get("pod") or labels.get("pod_name")
        if not namespace or not pod:
            continue
        key = (namespace, pod)
        for raw_timestamp, line in stream.get("values", []):
            if not isinstance(line, str) or not ERROR_KEYWORD_PATTERN.search(line):
                continue
            timestamp = _loki_timestamp(raw_timestamp)
            signature = signature_for_log_line(line)
            bucket = grouped.setdefault(key, {}).setdefault(
                signature,
                {
                    "count": 0,
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "sample": line.strip()[:500],
                },
            )
            bucket["count"] += 1
            bucket["first_seen"] = min(bucket["first_seen"], timestamp)
            bucket["last_seen"] = max(bucket["last_seen"], timestamp)

    output: dict[tuple[str, str], list[LogErrorSignature]] = {}
    for key, signatures in grouped.items():
        top_signatures = sorted(
            signatures.items(),
            key=lambda item: (-item[1]["count"], item[0]),
        )[:top_n]
        output[key] = [
            LogErrorSignature(
                signature=signature,
                count=data["count"],
                first_seen=data["first_seen"],
                last_seen=data["last_seen"],
                sample=data["sample"],
            )
            for signature, data in top_signatures
        ]
    return output


def signature_for_log_line(line: str) -> str:
    lines = [part.strip() for part in line.splitlines() if part.strip()]
    if not lines:
        return "empty log line"

    error_line = next((part for part in lines if ERROR_KEYWORD_PATTERN.search(part)), lines[0])
    stack_frame = next((part for part in lines if STACK_FRAME_PATTERN.search(part)), None)
    normalized = _normalize_message(error_line)
    if stack_frame and stack_frame != error_line:
        normalized = f"{normalized} | {normalize_stack_frame(stack_frame)}"
    return normalized[:220]


def normalize_stack_frame(line: str) -> str:
    return _normalize_message(line)


def _normalize_message(message: str) -> str:
    normalized = UUID_PATTERN.sub("<uuid>", message)
    normalized = HEX_PATTERN.sub("<hex>", normalized)
    normalized = NUMBER_PATTERN.sub("<num>", normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized)
    return normalized.strip().lower()


def _loki_timestamp(raw_timestamp: str) -> datetime:
    try:
        nanoseconds = int(raw_timestamp)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(nanoseconds / 1_000_000_000, tz=timezone.utc)
