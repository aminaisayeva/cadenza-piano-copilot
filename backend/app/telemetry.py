"""Append-only telemetry for the evaluation layer.

Every suggestion shown and every accept/dismiss decision is logged as one JSONL
line. Phase 5's eval reads this file to compute acceptance rate (overall, per
mode, per model) and latency percentiles — the Copilot-style headline metric.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).resolve().parent.parent / "telemetry"
LOG_PATH = LOG_DIR / "events.jsonl"


def _append(record: dict) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    record["ts"] = time.time()
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")


def log_suggestion(
    suggestion_id: str, mode: str, model: str, latency_ms: float, n_notes: int
) -> None:
    _append(
        {
            "kind": "suggestion",
            "id": suggestion_id,
            "mode": mode,
            "model": model,
            "latency_ms": latency_ms,
            "n_notes": n_notes,
        }
    )


def log_decision(suggestion_id: str, accepted: bool) -> None:
    _append({"kind": "decision", "id": suggestion_id, "accepted": accepted})


def read_events(path: Optional[Path] = None) -> list[dict]:
    p = path or LOG_PATH
    if not p.exists():
        return []
    with p.open() as f:
        return [json.loads(line) for line in f if line.strip()]
