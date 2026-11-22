import { DECISION_TIERS, type CheckResponse, type DecisionTier, type StreamEvent } from "./types";

export class NdjsonError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NdjsonError";
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isTier(v: unknown): v is DecisionTier {
  return typeof v === "string" && (DECISION_TIERS as readonly string[]).includes(v);
}

function strings(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

/** Validates and normalizes a CheckResponse; returns null when the verdict is unusable. */
export function normalizeCheckResponse(raw: unknown): CheckResponse | null {
  if (!isRecord(raw) || !isRecord(raw.verdict)) return null;
  const v = raw.verdict;
  if (!isTier(v.decision_tier)) return null;
  const hints = isRecord(raw.ui_hints) ? raw.ui_hints : {};
  return {
    request_id: typeof raw.request_id === "string" ? raw.request_id : "",
    verdict_id: typeof raw.verdict_id === "string" ? raw.verdict_id : "",
    channel: typeof raw.channel === "string" ? raw.channel : "FLOW_B",
    verdict: {
      decision_tier: v.decision_tier,
      reason_codes: strings(v.reason_codes),
      evidence_bullets: strings(v.evidence_bullets),
      system2_check_questions: strings(v.system2_check_questions),
      cooling_off_seconds:
        typeof v.cooling_off_seconds === "number" && Number.isFinite(v.cooling_off_seconds)
          ? v.cooling_off_seconds
          : 0,
    },
    ui_hints: {
      calm_shield: hints.calm_shield === true,
      hotline: typeof hints.hotline === "string" && hints.hotline ? hints.hotline : null,
    },
  };
}

/** Parses one NDJSON line. Returns null for blank lines; throws NdjsonError on bad data. */
export function parseNdjsonLine(line: string): StreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  let raw: unknown;
  try {
    raw = JSON.parse(trimmed);
  } catch {
    throw new NdjsonError("Dòng NDJSON không hợp lệ");
  }
  if (!isRecord(raw)) throw new NdjsonError("Sự kiện NDJSON không hợp lệ");
  if (raw.event === "stage2") {
    if (!isTier(raw.provisional_tier)) throw new NdjsonError("Sự kiện stage2 không hợp lệ");
    return {
      event: "stage2",
      request_id: typeof raw.request_id === "string" ? raw.request_id : "",
      provisional_tier: raw.provisional_tier,
      provisional_reason_codes: strings(raw.provisional_reason_codes),
      red_alert: raw.red_alert === true,
    };
  }
  if (raw.event === "final") {
    const response = normalizeCheckResponse(raw.response);
    if (!response) throw new NdjsonError("Sự kiện final không hợp lệ");
    return { event: "final", response };
  }
  if (typeof raw.error === "string") {
    return {
      event: "error",
      error: raw.error,
      message_vi: typeof raw.message_vi === "string" ? raw.message_vi : "",
    };
  }
  throw new NdjsonError("Sự kiện NDJSON không xác định");
}

/** Incremental parser: feed decoded chunks, get complete events. Call `flush()` at end of stream. */
export class NdjsonParser {
  private buffer = "";

  push(chunk: string): StreamEvent[] {
    this.buffer += chunk;
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() ?? "";
    return lines.flatMap((l) => {
      const e = parseNdjsonLine(l);
      return e ? [e] : [];
    });
  }

  flush(): StreamEvent[] {
    const rest = this.buffer;
    this.buffer = "";
    const e = parseNdjsonLine(rest);
    return e ? [e] : [];
  }
}

/** Reads a fetch body as NDJSON events. */
export async function* readNdjson(body: ReadableStream<Uint8Array>): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = new NdjsonParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      yield* parser.push(decoder.decode(value, { stream: true }));
    }
    yield* parser.push(decoder.decode());
    yield* parser.flush();
  } finally {
    reader.releaseLock();
  }
}