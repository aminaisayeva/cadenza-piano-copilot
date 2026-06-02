"""Tests for the music21 understanding layer."""

from music21 import key as m21key
from music21 import roman

from app.understanding import (
    Session,
    analyze_window,
    describe_chord,
    detect_key,
)


def test_describe_chord_major_triad():
    ch = describe_chord([60, 64, 67])  # C E G
    assert ch is not None
    assert "major" in ch.pitchedCommonName.lower()


def test_describe_chord_needs_two_notes():
    assert describe_chord([60]) is None
    assert describe_chord([]) is None


def test_roman_numeral_tonic_in_c():
    # Deterministic music21 path: C major triad in key of C is I.
    ch = describe_chord([60, 64, 67])
    rn = roman.romanNumeralFromChord(ch, m21key.Key("C"))
    assert rn.figure == "I"


def test_detect_key_on_c_major_scale():
    scale = [60, 62, 64, 65, 67, 69, 71, 72]
    k = detect_key(scale)
    assert k is not None
    # Krumhansl should land on C major (or its relative a minor); tonic class 0 or 9.
    assert k.tonic.pitchClass in (0, 9)


def test_analyze_window_full():
    res = analyze_window([60, 62, 64, 65, 67, 69, 71, 72], [60, 64, 67])
    assert res.key is not None
    assert res.chord is not None


def test_session_tracks_held_notes():
    s = Session()
    s.note_on(60)
    s.note_on(64)
    res = s.note_on(67)  # C major triad held
    assert res.chord is not None
    res2 = s.note_off(64)
    # After releasing E, only C and G held -> still a (dyad) chord or note
    assert res2 is not None
    assert 64 not in s.held
