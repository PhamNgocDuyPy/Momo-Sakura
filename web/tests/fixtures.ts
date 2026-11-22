import type { CheckResponse, DecisionTier, UiHints } from "../src/types/api";

export function makeCheckResponse(
  tier: DecisionTier = "ALLOW",
  hints: Partial<UiHints> = {},
  over: Partial<CheckResponse> = {},
): CheckResponse {
  return {
    request_id: "req_1",
    verdict_id: "v_1",
    channel: "FLOW_B",
    verdict: {
      decision_tier: tier,
      reason_codes: [],
      evidence_bullets: ["Bằng chứng 1", "Bằng chứng 2", "Bằng chứng 3", "Bằng chứng 4", "Bằng chứng 5"],
      system2_check_questions: [],
      cooling_off_seconds: 15,
      requires_user_account_confirm: false,
      allow_fast_unblock: false,
    },
    ui_hints: {
      calm_shield: false,
      show_context_elicitation: false,
      safe_payment_tips: false,
      show_transfer_now: false,
      handoff_allowed: tier !== "HARD_HOLD",
      missing_fields: [],
      trusted_contacts: [],
      hotline: null,
      ...hints,
    },
    qr: null,
    prefill: {
      bank_bin: "970436",
      account_number: "0123456789",
      amount_vnd: 200000,
      memo: null,
      source_integrity_for_flow_a: "OCR_UNCONFIRMED",
    },
    name_confirmation: null,
    signals: { scam_playbook: null, manipulation_cues: [], url_flags: [], prefilter_score: null },
    sandbox_sources: [],
    trace: [],
    rules_fired: [],
    stop_codes: [],
    stage_timings_ms: { stage2: 5, stage3: 100, total: 120 },
    latency_ms: 120,
    ...over,
  };
}
