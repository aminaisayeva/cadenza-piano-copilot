// Typed WebSocket client mirroring backend/app/protocol.py.

export type ClientMessage =
  | { type: "note_on"; note: number; velocity: number; time: number }
  | { type: "note_off"; note: number; time: number }
  | { type: "request_suggestion"; mode: SuggestMode; style?: string; model?: string }
  | { type: "decision"; suggestion_id: string; accepted: boolean };

export type SuggestMode = "continue" | "harmonize" | "reharmonize";

export interface SuggestedNote {
  note: number;
  start: number;
  duration: number;
}

export type ServerMessage =
  | { type: "ack"; echo: unknown }
  | { type: "analysis"; key?: string; chord?: string; roman?: string }
  | {
      type: "suggestion";
      id: string;
      mode: string;
      model: string;
      notes: SuggestedNote[];
      explanation?: string;
      latency_ms?: number;
    };

type Listener = (msg: ServerMessage) => void;

export class CadenzaSocket {
  private ws: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private url: string;
  onStatusChange?: (connected: boolean) => void;

  constructor(url = "ws://localhost:8200/ws") {
    this.url = url;
  }

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => this.onStatusChange?.(true);
    this.ws.onclose = () => {
      this.onStatusChange?.(false);
      // simple auto-reconnect for dev convenience
      setTimeout(() => this.connect(), 1000);
    };
    this.ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as ServerMessage;
      this.listeners.forEach((l) => l(msg));
    };
  }

  send(msg: ClientMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  on(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}
