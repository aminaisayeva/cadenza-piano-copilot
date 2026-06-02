// VexFlow notation. Renders the player's committed notes plus optional grey
// "ghost notes" (the AI suggestion). Accepting (Tab) recolors them black upstream.

import { useEffect, useRef } from "react";
import {
  Renderer,
  Stave,
  StaveNote,
  Voice,
  Formatter,
  Accidental,
} from "vexflow";
import type { SuggestedNote } from "./ws";

const SHARP_NAMES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"];
const GHOST_COLOR = "#9aa0a6";

/** MIDI number -> VexFlow key like "c#/4", plus whether it needs an accidental. */
export function midiToVexKey(midi: number): { key: string; accidental: string | null } {
  const name = SHARP_NAMES[midi % 12];
  const octave = Math.floor(midi / 12) - 1;
  return { key: `${name}/${octave}`, accidental: name.includes("#") ? "#" : null };
}

function styled(n: StaveNote, color?: string): StaveNote {
  if (color) n.setStyle({ fillStyle: color, strokeStyle: color });
  return n;
}

function buildNote(midi: number, color?: string): StaveNote {
  const { key, accidental } = midiToVexKey(midi);
  const n = new StaveNote({ keys: [key], duration: "q" });
  if (accidental) n.addModifier(new Accidental("#"), 0);
  return styled(n, color);
}

function buildChord(midis: number[], color?: string): StaveNote {
  const sorted = [...midis].sort((a, b) => a - b);
  const keys = sorted.map((m) => midiToVexKey(m).key);
  const n = new StaveNote({ keys, duration: "q" });
  sorted.forEach((m, i) => {
    if (midiToVexKey(m).accidental) n.addModifier(new Accidental("#"), i);
  });
  return styled(n, color);
}

/** Turn a suggestion into grey StaveNotes: a chord if simultaneous, else a line. */
function buildGhost(ghost: SuggestedNote[]): StaveNote[] {
  if (ghost.length === 0) return [];
  const distinctStarts = new Set(ghost.map((g) => g.start));
  if (distinctStarts.size === 1) {
    return [buildChord(ghost.map((g) => g.note), GHOST_COLOR)];
  }
  return [...ghost]
    .sort((a, b) => a.start - b.start)
    .map((g) => buildNote(g.note, GHOST_COLOR));
}

export interface ScoreProps {
  notes: number[]; // committed player notes (MIDI numbers)
  ghost?: SuggestedNote[]; // pending AI suggestion, rendered grey
  width?: number;
  height?: number;
}

export function Score({ notes, ghost = [], width = 720, height = 180 }: ScoreProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.innerHTML = "";

    const renderer = new Renderer(el, Renderer.Backends.SVG);
    renderer.resize(width, height);
    const ctx = renderer.getContext();

    const stave = new Stave(10, 40, width - 20);
    stave.addClef("treble").addTimeSignature("4/4");
    stave.setContext(ctx).draw();

    const staveNotes = [...notes.map((m) => buildNote(m)), ...buildGhost(ghost)];
    if (staveNotes.length === 0) return;

    const voice = new Voice({ numBeats: staveNotes.length, beatValue: 4 });
    voice.setStrict(false);
    voice.addTickables(staveNotes);

    new Formatter().joinVoices([voice]).format([voice], width - 60);
    voice.draw(ctx, stave);
  }, [notes, ghost, width, height]);

  return <div ref={containerRef} />;
}
