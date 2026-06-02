// VexFlow grand-staff notation. Played notes (with real durations) are laid out
// by ./notation into 4/4 measures per hand — proper note values, bar lines, and
// rests only where a hand is silent. AI suggestions render as grey ghost notes.

import { useEffect, useRef } from "react";
import {
  Renderer,
  Stave,
  StaveNote,
  StaveConnector,
  Voice,
  Formatter,
  Accidental,
  Dot,
} from "vexflow";
import { layout, type Clef, type NElement, type PlayedNote } from "./notation";

const SHARP_NAMES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"];
const GHOST_COLOR = "#9aa0a6";

/** MIDI number -> VexFlow key like "c#/4", plus whether it needs an accidental. */
export function midiToVexKey(midi: number): { key: string; accidental: string | null } {
  const name = SHARP_NAMES[midi % 12];
  const octave = Math.floor(midi / 12) - 1;
  return { key: `${name}/${octave}`, accidental: name.includes("#") ? "#" : null };
}

function buildElement(el: NElement, clef: Clef): StaveNote {
  if (el.kind === "rest") {
    const sn = new StaveNote({
      keys: [clef === "treble" ? "b/4" : "d/3"],
      duration: `${el.code}r`,
      clef,
    });
    for (let i = 0; i < el.dots; i++) Dot.buildAndAttach([sn], { all: true });
    return sn;
  }
  const sorted = [...el.notes].sort((a, b) => a - b);
  const sn = new StaveNote({ keys: sorted.map((m) => midiToVexKey(m).key), duration: el.code, clef });
  sorted.forEach((m, i) => {
    if (midiToVexKey(m).accidental) sn.addModifier(new Accidental("#"), i);
  });
  for (let i = 0; i < el.dots; i++) Dot.buildAndAttach([sn], { all: true });
  if (el.ghost) sn.setStyle({ fillStyle: GHOST_COLOR, strokeStyle: GHOST_COLOR });
  return sn;
}

export interface ScoreProps {
  events: PlayedNote[];
  width?: number;
  measuresPerRow?: number;
}

const ROW_HEIGHT = 210; // room for ledger lines between systems
const STAFF_GAP = 95; // treble -> bass offset within a system
const TOP_PAD = 10;
const BOTTOM_PAD = 80; // space for low bass ledger lines on the last system
const MIN_BARS = 3; // always show at least three systems from the start

export function Score({ events, width = 720, measuresPerRow = 1 }: ScoreProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.innerHTML = "";

    const { treble, bass } = layout(events);
    const barCount = Math.max(treble.length, bass.length, MIN_BARS);
    const measureW = (width - 20) / measuresPerRow;
    const rows = Math.ceil(barCount / measuresPerRow);

    const renderer = new Renderer(el, Renderer.Backends.SVG);
    renderer.resize(width, rows * ROW_HEIGHT + TOP_PAD + BOTTOM_PAD);
    const ctx = renderer.getContext();

    for (let bar = 0; bar < barCount; bar++) {
      const row = Math.floor(bar / measuresPerRow);
      const col = bar % measuresPerRow;
      const x = 10 + col * measureW;
      const trebleY = TOP_PAD + row * ROW_HEIGHT;
      const bassY = trebleY + STAFF_GAP;

      const tStave = new Stave(x, trebleY, measureW);
      const bStave = new Stave(x, bassY, measureW);
      if (col === 0) {
        tStave.addClef("treble");
        bStave.addClef("bass");
        if (bar === 0) {
          tStave.addTimeSignature("4/4");
          bStave.addTimeSignature("4/4");
        }
      }
      tStave.setContext(ctx).draw();
      bStave.setContext(ctx).draw();
      if (col === 0) {
        new StaveConnector(tStave, bStave).setType(StaveConnector.type.BRACE).setContext(ctx).draw();
        new StaveConnector(tStave, bStave).setType(StaveConnector.type.SINGLE_LEFT).setContext(ctx).draw();
      }

      const wholeRest: NElement = { kind: "rest", code: "w", dots: 0, beats: 4, notes: [], ghost: false };
      const drawClef = (stave: Stave, measure: NElement[] | undefined, clef: Clef) => {
        const els = measure && measure.length ? measure : [wholeRest]; // empty bar -> whole rest
        const voice = new Voice({ numBeats: 4, beatValue: 4 }).setStrict(false);
        voice.addTickables(els.map((m) => buildElement(m, clef)));
        new Formatter().joinVoices([voice]).format([voice], measureW - (col === 0 ? 60 : 20));
        voice.draw(ctx, stave);
      };
      drawClef(tStave, treble[bar], "treble");
      drawClef(bStave, bass[bar], "bass");
    }
  }, [events, width, measuresPerRow]);

  return <div ref={containerRef} />;
}
