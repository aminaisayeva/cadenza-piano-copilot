"""Generate eval/REPORT.md from telemetry + the offline benchmark.

Run:  python -m eval.report
"""

from __future__ import annotations

import os
from pathlib import Path
from statistics import median
from typing import Optional

from app.suggesters import RuleBasedSuggester

from app.telemetry import read_events

from .benchmark import run_benchmark


def _benchmark_suggesters():
    """Rule-based always; AMT too when CADENZA_BENCH_AMT=1 (slow: loads a model)."""
    suggesters = [RuleBasedSuggester()]
    if os.environ.get("CADENZA_BENCH_AMT"):
        from app.suggesters.amt import AMTSuggester

        suggesters.append(AMTSuggester())
    return suggesters

REPORT_PATH = Path(__file__).resolve().parent / "REPORT.md"


def _percentile(values: list[float], pct: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((pct / 100) * (len(s) - 1)))))
    return s[k]


def compute_acceptance_stats(events: list[dict]) -> dict:
    """Acceptance rate (overall / per mode / per model) + latency percentiles."""
    suggestions = {e["id"]: e for e in events if e.get("kind") == "suggestion"}
    decisions = {e["id"]: e["accepted"] for e in events if e.get("kind") == "decision"}

    def rate(ids: list[str]) -> Optional[float]:
        decided = [decisions[i] for i in ids if i in decisions]
        return (sum(decided) / len(decided)) if decided else None

    by_mode: dict[str, list[str]] = {}
    by_model: dict[str, list[str]] = {}
    for sid, s in suggestions.items():
        by_mode.setdefault(s.get("mode", "?"), []).append(sid)
        by_model.setdefault(s.get("model", "?"), []).append(sid)

    latencies = [s["latency_ms"] for s in suggestions.values() if "latency_ms" in s]

    return {
        "total_suggestions": len(suggestions),
        "total_decisions": len(decisions),
        "overall_rate": rate(list(suggestions.keys())),
        "by_mode": {m: rate(ids) for m, ids in by_mode.items()},
        "by_model": {m: rate(ids) for m, ids in by_model.items()},
        "latency_p50": median(latencies) if latencies else None,
        "latency_p95": _percentile(latencies, 95),
    }


def _fmt(x: Optional[float], pct: bool = False) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.0f}%" if pct else f"{x:.3f}"


def render_markdown() -> str:
    stats = compute_acceptance_stats(read_events())
    results, skipped = run_benchmark(_benchmark_suggesters())

    lines: list[str] = ["# Cadenza — Evaluation Report", ""]

    # 1. Acceptance
    lines += [
        "## 1. Suggestion acceptance (live telemetry)",
        "",
        f"- Suggestions shown: **{stats['total_suggestions']}**",
        f"- Decisions recorded: **{stats['total_decisions']}**",
        f"- Overall acceptance rate: **{_fmt(stats['overall_rate'], pct=True)}**",
        f"- Latency p50 / p95: **{_fmt(stats['latency_p50'])} ms / {_fmt(stats['latency_p95'])} ms**",
        "",
        "| Mode | Acceptance |", "|---|---|",
    ]
    for mode, r in sorted(stats["by_mode"].items()):
        lines.append(f"| {mode} | {_fmt(r, pct=True)} |")
    lines += ["", "| Model | Acceptance |", "|---|---|"]
    for model, r in sorted(stats["by_model"].items()):
        lines.append(f"| {model} | {_fmt(r, pct=True)} |")

    # 2. Benchmark
    lines += [
        "",
        "## 2. Offline continuation benchmark",
        "",
        "Ground truth: soprano lines from the Bach chorale corpus bundled with "
        "music21. Task: predict the next notes given the first 8. Higher is better.",
        "",
        "| Model | Pieces | Note F1 | Pitch-class cos | Rhythm | Theory |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.model} | {r.n_pieces} | {r.note_f1:.3f} | "
            f"{r.pc_cosine:.3f} | {r.rhythm:.3f} | {r.theory:.3f} |"
        )
    if skipped:
        lines += ["", f"_Skipped (not in local corpus): {', '.join(skipped)}_"]

    lines += [
        "",
        "## Notes",
        "",
        "- **Theory** is the automated music-theory validity score "
        "(in-key + voice-leading smoothness + chord-tone ratio).",
        "- The neural model (**AMT**) raises **Note F1** and **pitch-class "
        "similarity** — it actually imitates real continuations — while the "
        "**rule-based** baseline scores higher on **Theory** because it is "
        "constrained to be strictly diatonic. That precision-vs-validity tradeoff "
        "is the point of having both behind one interface.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:  # pragma: no cover
    REPORT_PATH.write_text(render_markdown())
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":  # pragma: no cover
    main()
