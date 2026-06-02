"""Automated music-theory validity checks.

Rigor without a human in the loop: given a key and a suggestion's pitches, score
how musically valid it is. Aggregated per model, this yields the headline
"suggestions pass theory checks N% of the time" claim.

All checks are pure functions over MIDI pitch lists so they're trivially testable
and can run both in the offline benchmark and (optionally) live.
"""

from __future__ import annotations

from dataclasses import dataclass

from music21 import key as m21key

# Consecutive melodic intervals wider than this (semitones) read as "leaps".
SMOOTH_LEAP_MAX = 9  # a major sixth


def _scale_pcs(key_name: str) -> set[int]:
    parts = key_name.split()
    try:
        k = m21key.Key(parts[0], parts[1] if len(parts) > 1 else "major")
    except Exception:
        k = m21key.Key("C")
    return {p.pitchClass for p in k.getScale().getPitches("C0", "C9")}


def _tonic_triad_pcs(key_name: str) -> set[int]:
    parts = key_name.split()
    try:
        k = m21key.Key(parts[0], parts[1] if len(parts) > 1 else "major")
    except Exception:
        k = m21key.Key("C")
    return {p.pitchClass for p in k.pitches[:1]} | {
        (k.tonic.pitchClass + i) % 12 for i in ((0, 3, 7) if k.mode == "minor" else (0, 4, 7))
    }


def in_key_ratio(pitches: list[int], key_name: str) -> float:
    """Fraction of pitches that belong to the key's scale."""
    if not pitches:
        return 0.0
    pcs = _scale_pcs(key_name)
    return sum(1 for p in pitches if p % 12 in pcs) / len(pitches)


def chord_tone_ratio(pitches: list[int], key_name: str) -> float:
    """Fraction of pitches that are tones of the tonic triad (a proxy for consonance)."""
    if not pitches:
        return 0.0
    triad = _tonic_triad_pcs(key_name)
    return sum(1 for p in pitches if p % 12 in triad) / len(pitches)


def leap_smoothness(pitches: list[int]) -> float:
    """Fraction of consecutive intervals that are stepwise/small (good voice leading).

    A single note (no intervals) is treated as perfectly smooth.
    """
    if len(pitches) < 2:
        return 1.0
    intervals = [abs(b - a) for a, b in zip(pitches, pitches[1:])]
    return sum(1 for iv in intervals if iv <= SMOOTH_LEAP_MAX) / len(intervals)


@dataclass
class TheoryScore:
    in_key: float
    chord_tone: float
    smoothness: float
    overall: float


def theory_score(pitches: list[int], key_name: str) -> TheoryScore:
    """Weighted blend: being in-key matters most, then smoothness, then consonance."""
    ik = in_key_ratio(pitches, key_name)
    ct = chord_tone_ratio(pitches, key_name)
    sm = leap_smoothness(pitches)
    overall = 0.5 * ik + 0.3 * sm + 0.2 * ct
    return TheoryScore(in_key=ik, chord_tone=ct, smoothness=sm, overall=overall)
