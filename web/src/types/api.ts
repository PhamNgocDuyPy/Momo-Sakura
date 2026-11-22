// Types mirroring backend `schemas/api_models.py` and the API contracts in design.md.

export type DecisionTier = "ALLOW" | "SOFT_FRICTION" | "HARD_HOLD";
export type Channel = "FLOW_A" | "FLOW_B" | "FAST_UNBLOCK" | "CONTEXT" | "NAME_CONFIRM";
export type SourceIntegrity =
  | "USER_TYPED"
  | "VALID_VIETQR_CRC"
  | "OCR_CONFIRMED_BY_USER"
  | "OCR_UNCONFIRMED";
export type AccountOrigin = "TYPED" | "PASTE" | "CLIPBOARD" | "OCR" | "QR" | "SHARE" | "CONTACT";
export type ContentOrigin =
  | "PASTE"
  | "CLIPBOARD"
  | "OCR"
  | "QR_CAMERA"
  | "QR_IMAGE"
  | "SHARE_TARGET"
  | "CONTEXT_CHAT"
  | "EXTENSION_SELECTION"
  | "EXTENSION_PAGE_TEXT";
export type ContentMode = "GENERAL" | "SPLIT_BILL" | "SHOP" | "PROMO";
export type QrResult = "VALID_VIETQR" | "BAD_CRC" | "FOREIGN_OR_NON_VND" | "INVALID_FORMAT";
export type QrFlag = "UTF8_BYTE_FALLBACK" | "LEGACY_DEFAULT_SERVICE_CODE";

export interface GuardianVerdict {
  decision_tier: DecisionTier;
  reason_codes: string[];
  evidence_bullets: string[];
  system2_check_questions: string[];
  cooling_off_seconds: number;
  requires_user_account_confirm: boolean;
  allow_fast_unblock: boolean;
}

export interface TrustedContactRef {
  name: string;
  phone: string;
}

export interface UiHints {
  calm_shield: boolean;
  show_context_elicitation: boolean;
  safe_payment_tips: boolean;
  show_transfer_now: boolean;
  handoff_allowed: boolean;
  missing_fields: string[];
  trusted_contacts: TrustedContactRef[];
  hotline: string | null;
}

export interface Signals {
  scam_playbook: string | null;
  manipulation_cues: string[];
  url_flags: string[];
  prefilter_score: number | null;
}

export interface QrTag62 {
  purpose: string | null;
  bill_number: string | null;
  reference: string | null;
}

export interface QrFields {
  payload_format: string;
  poi_method: string;
  aid: string;
  bank_bin: string;
  bank_name: string | null;
  account_number: string;
  service_code: string;
  amount_vnd: number | null;
  currency: string;
  country: string;
  tag62: QrTag62 | null;
}

export interface QrVerifyResponse {
  result: QrResult;
  flags: QrFlag[];
  fields: Partial<QrFields> | null;
  crc: { expected: string; computed: string } | null;
}

export interface Prefill {
  bank_bin: string | null;
  bank_name?: string | null;
  account_number: string | null;
  amount_vnd: number | null;
  memo: string | null;
  account_origin?: AccountOrigin;
  source_integrity_for_flow_a: SourceIntegrity;
}

export interface NameConfirmation {
  pending_id: string;
  display_name: string | null;
  bank_name: string | null;
  account_digits_spaced: string;
  found: boolean;
  sandbox: boolean;
}

export interface TraceStep {
  seq: number;
  kind: "stage" | "tool" | "llm" | "rule";
  name: string;
  t_start_ms: number;
  duration_ms: number;
  status: "ok" | "skipped" | "aborted" | "denied" | "timeout" | "error";
  detail: Record<string, string | number | boolean | null>;
}

export interface RuleFiring {
  rule: string;
  trigger: string;
  effect: string;
  reason_code: string;
  stop_code?: string | null;
}

export interface StageTimings {
  stage2: number | null;
  stage3: number | null;
  total: number | null;
}

export interface ReceiptItem {
  name: string;
  quantity: number;
  unit_price_vnd: number;
}

export interface Extensions {
  receipt?: {
    items: ReceiptItem[];
    total_vnd: number | null;
    items_sum_vnd: number;
  } | null;
  listing?: {
    product_category: string;
    product_key: string | null;
    listed_price_vnd: number | null;
    reference_price_vnd: number | null;
    discount_percent: number | null;
    requires_deposit: boolean;
  } | null;
  promo?: {
    brand: string;
    promo_code: string | null;
    matched: boolean;
    official_promo: { title_vi: string; valid_to: string } | null;
  } | null;
}

