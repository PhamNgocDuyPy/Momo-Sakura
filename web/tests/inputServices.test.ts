import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const jsqrMock = vi.hoisted(() => vi.fn());
vi.mock("jsqr", () => ({ default: jsqrMock }));

const tessMock = vi.hoisted(() => ({
  createWorker: vi.fn(),
}));
vi.mock("tesseract.js", () => tessMock);

import { digitsOnly, splitDigits } from "../src/lib/digits";
import { createClipboardDedupe, sha256Hex } from "../src/lib/clipboardDedupe";
import { readNdjson, streamFlowBCheck } from "../src/services/ndjson";
import { ApiError } from "../src/services/api";
import {
  CLIPBOARD_OPTIN_KEY,
  readClipboardOnce,
  resetClipboardDedupe,
  setClipboardOptIn,
} from "../src/services/clipboard";
import { decodeQrFromImageData, openQrCamera, CAMERA_DENIED_HINT_VI } from "../src/services/qrDecode";
import { getOcrWorker, recognizeText, terminateOcrWorker } from "../src/services/ocr";
import type { FlowBCheckRequest } from "../src/types/api";

function streamOf(chunks: string[], failAfter = false): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  let i = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(enc.encode(chunks[i++]));
      } else if (failAfter) {
        controller.error(new Error("broken"));
      } else {
        controller.close();
      }
    },
  });
}

const REQ: FlowBCheckRequest = {
  content: { origin: "PASTE", text: "hi" },
  mode: "GENERAL",
  explicit_consent_flag: false,
};

describe("digits", () => {
  it("splits digits", () => {
    expect(digitsOnly("0123 456-789")).toBe("0123456789");
    expect(splitDigits("1a2 3")).toEqual(["1", "2", "3"]);
  });
});

describe("clipboardDedupe", () => {
  it("hashes with SHA-256", async () => {
    expect(await sha256Hex("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });
  it("rejects repeats of the last value only", async () => {
    const d = createClipboardDedupe();
    expect(await d.accept("a")).toBe(true);
    expect(await d.accept("a")).toBe(false);
    expect(await d.accept("b")).toBe(true);
    expect(await d.accept("a")).toBe(true);
  });
});

describe("ndjson", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("parses lines split across chunks", async () => {
    const out: unknown[] = [];
    for await (const v of readNdjson(streamOf(['{"a":1}\n{"b"', ":2}\n\n", '{"c":3}']))) out.push(v);
    expect(out).toEqual([{ a: 1 }, { b: 2 }, { c: 3 }]);
  });

  it("delivers stage2 then final", async () => {
    const s2 = { event: "stage2", request_id: "r", red_alert: true };
    const fin = { event: "final", response: { channel: "FLOW_B" } };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(streamOf([JSON.stringify(s2) + "\n", JSON.stringify(fin) + "\n"]), { status: 200 })),
    );
    const order: string[] = [];
    const res = await streamFlowBCheck(REQ, {
      onStage2: () => order.push("stage2"),
      onFinal: () => order.push("final"),
    });
    expect(order).toEqual(["stage2", "final"]);
    expect(res.interrupted).toBe(false);
    expect(res.stage2?.red_alert).toBe(true);
  });

  it("keeps stage2 and flags interruption when the stream breaks", async () => {
    const s2 = { event: "stage2", request_id: "r", red_alert: false };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(streamOf([JSON.stringify(s2) + "\n"], true), { status: 200 })),
    );
    const res = await streamFlowBCheck(REQ);
    expect(res.stage2?.request_id).toBe("r");
    expect(res.final).toBeNull();
    expect(res.interrupted).toBe(true);
  });

  it("throws ApiError on HTTP errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: "CONTENT_TOO_LONG" }), { status: 422 })),
    );
    await expect(streamFlowBCheck(REQ)).rejects.toBeInstanceOf(ApiError);
  });
});

describe("clipboard", () => {
  beforeEach(() => {
    localStorage.clear();
    resetClipboardDedupe();
  });
  afterEach(() => vi.unstubAllGlobals());

  function mockClipboard(readText: () => Promise<string>) {
    const fn = vi.fn(readText);
    Object.defineProperty(navigator, "clipboard", { value: { readText: fn }, configurable: true });
    return fn;
  }

  it("does not read when opt-in is off", async () => {
    const fn = mockClipboard(async () => "x");
    expect((await readClipboardOnce("popup_open")).status).toBe("disabled");
    expect(fn).not.toHaveBeenCalled();
  });

  it("reads once per event and dedupes the same value", async () => {
    setClipboardOptIn(true);
    expect(localStorage.getItem(CLIPBOARD_OPTIN_KEY)).toBe("1");
    const fn = mockClipboard(async () => "stk 123");
    expect(await readClipboardOnce("popup_open")).toEqual({ status: "text", text: "stk 123" });
    expect((await readClipboardOnce("tab_visible")).status).toBe("duplicate");
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("reports denial with the Vietnamese message", async () => {
    setClipboardOptIn(true);
    mockClipboard(async () => {
      throw new DOMException("no", "NotAllowedError");
    });
    const r = await readClipboardOnce("popup_open");
    expect(r.status).toBe("denied");
  });

  it("clipboard.ts never polls", () => {
    const src = readFileSync("src/services/clipboard.ts", "utf8");
    expect(src).not.toMatch(/setInterval|setTimeout/);
  });
});

describe("qrDecode", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns the jsQR payload or null", () => {
    jsqrMock.mockReturnValueOnce({ data: "000201..." });
    expect(decodeQrFromImageData(new Uint8ClampedArray(16), 2, 2)).toBe("000201...");
    jsqrMock.mockReturnValueOnce(null);
    expect(decodeQrFromImageData(new Uint8ClampedArray(16), 2, 2)).toBeNull();
  });

  it("hints to pick an image when camera is denied", async () => {
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockRejectedValue(new DOMException("x", "NotAllowedError")) },
      configurable: true,
    });
    expect(await openQrCamera()).toEqual({ status: "denied", hintVi: CAMERA_DENIED_HINT_VI });
  });
});

describe("ocr", () => {
  beforeEach(async () => {
    await terminateOcrWorker();
    tessMock.createWorker.mockReset();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 404 })));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("creates the vie worker lazily and reuses it", async () => {
    const worker = {
      recognize: vi.fn(async () => ({ data: { text: "xin chào" } })),
      terminate: vi.fn(async () => undefined),
    };
    tessMock.createWorker.mockResolvedValue(worker);
    expect(tessMock.createWorker).not.toHaveBeenCalled();
    expect(await recognizeText(new Blob(["x"]))).toBe("xin chào");
    await getOcrWorker();
    await recognizeText("y");
    expect(tessMock.createWorker).toHaveBeenCalledTimes(1);
    expect(tessMock.createWorker.mock.calls[0]?.[0]).toBe("vie");
  });
});
