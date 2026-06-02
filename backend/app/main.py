"""Cadenza FastAPI app.

Phase 0: a /ws echo endpoint + /health, enough to prove the browser <-> backend
pipe works end to end. Later phases attach the understanding, suggestion, tutor,
and telemetry layers onto the same WebSocket loop.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # picks up backend/.env (e.g. ANTHROPIC_API_KEY) if present

from . import __version__, telemetry, tutor
from .suggesters import RuleBasedSuggester, SuggestionContext
from .suggesters.amt import AMTSuggester
from .understanding import Session

# Suggesters share across connections. AMT lazy-loads its model on first use, so
# constructing it here is cheap and the server still starts instantly.
SUGGESTERS = {"rule-based": RuleBasedSuggester(), "amt": AMTSuggester()}
DEFAULT_SUGGESTER = "rule-based"

app = FastAPI(title="Cadenza — Piano Copilot", version=__version__)

# Vite dev server may land on any free port (5173, 5174, ...); allow any localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    """Main connection loop.

    Phase 1: MIDI note events update a per-connection `Session`, and each event
    yields a live `analysis` (key / chord / roman numeral) sent back to the
    client. Unknown message types still get an `ack` (keeps Phase 0 behavior).
    """
    await websocket.accept()
    session = Session()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                msg = {"raw": raw}

            mtype = msg.get("type")
            if mtype == "note_on":
                result = session.note_on(int(msg["note"]))
                await websocket.send_json(result.as_message())
            elif mtype == "note_off":
                result = session.note_off(int(msg["note"]))
                await websocket.send_json(result.as_message())
            elif mtype == "request_suggestion":
                await _handle_suggestion(websocket, session, msg)
            elif mtype == "decision":
                telemetry.log_decision(msg["suggestion_id"], bool(msg["accepted"]))
            else:
                await websocket.send_json({"type": "ack", "echo": msg})
    except WebSocketDisconnect:
        return


async def _handle_suggestion(websocket: WebSocket, session: Session, msg: dict) -> None:
    """Run a suggester and emit a `suggestion` message; log it for the eval layer."""
    mode = msg.get("mode", "continue")
    style = msg.get("style")
    model = msg.get("model", DEFAULT_SUGGESTER)
    suggester = SUGGESTERS.get(model, SUGGESTERS[DEFAULT_SUGGESTER])

    analysis = session.analyze()
    ctx = SuggestionContext(
        history=list(session.history), held=sorted(session.held), key=analysis.key
    )

    # Model inference can block for seconds (AMT); run it off the event loop so
    # the server stays responsive to other clients/messages.
    t0 = time.perf_counter()
    notes = await asyncio.to_thread(suggester.suggest, ctx, mode, style)
    latency_ms = (time.perf_counter() - t0) * 1000

    explanation = None
    if notes:
        explanation = await asyncio.to_thread(
            tutor.explain, analysis.key, [n.note for n in notes], mode
        )

    suggestion_id = uuid.uuid4().hex
    telemetry.log_suggestion(suggestion_id, mode, suggester.name, latency_ms, len(notes))

    await websocket.send_json(
        {
            "type": "suggestion",
            "id": suggestion_id,
            "mode": mode,
            "model": suggester.name,
            "notes": [n.as_dict() for n in notes],
            "explanation": explanation,
            "latency_ms": round(latency_ms, 2),
        }
    )
