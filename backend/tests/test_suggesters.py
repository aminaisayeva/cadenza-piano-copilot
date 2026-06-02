"""Tests for the rule-based suggester: suggestions must be diatonic & well-formed."""

from music21 import key as m21key

from app.suggesters import RuleBasedSuggester, SuggestionContext


def _scale_pcs(name: str) -> set[int]:
    k = m21key.Key(*name.split())
    return {p.pitchClass for p in k.getScale().getPitches("C0", "C9")}


def test_continue_is_diatonic_and_nonempty():
    s = RuleBasedSuggester()
    ctx = SuggestionContext(history=[60, 62, 64], held=[], key="C major")
    notes = s.suggest(ctx, mode="continue")
    assert len(notes) == 4
    pcs = _scale_pcs("C major")
    assert all(n.note % 12 in pcs for n in notes)
    # starts are monotonically increasing in time
    assert [n.start for n in notes] == sorted(n.start for n in notes)


def test_harmonize_returns_triad_block_chord():
    s = RuleBasedSuggester()
    ctx = SuggestionContext(history=[67], held=[67], key="C major")  # melody G
    notes = s.suggest(ctx, mode="harmonize")
    assert len(notes) == 3
    assert all(n.start == 0.0 for n in notes)  # block chord (simultaneous)
    pcs = _scale_pcs("C major")
    assert all(n.note % 12 in pcs for n in notes)


def test_reharmonize_differs_from_harmonize():
    s = RuleBasedSuggester()
    ctx = SuggestionContext(history=[67], held=[67], key="C major")
    harm = {n.note for n in s.suggest(ctx, mode="harmonize")}
    reharm = {n.note for n in s.suggest(ctx, mode="reharmonize")}
    assert harm != reharm  # substitution picks a different chord


def test_handles_missing_key_gracefully():
    s = RuleBasedSuggester()
    ctx = SuggestionContext(history=[], held=[], key=None)
    notes = s.suggest(ctx, mode="continue")
    assert len(notes) >= 1  # falls back to C major around middle C
