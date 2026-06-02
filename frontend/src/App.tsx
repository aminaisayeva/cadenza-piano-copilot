// The copilot loop: play -> request a suggestion -> grey ghost notes appear ->
// Tab accepts (commit + play + log), Esc dismisses. A live HUD shows the
// Copilot-style acceptance rate. Played notes carry real durations so the score
// engraves proper note values, bars, and rests (see ./notation).

import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import { CadenzaSocket, type SuggestedNote, type SuggestMode } from "./ws";
import { enableMidi, isSupported, listen } from "./midi";
import { Score } from "./score";
import type { PlayedNote } from "./notation";
import { initAudio, playSuggestion, playNote, playPerformance, stopMelody } from "./playback";

// A short C-major phrase (quarter notes) so the app is demoable without hardware.
const DEMO_MELODY = [60, 62, 64, 67, 65, 64, 62, 64];

const MAX_EVENTS = 64; // bound how much of the performance we keep on the staff
const BEAT_MS = 500; // 120 bpm: maps held time -> note value
const GRID = 0.25;

type LiveNote = PlayedNote & { id: number };

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
  const [events, setEvents] = useState<LiveNote[]>([]);
  const [analysis, setAnalysis] = useState<{ key?: string; chord?: string; roman?: string } | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [stats, setStats] = useState({ shown: 0, accepted: 0 });
  const [model, setModel] = useState<"rule-based" | "amt">("rule-based");
  const [pending, setPending] = useState(false);

  const suggestionRef = useRef<Suggestion | null>(null);
  suggestionRef.current = suggestion;

  // Timing state for turning live note on/off into onsets + durations (in beats).
  const startMs = useRef<number | null>(null);
  const active = useRef<Map<number, number>>(new Map()); // midi -> event id
  const nextId = useRef(0);

  const resetPerformance = useCallback(() => {
    startMs.current = null;
    active.current.clear();
    setEvents([]);
    setSuggestion(null);
  }, []);

  const onNoteOn = useCallback((note: number, timeSec: number) => {
    const tMs = timeSec * 1000;
    if (startMs.current === null) startMs.current = tMs;
    const onset = (tMs - startMs.current) / BEAT_MS;
    const id = nextId.current++;
    active.current.set(note, id);
    // provisional quarter until the key is released
    setEvents((prev) => [...prev, { id, note, onset, dur: 1 }].slice(-MAX_EVENTS));
  }, []);

  const onNoteOff = useCallback((note: number, timeSec: number) => {
    const id = active.current.get(note);
    if (id === undefined) return;
    active.current.delete(note);
    const start = startMs.current ?? timeSec * 1000;
    const end = (timeSec * 1000 - start) / BEAT_MS;
    setEvents((prev) =>
      prev.map((ev) => (ev.id === id ? { ...ev, dur: Math.max(GRID, end - ev.onset) } : ev)),
    );
  }, []);

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
          onNoteOn(e.note, e.time);
          socketRef.current?.send({ type: "note_on", note: e.note, velocity: e.velocity, time: e.time });
        },
        onNoteOff: (e) => {
          onNoteOff(e.note, e.time);
          socketRef.current?.send({ type: "note_off", note: e.note, time: e.time });
        },
      });
    } catch (err) {
      setMidiError(err instanceof Error ? err.message : String(err));
    }
  }

  function requestSuggestion(mode: SuggestMode) {
    setPending(true);
    socketRef.current?.send({ type: "request_suggestion", mode, model });
  }

  // Canned phrase — feeds the same path as real input so you can demo (or record)
  // without a keyboard. Each note is a quarter, so it engraves as two 4/4 bars.
  async function playDemoMelody() {
    await initAudio();
    resetPerformance();
    DEMO_MELODY.forEach((note, i) => {
      setTimeout(() => {
        const id = nextId.current++;
        setEvents((prev) => [...prev, { id, note, onset: i, dur: 1 }].slice(-MAX_EVENTS));
        socketRef.current?.send({ type: "note_on", note, velocity: 90, time: i });
        void playNote(note);
      }, i * 450);
    });
  }

  const accept = useCallback(() => {
    const s = suggestionRef.current;
    if (!s) return;
    void playSuggestion(s.notes);
    setEvents((prev) => {
      const base = prev.length ? Math.max(...prev.map((e) => e.onset + e.dur)) : 0;
      const add = s.notes.map((n) => ({
        id: nextId.current++,
        note: n.note,
        onset: base + n.start,
        dur: n.duration,
      }));
      return [...prev, ...add].slice(-MAX_EVENTS);
    });
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

  // Position the pending suggestion right after the played notes, as grey ghosts.
  const base = events.length ? Math.max(...events.map((e) => e.onset + e.dur)) : 0;
  const ghostEvents: PlayedNote[] = suggestion
    ? suggestion.notes.map((n) => ({ note: n.note, onset: base + n.start, dur: n.duration, ghost: true }))
    : [];
  const allEvents: PlayedNote[] = [...events, ...ghostEvents];

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
          Right hand on the treble staff, left hand on the bass; AI suggestions
          appear as grey <em>ghost notes</em> — <kbd>Tab</kbd> to accept, <kbd>Esc</kbd> to dismiss.
        </p>
        <Score events={allEvents} />
        <div className="modes">
          <button onClick={() => playPerformance(events)} disabled={events.length === 0}>
            ▶ Run
          </button>
          <button className="ghost-btn" onClick={() => stopMelody()}>■ Stop</button>
          <button
            className="ghost-btn"
            onClick={() => {
              stopMelody();
              resetPerformance();
            }}
            disabled={events.length === 0}
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
