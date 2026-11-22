import type { CheckResponse } from "../../src/types/api";

export function makeCheck(over: Partial<CheckResponse> = {}): CheckResponse {
  return {
    request_id: "req_1",
    verdict_id: "v_1",
    channel: "FLOW_B",
    verdict: {
      decision_tier: "ALLOW",
      reason_codes: [],
      evidence_bullets: ["Bằng chứng mẫu"],
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
    stage_timings_ms: { stage2: 5, stage3: 100, total: 120 },
    latency_ms: 120,
    ...over,
  };
}
