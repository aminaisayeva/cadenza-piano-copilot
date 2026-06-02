# Recording a Cadenza demo

A tight 60–90s video is the highest-leverage artifact for the resume. Here's a
script that shows ML depth, the Copilot UX, and the rigor — in that order.

## Setup

1. **Two terminals:**
   ```bash
   # terminal 1
   cd backend && ./.venv/bin/python -m uvicorn app.main:app --reload --port 8200
   # terminal 2
   cd frontend && npm run dev
   ```
2. Open the app in **Chrome** (full-screen, hide bookmarks bar).
3. Optional: `cp backend/.env.example backend/.env` and add your
   `ANTHROPIC_API_KEY` so the tutor shows natural-language coaching.
4. Optional but better: connect a MIDI keyboard and click **Enable MIDI
   keyboard**. No keyboard? Use the **▶ Demo melody** button — it drives the
   exact same pipeline.

## Script (what to show, in order)

1. **(0:00) Hook.** Title on screen / say it: *"It's GitHub Copilot, but for
   composing at the piano."*
2. **(0:08) Play.** Play a short phrase (or click **▶ Demo melody**). Point out
   the **Harmony HUD** updating live — key, chord, roman numeral — *"this is
   music21 analyzing what I play in real time."*
3. **(0:20) Rule-based ghost notes.** Model = `rule-based`. Click **Continue** →
   grey ghost notes appear instantly. Press **`Tab`** → they turn black and you
   *hear* them. *"Tab to accept, just like Copilot."*
4. **(0:35) The neural model.** Switch model to **AMT**. Click **Continue** →
   show the "thinking…" state, then a musically richer suggestion. *"This one's
   a 128M-parameter transformer from Stanford running locally on my Mac."*
5. **(0:50) Harmonize + tutor.** Click **Harmonize** → a chord appears under the
   melody, and the tutor explains *why* (key / roman numeral). *"It teaches the
   theory, not just autocompletes."*
6. **(1:05) Rigor.** Cut to `eval/REPORT.md` (or a terminal running
   `CADENZA_BENCH_AMT=1 python -m eval.report`). Show the table: *"I measure it —
   acceptance rate, automated theory checks, and an offline benchmark on Bach
   chorales where the neural model beats the baseline on predictive accuracy."*
7. **(1:20) Close.** Show the accept-rate HUD ticking up. One line on the stack
   (React + FastAPI + music21 + a transformer behind one swappable interface).

## Capture tips

- macOS screen record: `Cmd+Shift+5`. Record system audio so the piano is heard.
- Keep the cursor deliberate; pause ~1s after each ghost-note appears so viewers
  register the grey→black accept.
- Export 1080p; trim dead air. Put the final GIF/MP4 link at the top of the
  README.
