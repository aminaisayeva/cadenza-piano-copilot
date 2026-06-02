# Cadenza — Design Notes

## Problem

Beginner-to-intermediate pianists who want to *compose* have no low-friction way
to get ideas while they play. Notation editors are manual; generative-music demos
are offline and batch. Cadenza reframes composition as **autocomplete**: you
play, and the system proposes the next notes inline — like GitHub Copilot, but on
a staff — and explains the theory so you learn while you write.

## System overview

```
Browser (Chrome/Edge)                         Python backend (FastAPI)
  WebMidi.js  ──note on/off──┐        ┌── understanding (music21): key/chord/roman
  VexFlow (ghost notes)      ├─ WS ───┤── Suggester interface
  Tone.js + smplr (audio)    │        │     ├─ RuleBasedSuggester (diatonic, instant)
  telemetry (accept/dismiss) ┘        │     └─ AMTSuggester (neural, lazy-loaded)
                                      ├── tutor: music21 facts → Claude (or template)
                                      └── telemetry + eval (acceptance, theory, benchmark)
```

A single WebSocket carries everything. The browser owns the real-time/UX
concerns (MIDI capture, notation, playback, key handling); the backend owns
musical intelligence (analysis, generation, explanation, evaluation).

## Key design decisions

**1. One `Suggester` interface, swappable implementations.**
`suggest(context, mode, style) -> [SuggestedNote]` is the only contract. The
rule-based suggester shipped first so the *entire* ghost-note loop was demoable
before any model existed; the neural model dropped in behind the same interface
without touching the WebSocket loop, telemetry, or eval. This also makes the
benchmark a fair apples-to-apples comparison.

**2. MIDI-first.** A MIDI keyboard emits exact pitch/timing, sidestepping
audio-transcription error. Audio input (Spotify `basic-pitch`) is a clean
future add-on behind the same note-event format.

**3. Lazy model loading + threadpool inference.** The 128M AMT model loads on the
*first* neural request, so the server boots instantly and the rule-based path
works with zero downloads. Generation is blocking (~10 s on MPS), so it runs via
`asyncio.to_thread` to keep the event loop responsive.

**4. Grounded tutor.** music21 computes the *facts* (key, the suggestion's chord
and roman numeral, scale degrees). Claude only *phrases* them. The same facts
drive a deterministic fallback, so the feature works with no API key and the
LLM can't hallucinate theory.

## Models

- **AMT (Anticipatory Music Transformer, `stanford-crfm/music-small-800k`,
  Apache-2.0).** GPT-2-style symbolic model supporting continuation *and*
  infilling-via-controls — so it powers both "continue" and "harmonize". Small
  and fast enough for interactive use on Apple Silicon.
- **Aria (`loubb/aria-medium-base`, Apache-2.0)** is a stronger piano-continuation
  model but its tokenizer (`ariautils`) requires Python ≥3.11, while the backend
  standardizes on 3.10 (for future `basic-pitch` audio support, which is
  3.10-only on Apple Silicon). Aria is therefore optional, gated behind a 3.11
  environment. *Honest constraint surfaced during the build, not papered over.*

## Evaluation

Three complementary views, all in `backend/eval/` and rendered to `REPORT.md`:

1. **Acceptance rate** (telemetry) — the Copilot-style headline: shown vs accepted,
   per mode/model, plus latency p50/p95.
2. **Theory-validity checks** — automated, human-free: in-key %, voice-leading
   smoothness, chord-tone ratio → a 0–1 score per suggestion.
3. **Offline continuation benchmark** — predict the next notes of held-out Bach
   chorale soprano lines (bundled in music21, zero data setup); score Note-F1,
   pitch-class similarity, rhythm, and theory.

Observed (8 chorales): AMT roughly doubles pitch-class similarity over the
baseline and lifts Note-F1 from 0 → ~0.12 (it imitates real continuations),
while the rule-based baseline scores higher on theory validity (it is strictly
diatonic by construction). Surfacing that **precision-vs-validity tradeoff** is
the reason both live behind one interface.

## Limitations & future work

- **Latency.** ~10 s for an AMT suggestion; acceptable for an on-demand button,
  not yet for keystroke-by-keystroke ghosting. Mitigations: shorter generation
  spans, KV-cache reuse, an MLX port, or a smaller distilled model.
- **Harmonization parsing** takes the first few accompaniment notes as a block
  chord; a smarter voicing/clef split would improve musical quality.
- **Aria** integration (3.11 env) and **audio input** (`basic-pitch`) are scoped
  but not built.
- **Public deploy** would need server-side model hosting (GPU) or a lighter
  cloud model; intentionally out of scope for the local flagship.

## Browser support

Web MIDI is Chrome/Edge/Firefox only — **Safari is unsupported** and the UI shows
a fallback notice. The "Demo melody" button feeds the same pipeline without a
keyboard, so the app is fully demoable on any supported browser.
