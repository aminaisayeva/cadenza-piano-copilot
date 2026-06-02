// Turns played notes (with real onsets + durations, in beats) into engraved
// measures: standard note values, 4/4 bars, and rests only where a hand is
// actually silent. Pure + framework-free so it can be unit-tested in isolation.

export interface PlayedNote {
  note: number; // MIDI number
  onset: number; // beats from the start of the piece
  dur: number; // length in beats
  ghost?: boolean; // true for not-yet-accepted AI suggestions
}

export type Clef = "treble" | "bass";

export interface NElement {
  kind: "note" | "rest";
  code: string; // VexFlow duration code: "w" | "h" | "q" | "8" | "16"
  dots: number;
  beats: number;
  notes: number[]; // MIDI numbers (empty for rests)
  ghost: boolean;
}

export const GRID = 0.25; // quantize to 16th notes
export const MEASURE_BEATS = 4; // 4/4
export const SPLIT = 60; // middle C: >= treble (right hand), < bass (left hand)
const MAX_REST_BEATS = MEASURE_BEATS; // never draw silences longer than one bar

// Standard note values in beats, largest first (for greedy decomposition).
const DURS: { beats: number; code: string; dots: number }[] = [
  { beats: 4, code: "w", dots: 0 },
  { beats: 3, code: "h", dots: 1 },
  { beats: 2, code: "h", dots: 0 },
  { beats: 1.5, code: "q", dots: 1 },
  { beats: 1, code: "q", dots: 0 },
  { beats: 0.75, code: "8", dots: 1 },
  { beats: 0.5, code: "8", dots: 0 },
  { beats: 0.25, code: "16", dots: 0 },
];

const q = (x: number) => Math.round(x / GRID) * GRID;

/** Break a span (beats, grid-aligned) into standard note values that sum to it. */
export function decompose(beats: number): { beats: number; code: string; dots: number }[] {
  const out: { beats: number; code: string; dots: number }[] = [];
  let rem = q(beats);
  for (const d of DURS) {
    while (rem >= d.beats - 1e-9) {
      out.push(d);
      rem = +(rem - d.beats).toFixed(3);
    }
  }
  return out;
}

interface Event {
  onset: number;
  dur: number;
  notes: number[];
  ghost: boolean;
}

// Notes struck within this window (beats; ~35ms @120bpm) form a chord. Anything
// further apart is sequential — so fast runs don't pile up as chords.
export const CHORD_EPS = 0.07;

function toEvents(notes: PlayedNote[]): Event[] {
  const sorted = [...notes].sort((a, b) => a.onset - b.onset);
  const events: (Event & { raw: number })[] = [];
  let placedPrev = -Infinity;
  for (const n of sorted) {
    const dur = Math.max(GRID, q(n.dur));
    const last = events[events.length - 1];
    if (last && n.onset - last.raw <= CHORD_EPS) {
      // close enough to the chord's first note -> stack it
      last.notes.push(n.note);
      last.dur = Math.max(last.dur, dur);
      last.ghost = last.ghost || !!n.ghost;
    } else {
      // place on the grid, but never on top of the previous event
      let placed = q(n.onset);
      if (placed <= placedPrev + 1e-9) placed = placedPrev + GRID;
      events.push({ onset: placed, dur, notes: [n.note], ghost: !!n.ghost, raw: n.onset });
      placedPrev = placed;
    }
  }
  return events.map(({ raw: _raw, ...e }) => e);
}

/** Lay out one clef's notes into measures (each summing to MEASURE_BEATS). */
export function layoutClef(notes: PlayedNote[], totalBeats: number): NElement[][] {
  const events = toEvents(notes);

  // 1. flat timeline: notes truncated to the next onset (monophonic per clef),
  //    with rests filling the gaps (clamped so silences never exceed a bar).
  type Span = { kind: "note" | "rest"; start: number; dur: number; notes: number[]; ghost: boolean };
  const flat: Span[] = [];
  let pos = 0;
  for (let i = 0; i < events.length; i++) {
    const ev = events[i];
    if (ev.onset > pos + 1e-9) {
      flat.push({ kind: "rest", start: pos, dur: Math.min(ev.onset - pos, MAX_REST_BEATS), notes: [], ghost: false });
      pos = ev.onset;
    }
    const next = i + 1 < events.length ? events[i + 1].onset : Infinity;
    let dur = Math.min(ev.dur, next - ev.onset); // truncate overlaps
    if (dur < GRID) dur = GRID;
    flat.push({ kind: "note", start: ev.onset, dur, notes: ev.notes, ghost: ev.ghost });
    pos = ev.onset + dur;
  }

  // 2. tile into measures, splitting any span that crosses a barline.
  const bars = Math.max(1, Math.ceil(Math.max(totalBeats, pos) / MEASURE_BEATS - 1e-9));
  const measures: NElement[][] = Array.from({ length: bars }, () => []);
  const push = (m: number, kind: "note" | "rest", piece: { beats: number; code: string; dots: number }, notes: number[], ghost: boolean) =>
    measures[m].push({ kind, code: piece.code, dots: piece.dots, beats: piece.beats, notes, ghost });

  for (const span of flat) {
    let s = span.start;
    let remaining = span.dur;
    while (remaining > 1e-9) {
      const m = Math.floor(s / MEASURE_BEATS + 1e-9);
      const chunk = Math.min(remaining, (m + 1) * MEASURE_BEATS - s);
      for (const piece of decompose(chunk)) push(m, span.kind, piece, span.notes, span.ghost);
      s += chunk;
      remaining -= chunk;
    }
  }

  // 3. pad each measure to exactly MEASURE_BEATS with trailing rests.
  for (const measure of measures) {
    const sum = measure.reduce((a, e) => a + e.beats, 0);
    const deficit = +(MEASURE_BEATS - sum).toFixed(3);
    if (deficit > 1e-9) {
      for (const piece of decompose(deficit)) measure.push({ kind: "rest", code: piece.code, dots: piece.dots, beats: piece.beats, notes: [], ghost: false });
    }
  }
  return measures;
}

/** Split all notes into treble/bass measures aligned to the same bar grid. */
export function layout(notes: PlayedNote[]): { treble: NElement[][]; bass: NElement[][] } {
  if (notes.length === 0) {
    const empty = layoutClef([], MEASURE_BEATS);
    return { treble: empty, bass: layoutClef([], MEASURE_BEATS) };
  }
  // rebase so the first note starts at beat 0
  const minOnset = Math.min(...notes.map((n) => n.onset));
  const based = notes.map((n) => ({ ...n, onset: n.onset - minOnset }));
  const totalBeats = Math.max(...based.map((n) => q(n.onset) + Math.max(GRID, q(n.dur))));
  return {
    treble: layoutClef(based.filter((n) => n.note >= SPLIT), totalBeats),
    bass: layoutClef(based.filter((n) => n.note < SPLIT), totalBeats),
  };
}
