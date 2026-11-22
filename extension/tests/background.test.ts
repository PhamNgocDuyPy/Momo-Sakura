import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  FINAL_TIMEOUT_MS,
  FIRST_EVENT_TIMEOUT_MS,
  MSG_NO_FINAL,
  MSG_TIMEOUT,
  handleCheckPort,
  msgHttp,
  msgNetwork,
  runCheck,
} from "../src/background/check";
import { triggerTab } from "../src/background/trigger";
import { STORAGE_KEYS, isUuidV4 } from "../src/shared/settings";
import type { BackgroundMessage } from "../src/shared/types";
import { finalLine, installChromeStorage, makeFakePort, makeResponse, ndjsonResponse, stage2Line } from "./helpers";

const fetchMock = vi.fn();
let store: Record<string, unknown>;

beforeEach(() => {
  store = installChromeStorage();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const request = { type: "check" as const, text: "Chuyển 50tr vào stk 123", origin: "EXTENSION_SELECTION" as const };

function collect(): { msgs: BackgroundMessage[]; post: (m: BackgroundMessage) => void } {
  const msgs: BackgroundMessage[] = [];
  return { msgs, post: (m) => void msgs.push(m) };
}

/** fetch that never answers but honours abort, like the real one. */
function hangingFetch(): void {
  fetchMock.mockImplementation(
    (_url: string, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      }),
  );
}

describe("runCheck", () => {
  it("POSTs the Flow B request with a uuid v4 session header and forwards stage2 then final", async () => {
    fetchMock.mockResolvedValue(ndjsonResponse([stage2Line(), finalLine(makeResponse())]));
    const { msgs, post } = collect();
    await runCheck(request, post);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/flow-b/check");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(isUuidV4(headers["X-Guardian-Session"])).toBe(true);
    expect(store[STORAGE_KEYS.sessionId]).toBe(headers["X-Guardian-Session"]);
    expect(JSON.parse(init.body as string)).toEqual({
      content: { origin: "EXTENSION_SELECTION", text: "Chuyển 50tr vào stk 123" },
      mode: "GENERAL",
      explicit_consent_flag: false,
    });
    expect(msgs.map((m) => m.type)).toEqual(["stage2", "final"]);
    expect(msgs[0]).toMatchObject({ type: "stage2", event: { red_alert: true } });
    expect(msgs[1]).toMatchObject({ type: "final", response: { verdict: { decision_tier: "HARD_HOLD" } } });
  });

  it("uses the configured backend and sends EXTENSION_PAGE_TEXT", async () => {
    store[STORAGE_KEYS.backendUrl] = "http://127.0.0.1:9000/";
    fetchMock.mockResolvedValue(ndjsonResponse([finalLine()]));
    const { post } = collect();
    await runCheck({ ...request, origin: "EXTENSION_PAGE_TEXT" }, post);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:9000/api/flow-b/check");
    expect(JSON.parse(init.body as string).content.origin).toBe("EXTENSION_PAGE_TEXT");
  });

  it("trims text to the last 4000 characters", async () => {
    fetchMock.mockResolvedValue(ndjsonResponse([finalLine()]));
    await runCheck({ ...request, text: "a".repeat(100) + "b".repeat(4000) }, () => {});
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
    expect(body.content.text).toBe("b".repeat(4000));
  });

  it("reports the backend's message_vi on an HTTP error and posts no verdict", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "CONTENT_TOO_LONG", message_vi: "Nội dung quá dài." }), { status: 422 }),
    );
    const { msgs, post } = collect();
    await runCheck(request, post);
    expect(msgs).toEqual([{ type: "error", message_vi: "Nội dung quá dài." }]);
  });

  it("uses a generic Vietnamese message when the error body is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("oops", { status: 502 }));
    const { msgs, post } = collect();
    await runCheck(request, post);
    expect(msgs).toEqual([{ type: "error", message_vi: msgHttp(502) }]);
  });

  it("reports a network failure in Vietnamese", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const { msgs, post } = collect();
    await runCheck(request, post);
    expect(msgs).toEqual([{ type: "error", message_vi: msgNetwork("http://localhost:8000") }]);
  });

  it("errors when the stream ends without final, even after a provisional stage2", async () => {
    fetchMock.mockResolvedValue(ndjsonResponse([stage2Line("ALLOW", false)]));
    const { msgs, post } = collect();
    await runCheck(request, post);
    expect(msgs.map((m) => m.type)).toEqual(["stage2", "error"]);
    expect(msgs[1]).toEqual({ type: "error", message_vi: MSG_NO_FINAL });
  });

  it("errors on malformed NDJSON", async () => {
    fetchMock.mockResolvedValue(ndjsonResponse(["{not json"]));
    const { msgs, post } = collect();
    await runCheck(request, post);
    expect(msgs.map((m) => m.type)).toEqual(["error"]);
  });

  it("times out after 10 s without a first event", async () => {
    vi.useFakeTimers();
    hangingFetch();
    const { msgs, post } = collect();
    const done = runCheck(request, post);
    await vi.advanceTimersByTimeAsync(FIRST_EVENT_TIMEOUT_MS + 10);
    await done;
    expect(msgs).toEqual([{ type: "error", message_vi: MSG_TIMEOUT }]);
  });

  it("times out when final does not follow stage2", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      const enc = new TextEncoder();
      const body = new ReadableStream<Uint8Array>({
        start(c) {
          c.enqueue(enc.encode(`${stage2Line()}\n`));
          init.signal?.addEventListener("abort", () => c.error(new DOMException("Aborted", "AbortError")));
        },
      });
      return Promise.resolve(new Response(body, { status: 200 }));
    });
    const { msgs, post } = collect();
    const done = runCheck(request, post);
    await vi.advanceTimersByTimeAsync(FINAL_TIMEOUT_MS + 10);
    await done;
    expect(msgs.map((m) => m.type)).toEqual(["stage2", "error"]);
    expect(msgs[1]).toEqual({ type: "error", message_vi: MSG_TIMEOUT });
  });

  it("rejects empty text without calling the backend", async () => {
    const { msgs, post } = collect();
    await runCheck({ ...request, text: "   " }, post);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(msgs.map((m) => m.type)).toEqual(["error"]);
  });
});

