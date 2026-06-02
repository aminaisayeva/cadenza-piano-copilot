"""WebSocket message protocol shared across phases.

The same envelope is used in both directions; `type` discriminates. Keeping the
schema in one place means the frontend `ws.ts` types can mirror it 1:1.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


# ---- Client -> Server ----------------------------------------------------


class NoteOn(BaseModel):
    type: Literal["note_on"] = "note_on"
    note: int           # MIDI note number 0-127
    velocity: int       # 1-127
    time: float         # client timestamp in seconds (performance.now()/1000)


class NoteOff(BaseModel):
    type: Literal["note_off"] = "note_off"
    note: int
    time: float


class RequestSuggestion(BaseModel):
    type: Literal["request_suggestion"] = "request_suggestion"
    mode: Literal["continue", "harmonize", "reharmonize"] = "continue"
    style: Optional[str] = None
    model: Optional[str] = None  # "rule-based" | "amt"


class SuggestionDecision(BaseModel):
    """User accepted or dismissed a suggestion (feeds the eval acceptance rate)."""

    type: Literal["decision"] = "decision"
    suggestion_id: str
    accepted: bool


# ---- Server -> Client ----------------------------------------------------


class Analysis(BaseModel):
    type: Literal["analysis"] = "analysis"
    key: Optional[str] = None          # e.g. "G major"
    chord: Optional[str] = None        # e.g. "Dm7"
    roman: Optional[str] = None        # e.g. "ii7"


class SuggestedNote(BaseModel):
    note: int           # MIDI note number
    start: float        # beats from start of suggestion
    duration: float     # beats


class Suggestion(BaseModel):
    type: Literal["suggestion"] = "suggestion"
    id: str
    mode: str
    model: str          # which suggester produced it (for per-model eval)
    notes: list[SuggestedNote]
    explanation: Optional[str] = None
    latency_ms: Optional[float] = None


class Ack(BaseModel):
    type: Literal["ack"] = "ack"
    echo: dict
