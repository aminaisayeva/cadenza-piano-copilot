"""AMTSuggester — Anticipatory Music Transformer (stanford-crfm/music-small-800k).

A 128M GPT-2-style symbolic-music model. It supports both *continuation* and
*infilling via controls*, so it powers all three Cadenza modes:

* continue     -> generate notes after the prompt
* harmonize    -> treat the melody as a control track, generate accompaniment
* reharmonize  -> same, over a longer span (a fresh harmonic reading)

The model is lazy-loaded on first use (so the server still starts instantly and
the rule-based path keeps working even if weights aren't downloaded). All model
calls are wrapped defensively: any failure yields an empty suggestion rather than
crashing the WebSocket loop.
"""

from __future__ import annotations

import os
from typing import Optional

from ..midi_io import midi_to_notes, pitches_to_midi, temp_midi_path
from .base import Mode, SuggestedNote, Suggester, SuggestionContext

# Some AMT ops lack MPS kernels; allow CPU fallback for those.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

MODEL_ID = "stanford-crfm/music-small-800k"
GEN_SECONDS = 2.5      # how far past the prompt to generate (a few notes)
MAX_NOTES = 6          # cap the ghost suggestion length
BEAT_SECONDS = 0.5     # 120bpm: matches midi_io.DEFAULT_BPM


def _pick_device() -> str:
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


class AMTSuggester(Suggester):
    name = "amt"

    def __init__(self) -> None:
        self._model = None
        self._device = None

    # -- lazy model load -----------------------------------------------------
    def _ensure_model(self):
        if self._model is None:
            from transformers import AutoModelForCausalLM

            self._device = _pick_device()
            self._model = AutoModelForCausalLM.from_pretrained(MODEL_ID).to(self._device)
            self._model.eval()
        return self._model

    # -- public API ----------------------------------------------------------
    def suggest(
        self, ctx: SuggestionContext, mode: Mode = "continue", style: Optional[str] = None
    ) -> list[SuggestedNote]:
        if not ctx.history:
            return []
        try:
            if mode == "continue":
                return self._continue(ctx)
            return self._harmonize(ctx, long=(mode == "reharmonize"))
        except Exception:
            # Never break the loop on a model hiccup.
            return []

    # -- continuation --------------------------------------------------------
    def _continue(self, ctx: SuggestionContext) -> list[SuggestedNote]:
        from anticipation import ops
        from anticipation.convert import events_to_midi, midi_to_events
        from anticipation.sample import generate

        model = self._ensure_model()
        prompt_path = temp_midi_path()
        pitches_to_midi(ctx.history, prompt_path)
        events = midi_to_events(prompt_path)

        prompt_end = len(ctx.history) * BEAT_SECONDS
        gen = generate(
            model, start_time=prompt_end, end_time=prompt_end + GEN_SECONDS,
            inputs=events, top_p=0.98,
        )
        # keep only the newly generated span, shifted to start at 0
        new = ops.clip(gen, prompt_end, prompt_end + GEN_SECONDS, seconds=True)
        new = ops.translate(new, -prompt_end, seconds=True)

        out_path = temp_midi_path()
        events_to_midi(new).save(out_path)
        return self._notes_to_suggestion(midi_to_notes(out_path))

    # -- harmonization via control track ------------------------------------
    def _harmonize(self, ctx: SuggestionContext, long: bool) -> list[SuggestedNote]:
        from anticipation.convert import events_to_midi, midi_to_events
        from anticipation.sample import generate
        from anticipation.tokenize import extract_instruments

        model = self._ensure_model()
        melody_path = temp_midi_path()
        pitches_to_midi(ctx.history, melody_path)
        events = midi_to_events(melody_path)

        # Pull the (program 0) melody out as a control the model anticipates.
        _, melody = extract_instruments(events, [0])
        span = len(ctx.history) * BEAT_SECONDS * (1.0 if long else 0.5)
        accomp = generate(model, 0, max(span, 1.0), inputs=[], controls=melody, top_p=0.98)

        out_path = temp_midi_path()
        events_to_midi(accomp).save(out_path)
        notes = midi_to_notes(out_path)
        if not notes:
            return []
        # take the first few accompaniment notes as a block chord under the melody
        chord = sorted({n[0] for n in notes[:4]})
        return [SuggestedNote(note=p, start=0.0, duration=2.0) for p in chord]

    # -- helpers -------------------------------------------------------------
    def _notes_to_suggestion(self, notes: list[tuple[int, float, float]]) -> list[SuggestedNote]:
        notes = notes[:MAX_NOTES]
        if not notes:
            return []
        t0 = notes[0][1]
        return [
            SuggestedNote(note=p, start=round(onset - t0, 3), duration=round(dur, 3))
            for p, onset, dur in notes
        ]
