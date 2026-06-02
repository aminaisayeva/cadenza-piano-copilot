"""Theory tutor: explains WHY a suggestion works.

Hybrid by design:
  * music21 computes the *ground-truth* facts (key, the suggestion's chord &
    roman numeral, scale degrees) — so the theory is always correct.
  * If ANTHROPIC_API_KEY is set, Claude phrases those facts as natural coaching.
  * Otherwise a deterministic template turns the same facts into a sentence.

The facts are computed once and shared by both paths, so the Claude version is
grounded (low hallucination) and the offline version says the same thing, plainer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from music21 import chord as m21chord
from music21 import key as m21key
from music21 import pitch as m21pitch
from music21 import roman as m21roman

TUTOR_MODEL = "claude-haiku-4-5"

DEGREE_NAMES = {
    1: "tonic", 2: "supertonic", 3: "mediant", 4: "subdominant",
    5: "dominant", 6: "submediant", 7: "leading tone",
}


@dataclass
class Facts:
    key: Optional[str]
    chord: Optional[str]
    roman: Optional[str]
    degrees: list[str]


def _key_obj(key_name: Optional[str]) -> m21key.Key:
    if not key_name:
        return m21key.Key("C")
    parts = key_name.split()
    try:
        return m21key.Key(parts[0], parts[1] if len(parts) > 1 else "major")
    except Exception:
        return m21key.Key("C")


def compute_facts(key_name: Optional[str], pitches: list[int]) -> Facts:
    """Ground-truth analysis of a suggestion's pitches within a key."""
    k = _key_obj(key_name)

    chord_name = roman_fig = None
    if len(pitches) >= 2:
        try:
            ch = m21chord.Chord(sorted(pitches))
            chord_name = ch.pitchedCommonName
            roman_fig = m21roman.romanNumeralFromChord(ch, k).figure
        except Exception:
            pass

    degrees: list[str] = []
    for p in pitches:
        try:
            deg = k.getScaleDegreeFromPitch(m21pitch.Pitch(midi=p))
            if deg in DEGREE_NAMES:
                degrees.append(DEGREE_NAMES[deg])
        except Exception:
            continue

    return Facts(key=key_name, chord=chord_name, roman=roman_fig, degrees=degrees)


def deterministic_explanation(facts: Facts, mode: str) -> str:
    key = facts.key or "the current key"
    if mode in ("harmonize", "reharmonize") and facts.chord:
        verb = "reharmonizes with" if mode == "reharmonize" else "harmonizes to"
        roman = f" ({facts.roman})" if facts.roman else ""
        return f"In {key}, this {verb} a {facts.chord}{roman} under your melody."
    # continuation
    if facts.degrees:
        uniq = list(dict.fromkeys(facts.degrees))
        target = uniq[-1]
        return f"This continuation stays in {key}, moving toward the {target}."
    return f"This continuation stays diatonic to {key}."


def claude_explanation(facts: Facts, mode: str) -> str:
    """Phrase the facts as coaching via Claude. Raises if unavailable."""
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY
    system = (
        "You are a concise, encouraging piano composition tutor. Given factual "
        "music-theory analysis, explain in ONE or TWO short sentences why the "
        "suggested notes work and what idea they introduce. Use ONLY the provided "
        "facts; never invent theory. No preamble."
    )
    user = (
        f"Mode: {mode}\n"
        f"Key: {facts.key}\n"
        f"Suggestion chord: {facts.chord}\n"
        f"Roman numeral: {facts.roman}\n"
        f"Scale degrees used: {', '.join(facts.degrees) or 'n/a'}"
    )
    msg = client.messages.create(
        model=TUTOR_MODEL,
        max_tokens=120,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


def explain(key_name: Optional[str], pitches: list[int], mode: str) -> str:
    """Best available explanation: Claude if keyed, else deterministic template."""
    facts = compute_facts(key_name, pitches)
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return claude_explanation(facts, mode)
        except Exception:
            pass
    return deterministic_explanation(facts, mode)
