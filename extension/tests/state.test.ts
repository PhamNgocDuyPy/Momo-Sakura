import { describe, expect, it } from "vitest";
import { checkReducer, type CheckState } from "../src/content/state";
import { makeResponse } from "./helpers";

describe("checkReducer", () => {
  it("goes scanning -> stage2 -> final", () => {
    let s: CheckState = { phase: "idle" };
    s = checkReducer(s, { type: "start", charCount: 5 });
    s = checkReducer(s, {
      type: "stage2",
      event: { event: "stage2", request_id: "r", provisional_tier: "SOFT_FRICTION", provisional_reason_codes: [], red_alert: false },
    });
    expect(s.phase).toBe("stage2");
    s = checkReducer(s, { type: "final", response: makeResponse() });
    expect(s.phase).toBe("final");
  });

  it("a late error (port disconnect) does not replace a delivered result", () => {
    let s: CheckState = checkReducer({ phase: "idle" }, { type: "start", charCount: 1 });
    s = checkReducer(s, { type: "final", response: makeResponse() });
    expect(checkReducer(s, { type: "error", message: "x" }).phase).toBe("final");
  });

  it("ignores events after close", () => {
    const idle = checkReducer(checkReducer({ phase: "idle" }, { type: "start", charCount: 1 }), { type: "close" });
    expect(checkReducer(idle, { type: "final", response: makeResponse() })).toEqual({ phase: "idle" });
    expect(checkReducer(idle, { type: "error", message: "x" })).toEqual({ phase: "idle" });
  });
});