"""AMT integration test — opt-in (slow: loads a model + generates).

Run with:  CADENZA_RUN_MODEL_TESTS=1 pytest tests/test_amt.py
Skipped by default so the main suite stays fast.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("CADENZA_RUN_MODEL_TESTS"),
    reason="set CADENZA_RUN_MODEL_TESTS=1 to run model tests",
)


def test_amt_continue_returns_valid_notes():
    from app.suggesters.amt import AMTSuggester
    from app.suggesters.base import SuggestionContext

    s = AMTSuggester()
    ctx = SuggestionContext(history=[60, 62, 64, 65, 67, 69, 71, 72], held=[], key="C major")
    notes = s.suggest(ctx, mode="continue")
    assert len(notes) >= 1
    assert all(0 <= n.note <= 127 for n in notes)
    assert all(n.start >= 0 and n.duration > 0 for n in notes)


def test_amt_empty_history_returns_empty():
    from app.suggesters.amt import AMTSuggester
    from app.suggesters.base import SuggestionContext

    s = AMTSuggester()
    assert s.suggest(SuggestionContext(history=[], held=[], key="C major")) == []
