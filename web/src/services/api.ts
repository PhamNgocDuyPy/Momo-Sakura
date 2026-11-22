import { getSessionId } from "./session";
import type {
  ApiErrorBody,
  AssistantCommandResponse,
  CheckResponse,
  ContextRequest,
  EvalScenario,
  FastUnblockRequest,
  FlowACheckRequest,
  HealthResponse,
  NameConfirmation,
  NameConfirmRequest,
  NameConfirmResponse,
  NameInquiryRequest,
  PrecheckResponse,
  QrEncodeRequest,
  QrEncodeResponse,
  QrVerifyResponse,
  SpendAnswerResult,
  SplitComputeRequest,
  SplitComputeResponse,
  TransferCommitRequest,
  TransferCommitResponse,
  WalletSummary,
} from "../types/api";

export const API_TIMEOUT_MS = 10_000;

export function apiBase(): string {
  const base = import.meta.env.VITE_API_BASE_URL;
  return typeof base === "string" && base.length > 0 ? base.replace(/\/$/, "") : "/api";
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly messageVi: string | undefined;
  readonly details: Record<string, unknown> | undefined;

  constructor(status: number, body: Partial<ApiErrorBody>) {
    super(body.error ?? `HTTP_${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = body.error ?? `HTTP_${status}`;
    this.messageVi = body.message_vi;
    this.details = body.details;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  timeoutMs?: number;
  signal?: AbortSignal;
}

/** Low-level fetch with session header and timeout. Used by the NDJSON client too. */
export async function apiFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? API_TIMEOUT_MS);
  const external = options.signal;
  const onAbort = (): void => controller.abort();
  external?.addEventListener("abort", onAbort);
  try {
    const headers: Record<string, string> = { "X-Guardian-Session": getSessionId() };
    const init: RequestInit = { method: options.method ?? "GET", headers, signal: controller.signal };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    return await fetch(`${apiBase()}${path}`, init);
  } finally {
    clearTimeout(timer);
    external?.removeEventListener("abort", onAbort);
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const res = await apiFetch(path, options);
  if (!res.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = (await res.json()) as Partial<ApiErrorBody>;
    } catch {
      body = {};
    }
    throw new ApiError(res.status, body);
  }
  return (await res.json()) as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body });
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  walletSummary: () => request<WalletSummary>("/wallet/summary"),
  verifyQr: (payload: string) => post<QrVerifyResponse>("/qr/verify", { payload }),
  encodeQr: (req: QrEncodeRequest) => post<QrEncodeResponse>("/qr/encode", req),
  flowACheck: (req: FlowACheckRequest) => post<CheckResponse>("/flow-a/check", req),
  fastUnblock: (req: FastUnblockRequest) => post<CheckResponse>("/flow-a/fast-unblock", req),
  context: (req: ContextRequest) => post<CheckResponse>("/flow-a/context", req),
  precheck: (text: string, clientTime?: string) =>
    post<PrecheckResponse>("/precheck", { text, client_time: clientTime }),
  nameInquiry: (req: NameInquiryRequest) => post<NameConfirmation>("/name/inquiry", req),
  nameConfirm: (req: NameConfirmRequest) => post<NameConfirmResponse>("/name/confirm", req),
  assistantCommand: (text: string) => post<AssistantCommandResponse>("/assistant/command", { text }),
  spendQuery: (req: { category?: string; period?: string; metric?: string }) =>
    post<SpendAnswerResult>("/spend/query", req),
  splitCompute: (req: SplitComputeRequest) => post<SplitComputeResponse>("/split/compute", req),
  transferCommit: (req: TransferCommitRequest) =>
    post<TransferCommitResponse>("/transfer/commit", req),
};

// --------------------------------------------------------------------------- eval / demo scenarios
export const evalApi = {
  scenarios: () => request<EvalScenario[]>("/eval/scenarios"),
  /** Calls a business endpoint exactly as a fixture case describes it ("POST /api/flow-a/check"). */
  runCase: (endpoint: string, body: Record<string, unknown>): Promise<unknown> => {
    const [method, rawPath = ""] = endpoint.split(" ");
    const path = rawPath.replace(/^\/api/, "");
    if (method === "GET") {
      const query = new URLSearchParams(
        Object.entries(body).map(([k, v]) => [k, String(v)] as [string, string]),
      ).toString();
      return request<unknown>(query ? `${path}${path.includes("?") ? "&" : "?"}${query}` : path);
    }
    return request<unknown>(path, { method: "POST", body });
  },
};
