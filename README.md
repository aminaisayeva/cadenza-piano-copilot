# 🎹 Cadenza — a Piano Copilot

**GitHub Copilot, but for composing at the piano.** Play a MIDI keyboard and
Cadenza understands your harmony and melody in real time, renders live sheet
music, and suggests how to continue — as greyed-in **ghost notes** you accept
with `Tab`. It also **explains the music theory** behind each suggestion (so it
teaches composition) and ships with an **evaluation layer** that measures
suggestion quality.

![demo](docs/demo.gif) <!-- add a recording here; see DEMO.md -->

- **Live harmony analysis** — key, chord, and roman numeral as you play (music21).
- **Ghost-note suggestions** — `Tab` to accept, `Esc` to dismiss; continue,
  harmonize, or reharmonize.
- **Two engines behind one interface** — an instant rule-based baseline and a
  128M-parameter neural model (Anticipatory Music Transformer) running locally.
- **Theory tutor** — explains why each suggestion works (music21 + Claude, with
  an offline fallback).
- **Evaluation** — acceptance rate, automated theory-validity checks, and an
  offline Bach-chorale benchmark.

---

## Quick start

**Prerequisites:** Python **3.10**, Node **18+**, and Chrome or Edge (Web MIDI is
not supported in Safari). A MIDI keyboard is optional — there's a built-in demo.

```bash
git clone https://github.com/aminaisayeva/cadenza-piano-copilot.git
cd cadenza-piano-copilot
```

**Fastest path:** `./start.sh` sets up anything missing, starts both servers, and
opens the app in your browser (Ctrl+C to stop). Or follow the manual steps below.

### 1. Backend

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Enable the neural model (Anticipatory Music Transformer; optional but recommended).
# It has no PyPI release, and --no-deps protects the modern transformers above:
pip install --no-deps git+https://github.com/jthickstun/anticipation.git

# (optional) natural-language theory tutor via Claude:
cp .env.example .env   # then paste your ANTHROPIC_API_KEY

uvicorn app.main:app --reload --port 8200
```

> Cadenza uses port **8200** (8000 is often taken by other local apps). If you
> change it, update `ws://localhost:8200/ws` in `frontend/src/ws.ts`.

### 2. Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev          # opens http://localhost:5173 (or the next free port)
```

### 3. Use it

Open the app in **Chrome or Edge**, then:

1. Click **Enable MIDI keyboard** and play — or click **▶ Demo melody** to drive
   it with no hardware.
2. Watch the **Harmony** panel update (key / chord / roman numeral).
3. Pick a **model** (`rule-based` is instant; `AMT` is neural, ~10 s) and a mode:
   **Continue**, **Harmonize**, or **Reharmonize**.
4. Grey **ghost notes** appear — press **`Tab`** to accept (and hear them) or
   **`Esc`** to dismiss. The tutor explains the theory; the HUD tracks your
   acceptance rate.

---

## How it works

```
Browser (Chrome/Edge)                    Python backend (FastAPI)
  WebMidi.js  ──notes──┐         ┌── understanding (music21): key / chord / roman
  VexFlow (ghost notes)├── WS ───┤── Suggester interface
  Tone.js + smplr      │         │     ├─ rule-based (diatonic, instant)
  acceptance telemetry ┘         │     └─ AMT (neural, lazy-loaded)
                                 ├── theory tutor (music21 → Claude / fallback)
                                 └── telemetry + evaluation
```

The whole app runs over one WebSocket. The browser owns real-time UX (MIDI,
notation, playback); the backend owns musical intelligence. Suggestion models are
swappable behind a single `Suggester` interface. See [DESIGN.md](DESIGN.md) for
the rationale and tradeoffs.

### Tech stack

| Layer | Library | License |
|---|---|---|
| MIDI input | WebMidi.js | Apache-2.0 |
| Notation | VexFlow 5 | MIT |
| Playback | Tone.js + smplr | MIT |
| Backend | FastAPI + uvicorn | MIT |
| Understanding | music21 | BSD-3 |
| Generation | Anticipatory Music Transformer (+ rule-based) | Apache-2.0 |
| Theory tutor | music21 + Claude API | — |

### Models

| Model | Modes | Speed |
|---|---|---|
| `rule-based` | continue / harmonize / reharmonize | instant |
| `amt` (128M, Apache-2.0) | continue / harmonize | ~10 s on Apple Silicon (MPS) |

The neural model downloads on first request (not at startup), so the app always
boots instantly and the rule-based path works fully offline. (A larger model,
Aria, is supported in principle but needs Python ≥3.11 — see DESIGN.md.)

---

## Tests & evaluation

```bash
# backend (30 tests; model + Claude tests auto-skip)
cd backend && source .venv/bin/activate && pytest -q

# frontend typecheck + bundle
cd frontend && npm run build

# evaluation report -> backend/eval/REPORT.md
cd backend && CADENZA_BENCH_AMT=1 python -m eval.report

# opt-in slow model test
cd backend && CADENZA_RUN_MODEL_TESTS=1 pytest tests/test_amt.py
```

Benchmark snapshot (8 Bach chorales, predict the next 4 notes):

| Model | Note F1 | Pitch-class cos | Theory |
|---|---|---|---|
| rule-based | 0.000 | 0.221 | 0.875 |
| amt | 0.121 | 0.347 | 0.632 |

AMT imitates real continuations (higher F1 / pitch-class similarity); the
rule-based baseline is strictly diatonic, so it scores higher on theory validity.

## Project structure

```
cadenza/
├── backend/          FastAPI app, suggesters, theory tutor, eval harness
│   ├── app/          main.py · understanding.py · suggesters/ · tutor.py · ...
│   └── eval/         metrics · theory_checks · benchmark · report
├── frontend/         React + TypeScript (Vite)
│   └── src/          App.tsx · score.tsx · midi.ts · playback.ts · ws.ts
├── DESIGN.md         architecture & decisions
└── DEMO.md           how to record a demo
```

## License

MIT for the application code. Pretrained models retain their own licenses (AMT is
Apache-2.0).
