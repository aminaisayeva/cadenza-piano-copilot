"""Similarity metrics for the offline benchmark.

Each compares a *predicted* note sequence against the *ground-truth* continuation:
  * note_f1            — onset+pitch overlap (the primary metric)
  * pitch_class_cosine — does it use the same notes? (harmonic fit)
  * rhythm_similarity  — does it move at the same pace?

Notes are (pitch, onset) tuples with onsets in beats, both aligned to start at 0.
"""

from __future__ import annotations

import math

Note = tuple[int, float]  # (midi_pitch, onset_in_beats)


def note_f1(pred: list[Note], true: list[Note], onset_tol: float = 0.25) -> float:
    """Greedy onset+pitch matching -> F1. Exact pitch, onset within tolerance."""
    if not pred and not true:
        return 1.0
    if not pred or not true:
        return 0.0

    remaining = list(true)
    matched = 0
    for p_pitch, p_onset in pred:
        for i, (t_pitch, t_onset) in enumerate(remaining):
            if t_pitch == p_pitch and abs(t_onset - p_onset) <= onset_tol:
                matched += 1
                remaining.pop(i)
                break

    precision = matched / len(pred)
    recall = matched / len(true)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _pc_histogram(notes: list[Note]) -> list[float]:
    hist = [0.0] * 12
    for pitch, _ in notes:
        hist[pitch % 12] += 1
    return hist


def pitch_class_cosine(pred: list[Note], true: list[Note]) -> float:
    """Cosine similarity of pitch-class histograms (0..1)."""
    a, b = _pc_histogram(pred), _pc_histogram(true)
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _iois(notes: list[Note]) -> list[float]:
    onsets = sorted(o for _, o in notes)
    return [b - a for a, b in zip(onsets, onsets[1:])]


def rhythm_similarity(pred: list[Note], true: list[Note]) -> float:
    """1 / (1 + |mean IOI difference|). Closer pacing -> closer to 1."""
    ip, it = _iois(pred), _iois(true)
    if not ip and not it:
        return 1.0
    if not ip or not it:
        return 0.0
    mean_p = sum(ip) / len(ip)
    mean_t = sum(it) / len(it)
    return 1.0 / (1.0 + abs(mean_p - mean_t))
