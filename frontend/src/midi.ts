// Live MIDI input via WebMidi.js. Chrome/Edge/Firefox only (Safari lacks Web MIDI).

import { WebMidi, type Input, type NoteMessageEvent } from "webmidi";

export interface MidiNoteEvent {
  note: number; // MIDI number 0-127
  velocity: number; // 0-127
  time: number; // seconds
}

export interface MidiHandlers {
  onNoteOn: (e: MidiNoteEvent) => void;
  onNoteOff: (e: MidiNoteEvent) => void;
}

export function isSupported(): boolean {
  return typeof navigator !== "undefined" && "requestMIDIAccess" in navigator;
}

/** Enable Web MIDI and return the list of input device names. */
export async function enableMidi(): Promise<string[]> {
  if (!isSupported()) {
    throw new Error("Web MIDI is not supported in this browser (use Chrome or Edge).");
  }
  await WebMidi.enable();
  return WebMidi.inputs.map((i) => i.name);
}

/** Attach handlers to every connected input. Returns a cleanup function. */
export function listen(handlers: MidiHandlers): () => void {
  const inputs: Input[] = WebMidi.inputs;
  const cleanups: Array<() => void> = [];

  for (const input of inputs) {
    const on = (e: NoteMessageEvent) =>
      handlers.onNoteOn({
        note: e.note.number,
        velocity: e.note.rawAttack,
        time: performance.now() / 1000,
      });
    const off = (e: NoteMessageEvent) =>
      handlers.onNoteOff({
        note: e.note.number,
        velocity: 0,
        time: performance.now() / 1000,
      });

    input.addListener("noteon", on);
    input.addListener("noteoff", off);
    cleanups.push(() => {
      input.removeListener("noteon", on);
      input.removeListener("noteoff", off);
    });
  }

  return () => cleanups.forEach((c) => c());
}
