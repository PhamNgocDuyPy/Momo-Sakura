import { describe, expect, it, beforeEach } from "vitest";
import vectors from "../../fixtures/amount_vectors.json";
import { findAmounts, parseAmount } from "../src/lib/amount";
import { getSessionId } from "../src/services/session";
import {
  guardianReducer,
  initialGuardianState,
} from "../src/state/guardianStore";
import type { CheckResponse, DecisionTier } from "../src/types/api";

describe("amount", () => {
  // Round-trip property and format vectors live in amount.property.test.ts.
  it("matches shared slang vectors", () => {
    for (const v of vectors.slang) expect(parseAmount(v.text)).toBe(v.value);
  });

  it("ignores bare account numbers when scanning", () => {
    expect(findAmounts("ck 2 lít vào stk 0123456789")).toEqual([200000]);
  });
});

describe("session", () => {
  beforeEach(() => sessionStorage.clear());
  it("creates a stable uuid", () => {
    const a = getSessionId();
    expect(a).toMatch(/^[0-9a-f-]{36}$/);
    expect(getSessionId()).toBe(a);
  });
});

function response(tier: DecisionTier, fromDemo = false): CheckResponse {
  return {
    request_id: "r",
    verdict_id: "v",
    channel: "FLOW_A",
    verdict: {
      decision_tier: tier,
      reason_codes: [],
      evidence_bullets: [],
      system2_check_questions: [],
      cooling_off_seconds: 0,
      requires_user_account_confirm: false,
      allow_fast_unblock: false,
    },
    ui_hints: {
      calm_shield: false,
      show_context_elicitation: false,
      safe_payment_tips: false,
      show_transfer_now: false,
      handoff_allowed: true,
      missing_fields: [],
      trusted_contacts: [],
      hotline: null,
    },
    qr: null,
    prefill: null,
    name_confirmation: null,
    signals: { scam_playbook: null, manipulation_cues: [], url_flags: [], prefilter_score: null },
    sandbox_sources: [],
    trace: [],
    rules_fired: [],
    stop_codes: [],
    stage_timings_ms: { stage2: null, stage3: null, total: null },
    latency_ms: 1,
    from_demo: fromDemo,
  };
}

describe("guardianReducer", () => {
  it("counts verdicts but skips demo ones", () => {
    let s = guardianReducer(initialGuardianState, { type: "VERDICT_RECEIVED", response: response("HARD_HOLD") });
    s = guardianReducer(s, { type: "VERDICT_RECEIVED", response: response("ALLOW", true) });
    expect(s.shieldStats).toEqual({ checks: 1, ALLOW: 0, SOFT_FRICTION: 0, HARD_HOLD: 1 });
    expect(s.lastVerdict?.verdict.decision_tier).toBe("ALLOW");
  });

  it("opens and closes the popup", () => {
    let s = guardianReducer(initialGuardianState, { type: "OPEN_POPUP", mode: "SHOP" });
    expect(s.popup.open).toBe(true);
    expect(s.popup.mode).toBe("SHOP");
    s = guardianReducer(s, { type: "CLOSE_POPUP" });
    expect(s.popup.open).toBe(false);
  });
});
