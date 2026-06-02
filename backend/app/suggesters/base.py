"""The Suggester abstraction.

Everything that produces ghost-note suggestions implements `Suggester`. v1 is
`RuleBasedSuggester` (works on any machine, instant); Phase 3 adds `AriaSuggester`
and `AMTSuggester` behind the *same* interface, so the rest of the app — the
WebSocket loop, the telemetry, the eval harness — never changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional

Mode = Literal["continue", "harmonize", "reharmonize"]


@dataclass
class SuggestionContext:
    """What the suggester gets to look at."""

    history: list[int]          # recent MIDI pitches, oldest -> newest
    held: list[int]             # currently sounding MIDI notes
    key: Optional[str] = None   # e.g. "G major" (from the understanding layer)


@dataclass
class SuggestedNote:
    note: int        # MIDI number
    start: float     # beats from the start of the suggestion
    duration: float  # beats

    def as_dict(self) -> dict:
        return {"note": self.note, "start": self.start, "duration": self.duration}


class Suggester(ABC):
    #: short identifier recorded in telemetry / eval (e.g. "rule-based", "aria").
    name: str = "abstract"

    @abstractmethod
    def suggest(
        self, ctx: SuggestionContext, mode: Mode = "continue", style: Optional[str] = None
    ) -> list[SuggestedNote]:
        """Return a short suggestion (a melodic continuation or a chord)."""
        raise NotImplementedError
