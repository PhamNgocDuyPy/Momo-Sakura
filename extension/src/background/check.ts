import { readNdjson } from "../shared/ndjson";
import { getSettings } from "../shared/settings";
import type { BackgroundMessage, CheckRequestMessage, FlowBCheckRequest } from "../shared/types";
import { CHECK_PORT_NAME } from "../shared/types";

/** Max wait for the first NDJSON line (stage2) after the request is sent. */
export const FIRST_EVENT_TIMEOUT_MS = 10_000;
/** Max wait for `final` once `stage2` arrived (Stage 3 may call the LLM). */
export const FINAL_TIMEOUT_MS = 20_000;
export const MAX_TEXT_CHARS = 4000;

export const MSG_TIMEOUT = "MoMo Guardian phản hồi quá lâu. Vui lòng thử lại sau.";
export const MSG_NO_FINAL = "MoMo Guardian chưa trả về kết luận. Vui lòng thử lại.";
export const MSG_BAD_REQUEST = "Yêu cầu kiểm tra không hợp lệ.";
export const msgNetwork = (backendUrl: string): string =>
  `Không kết nối được tới MoMo Guardian (${backendUrl}). Hãy kiểm tra backend đang chạy rồi thử lại.`;
export const msgHttp = (status: number): string => `MoMo Guardian gặp lỗi (mã ${status}). Vui lòng thử lại.`;

export type Post = (message: BackgroundMessage) => void;

function isCheckRequest(m: unknown): m is CheckRequestMessage {
  if (typeof m !== "object" || m === null) return false;
  const r = m as Record<string, unknown>;
  return (
    r.type === "check" &&
    typeof r.text === "string" &&
    (r.origin === "EXTENSION_SELECTION" || r.origin === "EXTENSION_PAGE_TEXT")
  );
}

async function errorFromResponse(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (typeof body === "object" && body !== null) {
      const m = (body as Record<string, unknown>).message_vi;
      if (typeof m === "string" && m.trim()) return m;
    }
  } catch {
    // body is not JSON; fall through
  }
  return msgHttp(res.status);
}

/**
 * Calls POST {backend}/api/flow-b/check and forwards `stage2`, `final` or `error` through `post`.
 * Never posts a verdict on failure: every failure path ends in a single `error` message.
 * `signal` lets the caller (port disconnect) cancel silently.
 */
export async function runCheck(request: CheckRequestMessage, post: Post, signal?: AbortSignal): Promise<void> {
  const text = request.text.slice(-MAX_TEXT_CHARS);
  if (!text.trim()) {
    post({ type: "error", message_vi: MSG_BAD_REQUEST });
    return;
  }
  const ctrl = new AbortController();
  const onExternalAbort = (): void => ctrl.abort();
  signal?.addEventListener("abort", onExternalAbort);
  let timedOut = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const arm = (ms: number): void => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      timedOut = true;
      ctrl.abort();
    }, ms);
  };
  let backendUrl = "";
  try {
    const settings = await getSettings();
    backendUrl = settings.backendUrl;
    const body: FlowBCheckRequest = {
      content: { origin: request.origin, text },
      mode: "GENERAL",
      explicit_consent_flag: false,
    };
    arm(FIRST_EVENT_TIMEOUT_MS);
    const res = await fetch(`${backendUrl}/api/flow-b/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Guardian-Session": settings.sessionId },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      post({ type: "error", message_vi: await errorFromResponse(res) });
      return;
    }
    if (!res.body) {
      post({ type: "error", message_vi: MSG_NO_FINAL });
      return;
    }
    for await (const ev of readNdjson(res.body)) {
      if (ev.event === "stage2") {
        post({ type: "stage2", event: ev });
        arm(FINAL_TIMEOUT_MS);
      } else if (ev.event === "final") {
        post({ type: "final", response: ev.response });
        return;
      } else {
        post({ type: "error", message_vi: ev.message_vi.trim() || msgHttp(res.status) });
        return;
      }
    }
    post({ type: "error", message_vi: MSG_NO_FINAL });
  } catch {
    if (signal?.aborted) return; // the user closed the overlay
    post({ type: "error", message_vi: timedOut ? MSG_TIMEOUT : backendUrl ? msgNetwork(backendUrl) : MSG_NO_FINAL });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onExternalAbort);
    ctrl.abort();
  }
}

/** Handles one `guardian-check` port: one request per port, cancelled when the port disconnects. */
export function handleCheckPort(port: chrome.runtime.Port): void {
  if (port.name !== CHECK_PORT_NAME) return;
  const ctrl = new AbortController();
  let started = false;
  const post: Post = (message) => {
    if (ctrl.signal.aborted) return;
    try {
      port.postMessage(message);
    } catch {
      ctrl.abort();
    }
  };
  port.onDisconnect.addListener(() => ctrl.abort());
  port.onMessage.addListener((message: unknown) => {
    if (started) return;
    if (!isCheckRequest(message)) {
      post({ type: "error", message_vi: MSG_BAD_REQUEST });
      return;
    }
    started = true;
    void runCheck(message, post, ctrl.signal);
  });
}