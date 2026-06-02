// Phase 2: the copilot loop. Play -> request a suggestion -> grey ghost notes
// appear -> Tab accepts (commit + play + log), Esc dismisses (log). A live HUD
// shows the Copilot-style acceptance rate.

import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import { CadenzaSocket, type SuggestedNote, type SuggestMode } from "./ws";
import { enableMidi, isSupported, listen } from "./midi";
import { Score } from "./score";
import { initAudio, playSuggestion, playNote, playMelody, stopMelody } from "./playback";

// A short C-major phrase so the app is demoable without a physical keyboard.
const DEMO_MELODY = [60, 62, 64, 67, 65, 64, 62, 64];

// How many note-groups to keep on the staff (wraps across rows in the Score).
const MAX_LIVE = 32;

// Note-ons landing within this window are treated as one chord (struck together).
const CHORD_WINDOW_MS = 60;

interface Suggestion {
  id: string;
  mode: string;
  model: string;
  notes: SuggestedNote[];
  explanation?: string;
  latency_ms?: number;
}

const MODES: { mode: SuggestMode; label: string }[] = [
  { mode: "continue", label: "Continue ▸" },
  { mode: "harmonize", label: "Harmonize ⊕" },
  { mode: "reharmonize", label: "Reharmonize ↻" },
];

