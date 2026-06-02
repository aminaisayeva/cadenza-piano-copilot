"""Bridge between Cadenza's note lists and MIDI files.

Both Aria and the Anticipatory Music Transformer take/return MIDI *files*, while
the rest of Cadenza works with note lists. These helpers (built on music21,
already a dependency) convert in both directions through a temp file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from music21 import converter, note, stream, tempo

# A synthetic tempo so beat<->second conversions are stable (120bpm: 1 beat=0.5s).
DEFAULT_BPM = 120


def pitches_to_midi(pitches: list[int], path: str, beat_per_note: float = 1.0) -> None:
    """Write a monophonic prompt: each pitch as one note, evenly spaced in time.

    The understanding layer only retains pitch history (no timing), so we
    synthesize a simple steady rhythm to give the models a playable prompt.
    """
    s = stream.Stream()
    s.insert(0, tempo.MetronomeMark(number=DEFAULT_BPM))
    for i, p in enumerate(pitches):
        n = note.Note(p)
        n.quarterLength = beat_per_note
        s.insert(i * beat_per_note, n)
    s.write("midi", fp=path)


def midi_to_notes(path: str) -> list[tuple[int, float, float]]:
    """Parse a MIDI file -> sorted [(midi_pitch, onset_beats, duration_beats)]."""
    score = converter.parse(path)
    out: list[tuple[int, float, float]] = []
    for n in score.flatten().notes:
        if n.isNote:
            out.append((n.pitch.midi, float(n.offset), float(n.quarterLength)))
        elif n.isChord:
            for p in n.pitches:
                out.append((p.midi, float(n.offset), float(n.quarterLength)))
    return sorted(out, key=lambda x: x[1])


def temp_midi_path() -> str:
    """A unique temp .mid path (caller is responsible for cleanup)."""
    fd = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    fd.close()
    return str(Path(fd.name))
