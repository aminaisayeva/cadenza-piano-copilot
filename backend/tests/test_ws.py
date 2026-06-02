"""Phase 0 smoke tests: the app boots and the WebSocket echoes."""

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_ws_unknown_type_acks():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text('{"type": "ping"}')
        reply = ws.receive_json()
        assert reply["type"] == "ack"
        assert reply["echo"]["type"] == "ping"


def test_ws_note_on_returns_analysis():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        # Play a C major triad; the third note (held) should yield a chord.
        for n in (60, 64, 67):
            ws.send_text(f'{{"type": "note_on", "note": {n}, "velocity": 100, "time": 0.0}}')
            reply = ws.receive_json()
            assert reply["type"] == "analysis"
        assert reply["chord"] is not None


def test_ws_request_suggestion_returns_notes():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        for n in (60, 62, 64, 65):
            ws.send_text(f'{{"type": "note_on", "note": {n}, "velocity": 90, "time": 0.0}}')
            ws.receive_json()  # drain analysis
        ws.send_text('{"type": "request_suggestion", "mode": "continue"}')
        reply = ws.receive_json()
        assert reply["type"] == "suggestion"
        assert reply["model"] == "rule-based"
        assert len(reply["notes"]) >= 1
        assert "id" in reply and "latency_ms" in reply
