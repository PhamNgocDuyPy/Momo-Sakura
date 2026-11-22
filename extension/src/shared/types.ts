// Reduced mirror of backend/guardian/schemas/api_models.py (CheckResponse, FlowBStage2Event,
// UiHints) and schemas/verdict.py (GuardianVerdict). Only fields the extension reads.

export type DecisionTier = "ALLOW" | "SOFT_FRICTION" | "HARD_HOLD";
export const DECISION_TIERS: readonly DecisionTier[] = ["ALLOW", "SOFT_FRICTION", "HARD_HOLD"];

export type ExtensionOrigin = "EXTENSION_SELECTION" | "EXTENSION_PAGE_TEXT";

export interface GuardianVerdict {
  decision_tier: DecisionTier;
  reason_codes: string[];
  evidence_bullets: string[];
  system2_check_questions: string[];
  cooling_off_seconds: number;
}

export interface UiHints {
  calm_shield: boolean;
  hotline: string | null;
}

export interface CheckResponse {
  request_id: string;
  verdict_id: string;
  channel: string;
  verdict: GuardianVerdict;
  ui_hints: UiHints;
}

export interface Stage2Event {
  event: "stage2";
  request_id: string;
  provisional_tier: DecisionTier;
  provisional_reason_codes: string[];
  red_alert: boolean;
}

export interface FinalEvent {
  event: "final";
  response: CheckResponse;
}

/** Error body of the backend: `{error, message_vi}`. */
export interface ErrorEvent {
  event: "error";
  error: string;
  message_vi: string;
}

export type StreamEvent = Stage2Event | FinalEvent | ErrorEvent;

/** Request body of POST /api/flow-b/check (FlowBCheckRequest). */
export interface FlowBCheckRequest {
  content: { origin: ExtensionOrigin; text: string };
  mode: "GENERAL";
  explicit_consent_flag: false;
}

// ---- messages between content script and service worker (port "guardian-check") ----

export const CHECK_PORT_NAME = "guardian-check";

export interface CheckRequestMessage {
  type: "check";
  text: string;
  origin: ExtensionOrigin;
}

export type BackgroundMessage =
  | { type: "stage2"; event: Stage2Event }
  | { type: "final"; response: CheckResponse }
  | { type: "error"; message_vi: string };

/** One-shot message from the service worker (menu / shortcut) to the content script. */
export interface TriggerMessage {
  type: "guardian-trigger";
  /** Text from the context menu's `selectionText`, when available. */
  selectionText?: string;
}