export interface CheckResponse {
  request_id: string;
  verdict_id: string;
  channel: Channel;
  verdict: GuardianVerdict;
  ui_hints: UiHints;
  qr: QrVerifyResponse | null;
  prefill: Prefill | null;
  name_confirmation: NameConfirmation | null;
  extensions?: Extensions | null;
  signals: Signals;
  sandbox_sources: string[];
  trace: TraceStep[];
  rules_fired: RuleFiring[];
  stop_codes: string[];
  stage_timings_ms: StageTimings;
  latency_ms: number;
  /** Client-side marker: verdict came from the demo page and must not count in shield stats. */
  from_demo?: boolean;
}

export interface DebugOverrides {
  simulate_llm_delay_ms?: number;
  simulate_skip_qr_verify?: boolean;
  force_llm_output?: Record<string, unknown> | null;
  simulate_redactor_failure?: boolean;
}

export interface FlowACheckRequest {
  bank_bin: string;
  account_number: string;
  amount_vnd: number;
  memo?: string | null;
  source_integrity: SourceIntegrity;
  qr_payload?: string | null;
  confirmation_token?: string | null;
  origin_verdict_id?: string | null;
  client_time?: string;
  debug?: DebugOverrides | null;
}

export type FastUnblockPurpose =
  | "PAY_FAMILY"
  | "PAY_GOODS_SERVICES"
  | "PAY_RENT"
  | "TUITION"
  | "LOAN_REPAYMENT"
  | "BUSINESS_PAYMENT"
  | "OTHER";

export interface FastUnblockRequest {
  verdict_id: string;
  identity_check: { method: "SANDBOX_OTP"; code: string };
  purpose: FastUnblockPurpose;
}

export type ContextChoice = "IN_STORE" | "ONLINE_ORDER" | "URGENT_RELATIVE" | "AUTHORITY_REQUEST";

export interface ContextRequest {
  verdict_id: string;
  context: ContextChoice;
}

export interface LinkedTransaction {
  verdict_id: string;
  bank_bin: string;
  account_number: string;
  amount_vnd: number;
}

export interface FlowBContent {
  origin: ContentOrigin;
  text?: string | null;
  qr_payload?: string | null;
}

export interface FlowBCheckRequest {
  content: FlowBContent;
  mode: ContentMode;
  linked_transaction?: LinkedTransaction | null;
  explicit_consent_flag: boolean;
  client_time?: string;
  debug?: DebugOverrides | null;
}

export interface FlowBStage2Event {
  event: "stage2";
  request_id: string;
  provisional_tier: DecisionTier;
  provisional_reason_codes: string[];
  red_alert: boolean;
  qr: QrVerifyResponse | null;
  urls: UrlReport[];
  prefilter_score: number;
  recipient_risk: { simo_hit: boolean; gnn_mule_score: number; sandbox: boolean } | null;
  elapsed_ms: number;
}

export interface FlowBFinalEvent {
  event: "final";
  response: CheckResponse;
}

export type FlowBEvent = FlowBStage2Event | FlowBFinalEvent;

export interface UrlReport {
  domain: string;
  flags: string[];
}

export interface PrecheckResponse {
  redacted_text: string;
  redaction_counts: Record<string, number>;
  prompt_guard_cpu_score: number;
  urls: UrlReport[];
  hijack_detected: boolean;
  duration_ms: number;
}

export interface NameInquiryRequest {
  pending_id: string;
  bank_bin: string;
  account_number: string;
}

export interface NameConfirmRequest {
  pending_id: string;
  confirmed: boolean;
}

export interface NameConfirmResponse {
  confirmation_token?: string;
  source_integrity: SourceIntegrity;
  check: CheckResponse | null;
}

export interface HealthResponse {
  status: string;
  llm_provider: string;
  version: string;
  sandbox_now: string;
  debug: boolean;
}

export type BudgetStatus = "OK" | "WARNING" | "OVER";

export interface WalletSummary {
  as_of: string;
  month: string;
  sandbox: boolean;
  spending_by_category: { category: string; label_vi: string; total_vnd: number }[];
  budgets: {
    category: string;
    label_vi: string;
    limit_vnd: number;
    spent_vnd: number;
    percent_used: number;
    status: BudgetStatus;
  }[];
  recent_transactions: {
    id: string;
    at: string;
    direction: "IN" | "OUT";
    category: string;
    counterparty: string;
    amount_vnd: number;
  }[];
  bills: {
    provider_id: string;
    provider_name: string;
    period: string;
    amount_vnd: number;
    due_date: string;
    status: string;
  }[];
  subscriptions: {
    id: string;
    name: string;
    amount_vnd: number;
    renewal_date: string;
    last_used_at: string | null;
  }[];
  alerts: WalletAlert[];
  trusted_contacts: TrustedContactRef[];
  shield_stats: ShieldStats;
}

