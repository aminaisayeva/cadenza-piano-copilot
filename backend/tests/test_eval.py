"""Tests for the evaluation layer: metrics, theory checks, acceptance stats."""

from eval.metrics import note_f1, pitch_class_cosine, rhythm_similarity
from eval.report import compute_acceptance_stats
from eval.theory_checks import in_key_ratio, leap_smoothness, theory_score


# ---- metrics --------------------------------------------------------------


def test_note_f1_perfect_match():
    seq = [(60, 0.0), (62, 1.0), (64, 2.0)]
    assert note_f1(seq, seq) == 1.0


def test_note_f1_no_overlap():
    assert note_f1([(60, 0.0)], [(72, 0.0)]) == 0.0


def test_note_f1_onset_tolerance():
    # within 0.25 beats -> still a match
    assert note_f1([(60, 0.0)], [(60, 0.2)]) == 1.0
    # outside tolerance -> miss
    assert note_f1([(60, 0.0)], [(60, 0.6)]) == 0.0


def test_pitch_class_cosine_identical_classes():
    a = [(60, 0.0), (64, 1.0)]
    b = [(72, 0.0), (76, 1.0)]  # same pitch classes, different octaves
    assert abs(pitch_class_cosine(a, b) - 1.0) < 1e-9


def test_rhythm_similarity_same_pace():
    a = [(60, 0.0), (62, 1.0), (64, 2.0)]
    assert rhythm_similarity(a, a) == 1.0


# ---- theory checks --------------------------------------------------------


def test_in_key_ratio_all_diatonic():
    assert in_key_ratio([60, 62, 64, 65, 67], "C major") == 1.0


def test_in_key_ratio_with_chromatic():
    # C, C# (out), D -> 2/3 in key
    assert abs(in_key_ratio([60, 61, 62], "C major") - 2 / 3) < 1e-9


def test_leap_smoothness_stepwise_is_smooth():
    assert leap_smoothness([60, 62, 64]) == 1.0


def test_leap_smoothness_penalizes_big_leaps():
    # 60 -> 80 is a 20-semitone leap (> major sixth)
    assert leap_smoothness([60, 80]) == 0.0


def test_theory_score_in_range():
    s = theory_score([60, 62, 64, 65], "C major")
    assert 0.0 <= s.overall <= 1.0
    assert s.in_key == 1.0


# ---- acceptance stats -----------------------------------------------------


def test_compute_acceptance_stats():
    events = [
        {"kind": "suggestion", "id": "a", "mode": "continue", "model": "rule-based", "latency_ms": 2.0},
        {"kind": "suggestion", "id": "b", "mode": "continue", "model": "rule-based", "latency_ms": 4.0},
        {"kind": "decision", "id": "a", "accepted": True},
        {"kind": "decision", "id": "b", "accepted": False},
    ]
    stats = compute_acceptance_stats(events)
    assert stats["total_suggestions"] == 2
    assert stats["total_decisions"] == 2
    assert stats["overall_rate"] == 0.5
    assert stats["by_model"]["rule-based"] == 0.5
    assert stats["latency_p50"] in (2.0, 3.0, 4.0)  # median of two -> 3.0
