import { describe, expect, it } from "vitest";
import { NdjsonError, NdjsonParser, parseNdjsonLine, readNdjson } from "../src/shared/ndjson";
import { finalLine, makeResponse, stage2Line } from "./helpers";

describe("parseNdjsonLine", () => {
  it("ignores blank lines", () => {
    expect(parseNdjsonLine("  ")).toBeNull();
  });

  it("parses stage2", () => {
    expect(parseNdjsonLine(stage2Line("HARD_HOLD", true))).toEqual({
      event: "stage2",
      request_id: "r1",
      provisional_tier: "HARD_HOLD",
      provisional_reason_codes: ["RC_AUTHORITY_COERCION"],
      red_alert: true,
    });
  });

  it("parses final and fills defaults", () => {
    const ev = parseNdjsonLine(
      JSON.stringify({
        event: "final",
        response: { request_id: "r", verdict: { decision_tier: "ALLOW", reason_codes: ["RC_NO_SCAM_SIGNAL_FOUND"] } },
      }),
    );
    expect(ev).toMatchObject({
      event: "final",
      response: {
        verdict: { decision_tier: "ALLOW", evidence_bullets: [], system2_check_questions: [], cooling_off_seconds: 0 },
        ui_hints: { calm_shield: false, hotline: null },
      },
    });
  });

  it("parses an error body", () => {
    expect(parseNdjsonLine('{"error":"X","message_vi":"Lỗi"}')).toEqual({ event: "error", error: "X", message_vi: "Lỗi" });
  });

  it.each([
    "not json",
    "[1]",
    '{"event":"stage2","provisional_tier":"MAYBE"}',
    '{"event":"final","response":{"verdict":{"decision_tier":"SAFE"}}}',
    '{"event":"other"}',
  ])("rejects %s", (line) => {
    expect(() => parseNdjsonLine(line)).toThrow(NdjsonError);
  });
});

describe("NdjsonParser", () => {
  it("reassembles lines split across chunks", () => {
    const p = new NdjsonParser();
    const text = `${stage2Line()}\n${finalLine(makeResponse())}\n`;
    const events = [...p.push(text.slice(0, 30)), ...p.push(text.slice(30, 120)), ...p.push(text.slice(120)), ...p.flush()];
    expect(events.map((e) => e.event)).toEqual(["stage2", "final"]);
  });

  it("flushes a last line without trailing newline", () => {
    const p = new NdjsonParser();
    expect(p.push(stage2Line())).toEqual([]);
    expect(p.flush().map((e) => e.event)).toEqual(["stage2"]);
  });
});

describe("readNdjson", () => {
  it("yields events from a streamed body, with multi-byte characters split across chunks", async () => {
    const bytes = new TextEncoder().encode(`${stage2Line()}\n${finalLine()}\n`);
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        for (let i = 0; i < bytes.length; i += 7) c.enqueue(bytes.slice(i, i + 7));
        c.close();
      },
    });
    const events = [];
    for await (const e of readNdjson(body)) events.push(e);
    expect(events.map((e) => e.event)).toEqual(["stage2", "final"]);
    const final = events[1];
    expect(final.event === "final" && final.response.verdict.evidence_bullets[0]).toContain("công an");
  });
});