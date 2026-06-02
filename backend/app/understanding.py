"""Live harmonic understanding via music21.

Two layers:

* `analyze_window` — a *pure* function (pitch history + currently-held notes ->
  key / chord / roman numeral). Pure so the eval layer and tests can call it
  deterministically.
* `Session` — per-connection state (a rolling history + the set of held notes)
  that calls `analyze_window` after each MIDI event.

Everything here runs on short windows (a handful of notes), where music21's
Krumhansl-Schmuckler key detection and chord identification are cheap enough for
the real-time loop.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from music21 import chord as m21chord
from music21 import key as m21key
from music21 import note as m21note
from music21 import roman, stream

# How many recent pitches feed key detection.
HISTORY_LEN = 24
# Below this, key detection is too unstable to report.
MIN_NOTES_FOR_KEY = 4


@dataclass
class AnalysisResult:
    key: Optional[str] = None
    chord: Optional[str] = None
    roman: Optional[str] = None

    def as_message(self) -> dict:
        return {"type": "analysis", "key": self.key, "chord": self.chord, "roman": self.roman}


def detect_key(pitches: list[int]) -> Optional[m21key.Key]:
    """Krumhansl-Schmuckler key estimate over a window of MIDI pitches."""
    if len(pitches) < MIN_NOTES_FOR_KEY:
        return None
    s = stream.Stream()
    for p in pitches:
        s.append(m21note.Note(p))
    try:
        return s.analyze("key")
    except Exception:
        return None


def describe_chord(held: list[int]) -> Optional[m21chord.Chord]:
    """Build a music21 Chord from currently-held MIDI notes (need >= 2)."""
    if len(held) < 2:
        return None
    try:
        return m21chord.Chord(sorted(held))
    except Exception:
        return None


def analyze_window(history: list[int], held: list[int]) -> AnalysisResult:
    """Pure analysis: recent pitch history + held notes -> key/chord/roman."""
    result = AnalysisResult()

    k = detect_key(history)
    if k is not None:
        result.key = k.name  # e.g. "G major"

    ch = describe_chord(held)
    if ch is not None:
        # pitchedCommonName gives e.g. "C-sharp minor seventh chord"; the
        # compact figured name is nicer for a HUD.
        result.chord = ch.pitchedCommonName
        if k is not None:
            try:
                result.roman = roman.romanNumeralFromChord(ch, k).figure
            except Exception:
                result.roman = None
    elif len(held) == 1:
        result.chord = m21note.Note(held[0]).nameWithOctave

    return result


@dataclass
class Session:
    """Per-WebSocket-connection musical state."""

    history: deque[int] = field(default_factory=lambda: deque(maxlen=HISTORY_LEN))
    held: set[int] = field(default_factory=set)

    def note_on(self, midi: int) -> AnalysisResult:
        self.held.add(midi)
        self.history.append(midi)
        return self.analyze()

    def note_off(self, midi: int) -> AnalysisResult:
        self.held.discard(midi)
        return self.analyze()

    def analyze(self) -> AnalysisResult:
        return analyze_window(list(self.history), sorted(self.held))
