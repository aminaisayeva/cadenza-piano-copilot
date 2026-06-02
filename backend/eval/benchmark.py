"""Offline continuation benchmark.

Task: give each suggester the first K notes of a real melody and ask it to
continue; score the predicted notes against the actual next M notes.

Ground truth = soprano lines from the Bach chorale corpus that ships *inside*
music21 (no download, permissively distributed, cited in REPORT.md). This makes
the benchmark reproducible on any machine with zero data setup.

The rule-based suggester is the baseline; Phase 3 adds Aria/AMT rows behind the
same `Suggester` interface, so the numbers become a real model comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

from music21 import corpus

from app.suggesters import RuleBasedSuggester, Suggester, SuggestionContext

from .metrics import Note, note_f1, pitch_class_cosine, rhythm_similarity
from .theory_checks import theory_score

# Chorales known to be in the bundled corpus. Missing ones are skipped & logged.
CHORALES = [
    "bach/bwv66.6",
    "bach/bwv7.7",
    "bach/bwv26.6",
    "bach/bwv1.6",
    "bach/bwv10.7",
    "bach/bwv267",
    "bach/bwv145.5",
    "bach/bwv40.8",
]


@dataclass
class Piece:
    name: str
    key: str
    notes: list[tuple[int, float, float]]  # (midi, onset_beats, duration_beats)


def load_test_pieces(ids: list[str] = CHORALES) -> tuple[list[Piece], list[str]]:
    """Return (pieces, skipped_ids). Soprano (top) line of each chorale."""
    pieces: list[Piece] = []
    skipped: list[str] = []
    for cid in ids:
        try:
            score = corpus.parse(cid)
            soprano = score.parts[0].flatten().notes
            notes = [
                (n.pitch.midi, float(n.offset), float(n.duration.quarterLength))
                for n in soprano
                if n.isNote
            ]
            if len(notes) < 12:
                skipped.append(cid)
                continue
            key_name = score.analyze("key").name
            pieces.append(Piece(name=cid, key=key_name, notes=notes))
        except Exception:
            skipped.append(cid)
    return pieces, skipped


@dataclass
class SuggesterResult:
    model: str
    n_pieces: int
    note_f1: float
    pc_cosine: float
    rhythm: float
    theory: float


def _eval_one(
    suggester: Suggester, piece: Piece, k_prefix: int, m_predict: int
) -> tuple[float, float, float, float]:
    prefix = piece.notes[:k_prefix]
    truth_raw = piece.notes[k_prefix : k_prefix + m_predict]
    if not truth_raw:
        return 0.0, 0.0, 0.0, 0.0

    o0 = truth_raw[0][1]
    truth: list[Note] = [(p, onset - o0) for p, onset, _ in truth_raw]

    ctx = SuggestionContext(
        history=[p for p, _, _ in prefix], held=[], key=piece.key
    )
    suggested = suggester.suggest(ctx, mode="continue")
    pred: list[Note] = [(s.note, s.start) for s in suggested]

    f1 = note_f1(pred, truth)
    pcc = pitch_class_cosine(pred, truth)
    rhy = rhythm_similarity(pred, truth)
    theory = theory_score([p for p, _ in pred], piece.key).overall
    return f1, pcc, rhy, theory


def run_benchmark(
    suggesters: list[Suggester] | None = None,
    k_prefix: int = 8,
    m_predict: int = 4,
) -> tuple[list[SuggesterResult], list[str]]:
    if suggesters is None:
        suggesters = [RuleBasedSuggester()]
    pieces, skipped = load_test_pieces()

    results: list[SuggesterResult] = []
    for sug in suggesters:
        f1s, pccs, rhys, ths = [], [], [], []
        for piece in pieces:
            f1, pcc, rhy, th = _eval_one(sug, piece, k_prefix, m_predict)
            f1s.append(f1)
            pccs.append(pcc)
            rhys.append(rhy)
            ths.append(th)
        n = max(len(pieces), 1)
        results.append(
            SuggesterResult(
                model=sug.name,
                n_pieces=len(pieces),
                note_f1=sum(f1s) / n,
                pc_cosine=sum(pccs) / n,
                rhythm=sum(rhys) / n,
                theory=sum(ths) / n,
            )
        )
    return results, skipped


if __name__ == "__main__":  # pragma: no cover
    results, skipped = run_benchmark()
    for r in results:
        print(
            f"{r.model:12s} pieces={r.n_pieces} "
            f"F1={r.note_f1:.3f} pc_cos={r.pc_cosine:.3f} "
            f"rhythm={r.rhythm:.3f} theory={r.theory:.3f}"
        )
    if skipped:
        print(f"skipped: {skipped}")
