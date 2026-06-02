// VexFlow grand-staff notation. Each "beat" (a group of simultaneously struck
// notes) is split by pitch into the treble (right hand) and bass (left hand)
// clefs; chords stack on whichever hand played them. AI suggestions render as
// grey "ghost notes" appended after the player's input.

import { useEffect, useRef } from "react";
import {
  Renderer,
  Stave,
  StaveNote,
  StaveConnector,
  Voice,
  Formatter,
  Accidental,
} from "vexflow";
import type { SuggestedNote } from "./ws";

const SHARP_NAMES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"];
const GHOST_COLOR = "#9aa0a6";
const MIDDLE_C = 60; // split point: >= treble (right hand), < bass (left hand)

type Clef = "treble" | "bass";

interface Beat {
  treble: number[];
  bass: number[];
  ghost: boolean;
}

/** MIDI number -> VexFlow key like "c#/4", plus whether it needs an accidental. */
export function midiToVexKey(midi: number): { key: string; accidental: string | null } {
  const name = SHARP_NAMES[midi % 12];
  const octave = Math.floor(midi / 12) - 1;
  return { key: `${name}/${octave}`, accidental: name.includes("#") ? "#" : null };
}

function noteFor(midis: number[], clef: Clef, color?: string): StaveNote {
  const sorted = [...midis].sort((a, b) => a - b);
  const n = new StaveNote({ keys: sorted.map((m) => midiToVexKey(m).key), duration: "q", clef });
  sorted.forEach((m, i) => {
    if (midiToVexKey(m).accidental) n.addModifier(new Accidental("#"), i);
  });
  if (color) n.setStyle({ fillStyle: color, strokeStyle: color });
  return n;
}

function restFor(clef: Clef): StaveNote {
  return new StaveNote({ keys: [clef === "treble" ? "b/4" : "d/3"], duration: "qr", clef });
}

/** One tickable per beat per clef (a note/chord, or a rest to keep voices aligned). */
function tickable(beat: Beat, clef: Clef): StaveNote {
  const notes = clef === "treble" ? beat.treble : beat.bass;
  return notes.length ? noteFor(notes, clef, beat.ghost ? GHOST_COLOR : undefined) : restFor(clef);
}

function splitBeat(notes: number[], ghost: boolean): Beat {
  return {
    treble: notes.filter((m) => m >= MIDDLE_C),
    bass: notes.filter((m) => m < MIDDLE_C),
    ghost,
  };
}

/** Group a suggestion's notes by onset into ghost beats (chord if simultaneous). */
function ghostBeats(ghost: SuggestedNote[]): Beat[] {
  const byStart = new Map<number, number[]>();
  for (const s of ghost) byStart.set(s.start, [...(byStart.get(s.start) ?? []), s.note]);
  return [...byStart.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, notes]) => splitBeat(notes, true));
}

export interface ScoreProps {
  // committed input as groups: each group is one beat — a single note, or a
  // chord when several keys were struck at the same time, across both hands.
  notes: number[][];
  ghost?: SuggestedNote[];
  width?: number;
  notesPerRow?: number;
}

const ROW_HEIGHT = 180;
const STAFF_GAP = 80; // treble -> bass vertical offset within a row
const TOP_PAD = 10;

export function Score({ notes, ghost = [], width = 720, notesPerRow = 8 }: ScoreProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.innerHTML = "";

    const beats: Beat[] = [
      ...notes.map((g) => splitBeat(g, false)),
      ...ghostBeats(ghost),
    ];

    const rows: Beat[][] = [];
    for (let i = 0; i < beats.length; i += notesPerRow) rows.push(beats.slice(i, i + notesPerRow));
    if (rows.length === 0) rows.push([]); // always show an empty grand staff

    const renderer = new Renderer(el, Renderer.Backends.SVG);
    renderer.resize(width, rows.length * ROW_HEIGHT + TOP_PAD);
    const ctx = renderer.getContext();

    rows.forEach((row, idx) => {
      const trebleY = TOP_PAD + idx * ROW_HEIGHT;
      const bassY = trebleY + STAFF_GAP;

      const treble = new Stave(10, trebleY, width - 20);
      const bass = new Stave(10, bassY, width - 20);
      treble.addClef("treble");
      bass.addClef("bass");
      if (idx === 0) {
        treble.addTimeSignature("4/4");
        bass.addTimeSignature("4/4");
      }
      treble.setContext(ctx).draw();
      bass.setContext(ctx).draw();
      // brace + left barline join the two staves into a grand staff
      new StaveConnector(treble, bass).setType(StaveConnector.type.BRACE).setContext(ctx).draw();
      new StaveConnector(treble, bass).setType(StaveConnector.type.SINGLE_LEFT).setContext(ctx).draw();

      if (row.length === 0) return;
      const tv = new Voice({ numBeats: row.length, beatValue: 4 }).setStrict(false);
      const bv = new Voice({ numBeats: row.length, beatValue: 4 }).setStrict(false);
      tv.addTickables(row.map((b) => tickable(b, "treble")));
      bv.addTickables(row.map((b) => tickable(b, "bass")));
      new Formatter().joinVoices([tv, bv]).format([tv, bv], width - 90);
      tv.draw(ctx, treble);
      bv.draw(ctx, bass);
    });
  }, [notes, ghost, width, notesPerRow]);

  return <div ref={containerRef} />;
}
