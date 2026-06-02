"""Tests for the theory tutor's grounded analysis + deterministic phrasing.

These cover the offline path (no API key needed). The Claude path is exercised
only when ANTHROPIC_API_KEY is present.
"""

import os

import pytest

from app.tutor import compute_facts, deterministic_explanation, explain


def test_facts_identify_tonic_triad_in_c():
    facts = compute_facts("C major", [60, 64, 67])  # C major triad
    assert facts.roman == "I"
    assert "major" in (facts.chord or "").lower()


def test_facts_scale_degrees():
    facts = compute_facts("C major", [60, 67])  # tonic + dominant
    assert "tonic" in facts.degrees
    assert "dominant" in facts.degrees


def test_deterministic_harmonize_mentions_chord_and_key():
    facts = compute_facts("C major", [60, 64, 67])
    text = deterministic_explanation(facts, "harmonize")
    assert "C major" in text
    assert "I" in text  # roman numeral surfaced


def test_deterministic_continue_is_nonempty():
    facts = compute_facts("G major", [67, 69, 71])
    text = deterministic_explanation(facts, "continue")
    assert isinstance(text, str) and len(text) > 0


def test_explain_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    text = explain("C major", [60, 64, 67], "harmonize")
    assert "C major" in text


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY"
)
def test_claude_path_runs():
    text = explain("C major", [60, 64, 67], "harmonize")
    assert isinstance(text, str) and len(text) > 0
