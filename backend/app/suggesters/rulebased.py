"""RuleBasedSuggester — the instant, zero-dependency v1 suggester.

It is deliberately simple but *musically valid*: every suggestion is diatonic to
the detected key. Its job is to make the whole ghost-note loop demoable on day
one and to serve as the baseline the ML models are measured against in the eval
layer. Quality is intentionally modest — Aria/AMT replace it in Phase 3.
"""

from __future__ import annotations

from typing import Optional

from music21 import key as m21key

from .base import Mode, SuggestedNote, Suggester, SuggestionContext

MIDDLE_C = 60


def _parse_key(name: Optional[str]) -> m21key.Key:
    """'G major' / 'e minor' -> music21 Key. Falls back to C major."""
    if not name:
        return m21key.Key("C")
    parts = name.split()
    tonic = parts[0]
    mode = parts[1] if len(parts) > 1 else "major"
    try:
        return m21key.Key(tonic, mode)
    except Exception:
        return m21key.Key("C")


def _diatonic_midi(k: m21key.Key, lo: int, hi: int) -> list[int]:
    """Sorted MIDI notes within [lo, hi] that belong to the key's scale."""
    pcs = {p.pitchClass for p in k.getScale().getPitches("C0", "C9")}
    return [m for m in range(lo, hi + 1) if m % 12 in pcs]


def _nearest_index(notes: list[int], target: int) -> int:
    """Index of the value in `notes` closest to `target`."""
    return min(range(len(notes)), key=lambda i: abs(notes[i] - target))


class RuleBasedSuggester(Suggester):
    name = "rule-based"

    def suggest(
        self, ctx: SuggestionContext, mode: Mode = "continue", style: Optional[str] = None
    ) -> list[SuggestedNote]:
        k = _parse_key(ctx.key)
        if mode == "continue":
            return self._continue(k, ctx)
        if mode == "harmonize":
            return self._harmonize(k, ctx, substitution=False)
        if mode == "reharmonize":
            return self._harmonize(k, ctx, substitution=True)
        return []

    # -- continuation: a short ascending diatonic motif resolving to a scale tone
    def _continue(self, k: m21key.Key, ctx: SuggestionContext) -> list[SuggestedNote]:
        ref = ctx.history[-1] if ctx.history else MIDDLE_C
        diat = _diatonic_midi(k, ref - 2, ref + 16)
        if not diat:
            return []
        i = _nearest_index(diat, ref)
        # four ascending stepwise scale tones starting just above the last note
        idxs = [min(i + step, len(diat) - 1) for step in (1, 2, 3, 4)]
        return [
            SuggestedNote(note=diat[j], start=n * 0.5, duration=0.5)
            for n, j in enumerate(idxs)
        ]

    # -- harmonization: a diatonic triad under the melody note (the top voice)
    def _harmonize(
        self, k: m21key.Key, ctx: SuggestionContext, substitution: bool
    ) -> list[SuggestedNote]:
        target = (ctx.held[-1] if ctx.held else ctx.history[-1] if ctx.history else MIDDLE_C)
        diat = _diatonic_midi(k, target - 24, target + 2)
        if len(diat) < 7:
            return []
        # find a diatonic note matching the melody's pitch class, near the top
        candidates = [j for j in range(len(diat)) if diat[j] % 12 == target % 12]
        i = candidates[-1] if candidates else _nearest_index(diat, target)
        # triad = stacked diatonic thirds (skip a scale degree => +2 indices).
        # melody sits on top (the chordal fifth): root at i-4, third i-2, fifth i.
        offset = 6 if substitution else 4  # a third lower => I->vi style sub
        root = max(i - offset, 0)
        triad_idxs = [root, min(root + 2, len(diat) - 1), min(root + 4, len(diat) - 1)]
        return [
            SuggestedNote(note=diat[j], start=0.0, duration=2.0) for j in triad_idxs
        ]
