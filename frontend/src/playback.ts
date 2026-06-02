// Audio playback of suggestions via smplr's sampled grand piano.
// AudioContext must be created/resumed from a user gesture (browser policy).

import { SplendidGrandPiano } from "smplr";
import type { SuggestedNote } from "./ws";

let ctx: AudioContext | null = null;
let piano: SplendidGrandPiano | null = null;
let ready: Promise<unknown> | null = null;

/** Lazily create the AudioContext + piano and wait for samples to load. */
export async function initAudio(): Promise<void> {
  if (!ctx) {
    ctx = new AudioContext();
    piano = new SplendidGrandPiano(ctx);
    ready = piano.ready;
  }
  await ready;
  if (ctx.state === "suspended") await ctx.resume();
}

/** Play a suggestion, honoring each note's start/duration in beats. */
export async function playSuggestion(notes: SuggestedNote[], bpm = 120): Promise<void> {
  await initAudio();
  const secPerBeat = 60 / bpm;
  const t0 = ctx!.currentTime + 0.05;
  for (const n of notes) {
    piano!.start({
      note: n.note,
      time: t0 + n.start * secPerBeat,
      duration: Math.max(0.2, n.duration * secPerBeat),
      velocity: 90,
    });
  }
}

/** Play a single note (used to echo the player's own key presses if desired). */
export async function playNote(midi: number): Promise<void> {
  await initAudio();
  piano!.start({ note: midi, duration: 0.5, velocity: 90 });
}

// --- melody transport (Run / Stop) ----------------------------------------

let melodyTimers: number[] = [];

/** Stop any in-progress melody playback. */
export function stopMelody(): void {
  melodyTimers.forEach((id) => clearTimeout(id));
  melodyTimers = [];
  piano?.stop();
}

/**
 * Replay a performance at its captured tempo: each note sounds at its real onset
 * and is held for its real duration (both in beats). stopMelody() halts it.
 */
export async function playPerformance(
  notes: { note: number; onset: number; dur: number }[],
  bpm = 120,
): Promise<void> {
  await initAudio();
  stopMelody();
  const beatMs = 60000 / bpm;
  const t0 = Math.min(...notes.map((n) => n.onset), 0);
  for (const n of notes) {
    const id = window.setTimeout(() => {
      piano?.start({ note: n.note, duration: Math.max(0.1, (n.dur * beatMs) / 1000), velocity: 90 });
    }, (n.onset - t0) * beatMs);
    melodyTimers.push(id);
  }
}