describe("handleCheckPort", () => {
  const flush = async (): Promise<void> => {
    for (let i = 0; i < 20; i++) await Promise.resolve();
    await new Promise((r) => setTimeout(r, 0));
  };

  it("handles a guardian-check request end to end through the port", async () => {
    fetchMock.mockResolvedValue(ndjsonResponse([stage2Line(), finalLine()]));
    const port = makeFakePort();
    handleCheckPort(port as unknown as chrome.runtime.Port);
    port.receive(request);
    await vi.waitFor(() => expect(port.sent()).toHaveLength(2));
    expect((port.sent() as BackgroundMessage[]).map((m) => m.type)).toEqual(["stage2", "final"]);
  });

  it("ignores ports with another name", async () => {
    const port = makeFakePort("other");
    handleCheckPort(port as unknown as chrome.runtime.Port);
    port.receive(request);
    await flush();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("answers an invalid request with an error and does not call the backend", async () => {
    const port = makeFakePort();
    handleCheckPort(port as unknown as chrome.runtime.Port);
    port.receive({ type: "check", text: 5, origin: "PASTE" });
    expect(port.sent()).toEqual([{ type: "error", message_vi: expect.any(String) }]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("aborts the fetch and stays silent when the port disconnects", async () => {
    hangingFetch();
    const port = makeFakePort();
    handleCheckPort(port as unknown as chrome.runtime.Port);
    port.receive(request);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    port.disconnect();
    await flush();
    expect((fetchMock.mock.calls[0][1] as RequestInit).signal?.aborted).toBe(true);
    expect(port.sent()).toEqual([]);
  });

  it("forwards a network failure as an error message, never a verdict", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const port = makeFakePort();
    handleCheckPort(port as unknown as chrome.runtime.Port);
    port.receive(request);
    await vi.waitFor(() => expect(port.sent()).toHaveLength(1));
    expect(port.sent()[0]).toMatchObject({ type: "error" });
    expect(JSON.stringify(port.sent())).not.toContain("ALLOW");
  });
});

describe("triggerTab", () => {
  function installTabs(sendMessage: ReturnType<typeof vi.fn>, executeScript: ReturnType<typeof vi.fn>): void {
    (globalThis as unknown as { chrome: Record<string, unknown> }).chrome = {
      tabs: { sendMessage },
      scripting: { executeScript },
    };
  }

  it("messages the content script directly when it is already there", async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    const exec = vi.fn();
    installTabs(send, exec);
    expect(await triggerTab(7, "chọn")).toBe(true);
    expect(send).toHaveBeenCalledWith(7, { type: "guardian-trigger", selectionText: "chọn" });
    expect(exec).not.toHaveBeenCalled();
  });

  it("injects content.js with chrome.scripting on pages outside the matches, then retries", async () => {
    const send = vi.fn().mockRejectedValueOnce(new Error("Receiving end does not exist")).mockResolvedValue(undefined);
    const exec = vi.fn().mockResolvedValue([]);
    installTabs(send, exec);
    expect(await triggerTab(9)).toBe(true);
    expect(exec).toHaveBeenCalledWith({ target: { tabId: 9 }, files: ["content.js"] });
    expect(send).toHaveBeenCalledTimes(2);
  });

  it("returns false when the page cannot be injected", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    installTabs(vi.fn().mockRejectedValue(new Error("no")), vi.fn().mockRejectedValue(new Error("restricted")));
    expect(await triggerTab(1)).toBe(false);
    warn.mockRestore();
  });
});