export default function App() {
  const socketRef = useRef<CadenzaSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [midiDevices, setMidiDevices] = useState<string[]>([]);
  const [midiError, setMidiError] = useState<string | null>(null);
  const [liveGroups, setLiveGroups] = useState<number[][]>([]);
  const [analysis, setAnalysis] = useState<{ key?: string; chord?: string; roman?: string } | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [stats, setStats] = useState({ shown: 0, accepted: 0 });
  const [model, setModel] = useState<"rule-based" | "amt">("rule-based");
  const [pending, setPending] = useState(false);

  // keep latest suggestion in a ref so the key handler isn't stale
  const suggestionRef = useRef<Suggestion | null>(null);
  suggestionRef.current = suggestion;

  // Buffer note-ons that arrive close together, then flush them as one chord.
  const chordBuf = useRef<number[]>([]);
  const chordTimer = useRef<number | null>(null);
  const flushChord = useCallback(() => {
    const group = [...chordBuf.current].sort((a, b) => a - b);
    chordBuf.current = [];
    chordTimer.current = null;
    if (group.length) setLiveGroups((prev) => [...prev, group].slice(-MAX_LIVE));
  }, []);
  const ingestNote = useCallback(
    (note: number) => {
      chordBuf.current.push(note);
      if (chordTimer.current == null) {
        chordTimer.current = window.setTimeout(flushChord, CHORD_WINDOW_MS);
      }
    },
    [flushChord],
  );

  useEffect(() => {
    const sock = new CadenzaSocket();
    socketRef.current = sock;
    sock.onStatusChange = setConnected;
    const off = sock.on((msg) => {
      if (msg.type === "analysis") {
        setAnalysis({ key: msg.key, chord: msg.chord, roman: msg.roman });
      } else if (msg.type === "suggestion") {
        setPending(false);
        if (msg.notes.length > 0) {
          setSuggestion(msg);
          setStats((s) => ({ ...s, shown: s.shown + 1 }));
        }
      }
    });
    sock.connect();
    return off;
  }, []);

  async function handleEnableMidi() {
    try {
      await initAudio();
      const devices = await enableMidi();
      setMidiDevices(devices);
      setMidiError(null);
      listen({
        onNoteOn: (e) => {
          ingestNote(e.note); // grouped into a chord if struck with others
          socketRef.current?.send({ type: "note_on", note: e.note, velocity: e.velocity, time: e.time });
        },
        onNoteOff: (e) => socketRef.current?.send({ type: "note_off", note: e.note, time: e.time }),
      });
    } catch (err) {
      setMidiError(err instanceof Error ? err.message : String(err));
    }
  }

  function requestSuggestion(mode: SuggestMode) {
    setPending(true);
    socketRef.current?.send({ type: "request_suggestion", mode, model });
  }

  // Play a canned phrase — feeds the same path as real MIDI input so you can
  // demo the copilot (and record a video) without a keyboard.
  async function playDemoMelody() {
    await initAudio();
    setLiveGroups([]);
    setSuggestion(null);
    DEMO_MELODY.forEach((note, i) => {
      setTimeout(() => {
        setLiveGroups((prev) => [...prev, [note]].slice(-MAX_LIVE));
        socketRef.current?.send({ type: "note_on", note, velocity: 90, time: i });
        void playNote(note);
      }, i * 450);
    });
  }

  const accept = useCallback(() => {
    const s = suggestionRef.current;
    if (!s) return;
    void playSuggestion(s.notes);
    // commit the accepted suggestion onto the staff: a melodic line becomes one
    // group per note; a simultaneous suggestion (harmonize) becomes one chord.
    const distinctStarts = new Set(s.notes.map((n) => n.start));
    const groups: number[][] =
      distinctStarts.size > 1
        ? s.notes.map((n) => [n.note])
        : [s.notes.map((n) => n.note)];
    setLiveGroups((prev) => [...prev, ...groups].slice(-MAX_LIVE));
    socketRef.current?.send({ type: "decision", suggestion_id: s.id, accepted: true });
    setStats((st) => ({ ...st, accepted: st.accepted + 1 }));
    setSuggestion(null);
  }, []);

  const dismiss = useCallback(() => {
    const s = suggestionRef.current;
    if (!s) return;
    socketRef.current?.send({ type: "decision", suggestion_id: s.id, accepted: false });
    setSuggestion(null);
  }, []);

  // Tab accepts, Esc dismisses (only while a suggestion is showing).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!suggestionRef.current) return;
      if (e.key === "Tab") {
        e.preventDefault();
        accept();
      } else if (e.key === "Escape") {
        e.preventDefault();
        dismiss();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [accept, dismiss]);

  const rate = stats.shown ? Math.round((stats.accepted / stats.shown) * 100) : 0;

  return (
    <div className="app">
      <header>
        <h1>🎹 Cadenza</h1>
        <p className="tagline">GitHub Copilot, but for composing at the piano.</p>
      </header>

      <section className="status-bar">
        <span className={connected ? "pill ok" : "pill bad"}>
          {connected ? "● backend connected" : "○ backend offline"}
        </span>
        <span className={isSupported() ? "pill ok" : "pill bad"}>
          {isSupported() ? "● Web MIDI" : "○ Web MIDI unsupported (use Chrome)"}
        </span>
        <span className="pill">accept rate: {rate}% ({stats.accepted}/{stats.shown})</span>
      </section>

      <section className="card">
        <h2>Score</h2>
        <p className="hint">
          Your notes in black; AI suggestions appear as grey <em>ghost notes</em> —
          press <kbd>Tab</kbd> to accept, <kbd>Esc</kbd> to dismiss.
        </p>
        <Score notes={liveGroups} ghost={suggestion?.notes ?? []} />
        <div className="modes">
          <button onClick={() => playMelody(liveGroups)} disabled={liveGroups.length === 0}>
            ▶ Run
          </button>
          <button className="ghost-btn" onClick={() => stopMelody()}>■ Stop</button>
          <button
            className="ghost-btn"
            onClick={() => {
              stopMelody();
              chordBuf.current = [];
              setLiveGroups([]);
              setSuggestion(null);
            }}
            disabled={liveGroups.length === 0}
          >
            Clear
          </button>
        </div>
        <div className="modes">
          <label className="model-select">
            model:
            <select value={model} onChange={(e) => setModel(e.target.value as "rule-based" | "amt")}>
              <option value="rule-based">rule-based (instant)</option>
              <option value="amt">AMT (neural, ~10s)</option>
            </select>
          </label>
          {MODES.map(({ mode, label }) => (
            <button
              key={mode}
              onClick={() => requestSuggestion(mode)}
              disabled={!connected || pending}
            >
              {label}
            </button>
          ))}
          {suggestion && (
            <>
              <button className="accept" onClick={accept}>Accept (Tab)</button>
              <button className="ghost-btn" onClick={dismiss}>Dismiss (Esc)</button>
            </>
          )}
        </div>
        {pending && <p className="hint">🎼 thinking… (neural model generating)</p>}
        {suggestion?.latency_ms != null && (
          <p className="hint">
            {suggestion.model} · {suggestion.mode} · {suggestion.latency_ms} ms
          </p>
        )}
        {suggestion?.explanation && <p className="explanation">💡 {suggestion.explanation}</p>}
      </section>

      <section className="card">
        <h2>Harmony</h2>
        <p className="hint">Live analysis from music21 as you play.</p>
        <div className="hud">
          <div className="hud-item">
            <span className="hud-label">Key</span>
            <span className="hud-value">{analysis?.key ?? "—"}</span>
          </div>
          <div className="hud-item">
            <span className="hud-label">Chord</span>
            <span className="hud-value">{analysis?.chord ?? "—"}</span>
          </div>
          <div className="hud-item">
            <span className="hud-label">Roman</span>
            <span className="hud-value">{analysis?.roman ?? "—"}</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>MIDI</h2>
        <div className="modes">
          <button onClick={handleEnableMidi} disabled={!isSupported()}>Enable MIDI keyboard</button>
          <button className="ghost-btn" onClick={playDemoMelody} disabled={!connected}>
            ▶ Demo melody (no keyboard)
          </button>
        </div>
        {midiError && <p className="error">{midiError}</p>}
        {midiDevices.length > 0 && (
          <ul className="devices">
            {midiDevices.map((d) => (<li key={d}>🎛️ {d}</li>))}
          </ul>
        )}
      </section>
    </div>
  );
}