export type WalletAlert =
  | {
      type: "BILL_SPIKE";
      provider_id: string;
      current_vnd: number;
      avg3_vnd: number;
      increase_percent: number;
    }
  | {
      type: "RENEWAL_SOON";
      subscription_id: string;
      renewal_date: string;
      amount_vnd: number;
      days_left: number;
    }
  | { type: "UNUSED_SUBSCRIPTION"; subscription_id: string; days_since_last_use: number };

export interface ShieldStats {
  checks: number;
  ALLOW: number;
  SOFT_FRICTION: number;
  HARD_HOLD: number;
}

export interface QrVerifyRequest {
  payload: string;
}

export interface TransferCommitRequest {
  verdict_id: string;
  cooldown_completed: boolean;
  answered_questions: number;
}

export interface TransferCommitResponse {
  status: "SIMULATED_SENT";
  ledger_total_24h_vnd: number;
}

export interface QrEncodeRequest {
  purpose: "BANK_HANDOFF" | "SPLIT_BILL";
  verdict_id?: string;
  bank_bin: string;
  account_number: string;
  amount_vnd: number | null;
  memo?: string;
}

export interface QrEncodeResponse {
  payload: string;
  verify: { result: QrResult };
  deeplink: string | null;
}

export interface ApiErrorBody {
  error: string;
  message_vi?: string;
  details?: Record<string, unknown>;
}

// ---- Assistant (F2), spend (F6), split (F3). Mirror backend schemas/api_models.py.
export type SpendCategory = string;
export interface SpendSeriesPoint {
  bucket: string;
  value: number;
}
export interface SpendAnswerResult {
  type: "SPEND_ANSWER";
  value: number;
  unit: "VND" | "COUNT" | "PERCENT";
  previous_value: number | null;
  delta_percent: number | null;
  range: { from: string; to: string };
  series: SpendSeriesPoint[];
  bucket_unit: "DAY" | "WEEK";
  answer_vi: string;
}
export interface ResolvedContact {
  id: string;
  display_name: string;
  bank_bin: string;
  account_number: string;
}
export interface TransferResolutionResult {
  type: "TRANSFER_RESOLUTION";
  status: "RESOLVED" | "AMBIGUOUS" | "NOT_FOUND" | "NEEDS_AMOUNT";
  contact: ResolvedContact | null;
  candidates: ResolvedContact[];
  prefill: Prefill | null;
  message_vi: string;
}
export interface OpenModeResult {
  type: "OPEN_MODE";
  mode: ContentMode;
  message_vi: string;
}
export interface RephraseResult {
  type: "REPHRASE";
  message_vi: string;
  examples_vi: string[];
}
export type AssistantResult =
  | TransferResolutionResult
  | SpendAnswerResult
  | OpenModeResult
  | RephraseResult;
export interface AssistantCommandResponse {
  intent: string;
  result: AssistantResult;
  trace: TraceStep[];
}
export interface SplitParticipant {
  id: string;
  display_name: string;
}
export interface SplitAssignment {
  item_index: number;
  participant_ids: string[];
}
export interface SplitComputeRequest {
  items: ReceiptItem[];
  receipt_total_vnd: number;
  participants: SplitParticipant[];
  mode: "EQUAL" | "BY_ITEM";
  assignments?: SplitAssignment[] | null;
  payee?: "SELF";
  memo?: string;
}
export interface SplitShare {
  participant_id: string;
  amount_vnd: number;
  is_payee: boolean;
  qr_payload: string | null;
  qr_status: "VALID_VIETQR" | "SKIPPED_PAYEE" | "QR_ERROR";
}
export interface SplitComputeResponse {
  status: "OK" | "TOTAL_MISMATCH";
  total_vnd: number;
  items_sum_vnd: number;
  mismatch_vnd: number;
  shares: SplitShare[];
}

// --------------------------------------------------------------------------- eval / demo scenarios
export interface EvalScenarioCase {
  endpoint: string;
  request: Record<string, unknown>;
  expect: Record<string, unknown>;
  headers: Record<string, string>;
}

export interface EvalScenario {
  id: string;
  title_vi: string;
  description_vi: string;
  group: string;
  channel: string;
  requires_debug: boolean;
  cases: EvalScenarioCase[];
}
