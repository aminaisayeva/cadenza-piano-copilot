import { describe, expect, it } from "vitest";
import { decompose, layout, layoutClef, MEASURE_BEATS, type PlayedNote } from "./notation";

const sum = (els: { beats: number }[]) => els.reduce((a, e) => a + e.beats, 0);

describe("decompose", () => {
  it("maps standard values", () => {
    expect(decompose(4)).toEqual([{ beats: 4, code: "w", dots: 0 }]);
    expect(decompose(3)).toEqual([{ beats: 3, code: "h", dots: 1 }]); // dotted half
    expect(decompose(1)).toEqual([{ beats: 1, code: "q", dots: 0 }]);
    expect(decompose(0.75)).toEqual([{ beats: 0.75, code: "8", dots: 1 }]);
  });

  it("splits non-standard spans into pieces that sum exactly", () => {
    expect(sum(decompose(2.5))).toBeCloseTo(2.5);
    expect(sum(decompose(3.25))).toBeCloseTo(3.25);
  });
});

describe("layoutClef", () => {
  it("fills the rest of the bar after a single quarter note", () => {
    const m = layoutClef([{ note: 60, onset: 0, dur: 1 }], MEASURE_BEATS);
    expect(m).toHaveLength(1);
    expect(m[0][0]).toMatchObject({ kind: "note", code: "q", notes: [60] });
    expect(m[0].slice(1).every((e) => e.kind === "rest")).toBe(true);
    expect(sum(m[0])).toBeCloseTo(MEASURE_BEATS); // every measure totals 4 beats
  });

  it("uses a single whole rest for a fully silent bar", () => {
    const m = layoutClef([], MEASURE_BEATS);
    expect(m[0]).toHaveLength(1);
    expect(m[0][0]).toMatchObject({ kind: "rest", code: "w" });
  });

  it("spreads notes across the right number of bars", () => {
    const notes: PlayedNote[] = [
      { note: 60, onset: 0, dur: 1 },
      { note: 62, onset: 4, dur: 1 }, // second bar
    ];
    const m = layoutClef(notes, 5);
    expect(m).toHaveLength(2);
    expect(sum(m[0])).toBeCloseTo(4);
    expect(sum(m[1])).toBeCloseTo(4);
  });
});

describe("layout (grand staff split)", () => {
  it("routes a left-hand chord to the bass clef as one stacked chord", () => {
    const chord: PlayedNote[] = [
      { note: 48, onset: 0, dur: 2 },
      { note: 52, onset: 0, dur: 2 },
      { note: 55, onset: 0, dur: 2 },
    ];
    const { treble, bass } = layout(chord);
    // bass: a half-note chord, then a half rest
    expect(bass[0][0]).toMatchObject({ kind: "note", code: "h" });
    expect(bass[0][0].notes.sort((a, b) => a - b)).toEqual([48, 52, 55]);
    // treble: silent -> whole rest
    expect(treble[0][0]).toMatchObject({ kind: "rest", code: "w" });
  });

  it("keeps fast sequential notes separate (no stacking)", () => {
    // played ~50ms apart (> chord window) -> three distinct notes, not a chord
    const fast: PlayedNote[] = [
      { note: 64, onset: 0, dur: 0.25 },
      { note: 65, onset: 0.1, dur: 0.25 },
      { note: 67, onset: 0.2, dur: 0.25 },
    ];
    const { treble } = layout(fast);
    const noteEls = treble.flat().filter((e) => e.kind === "note");
    expect(noteEls).toHaveLength(3);
    expect(noteEls.every((e) => e.notes.length === 1)).toBe(true);
  });

  it("merges near-simultaneous notes into one chord", () => {
    const chord: PlayedNote[] = [
      { note: 64, onset: 0, dur: 1 },
      { note: 67, onset: 0.02, dur: 1 },
      { note: 72, onset: 0.04, dur: 1 },
    ];
    const { treble } = layout(chord);
    const noteEls = treble.flat().filter((e) => e.kind === "note");
    expect(noteEls).toHaveLength(1);
    expect(noteEls[0].notes.sort((a, b) => a - b)).toEqual([64, 67, 72]);
  });

  it("routes high notes to treble, low to bass", () => {
    const { treble, bass } = layout([
      { note: 72, onset: 0, dur: 1 },
      { note: 36, onset: 0, dur: 1 },
    ]);
    expect(treble[0][0].notes).toEqual([72]);
    expect(bass[0][0].notes).toEqual([36]);
  });
});
