import { ApiError, apiFetch } from "./api";
import type { ApiErrorBody, FlowBCheckRequest, FlowBEvent, FlowBFinalEvent, FlowBStage2Event } from "../types/api";

/** Read a byte stream and yield one parsed JSON value per non-empty line. */
export async function* readNdjson(body: ReadableStream<Uint8Array>): AsyncGenerator<unknown> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl = buffer.indexOf("\n");
      while (nl >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (line) yield JSON.parse(line) as unknown;
        nl = buffer.indexOf("\n");
      }
    }
    buffer += decoder.decode();
    const rest = buffer.trim();
    if (rest) yield JSON.parse(rest) as unknown;
  } finally {
    reader.releaseLock();
  }
}

export interface FlowBStreamResult {
  stage2: FlowBStage2Event | null;
  final: FlowBFinalEvent | null;
  /** True when the stream ended or broke before a `final` event arrived. */
  interrupted: boolean;
}

export interface FlowBStreamOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  onStage2?: (event: FlowBStage2Event) => void;
  onFinal?: (event: FlowBFinalEvent) => void;
}

function isFlowBEvent(v: unknown): v is FlowBEvent {
  if (typeof v !== "object" || v === null) return false;
  const e = (v as { event?: unknown }).event;
  return e === "stage2" || e === "final";
}

/**
 * POST /api/flow-b/check and consume the NDJSON stream (stage2 then final).
 * A broken stream keeps whatever was received and reports `interrupted`.
 */
export async function streamFlowBCheck(
  req: FlowBCheckRequest,
  options: FlowBStreamOptions = {},
): Promise<FlowBStreamResult> {
  const res = await apiFetch("/flow-b/check", {
    method: "POST",
    body: req,
    ...(options.signal ? { signal: options.signal } : {}),
    ...(options.timeoutMs !== undefined ? { timeoutMs: options.timeoutMs } : {}),
  });
  if (!res.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = (await res.json()) as Partial<ApiErrorBody>;
    } catch {
      body = {};
    }
    throw new ApiError(res.status, body);
  }
  const result: FlowBStreamResult = { stage2: null, final: null, interrupted: false };
  if (!res.body) {
    result.interrupted = true;
    return result;
  }
  try {
    for await (const item of readNdjson(res.body)) {
      if (!isFlowBEvent(item)) continue;
      if (item.event === "stage2") {
        result.stage2 = item;
        options.onStage2?.(item);
      } else {
        result.final = item;
        options.onFinal?.(item);
      }
    }
  } catch {
    result.interrupted = true;
  }
  if (!result.final) result.interrupted = true;
  return result;
}
