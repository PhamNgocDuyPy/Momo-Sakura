import type { CheckResponse, DecisionTier } from "../src/shared/types";

type Store = Record<string, unknown>;

/** Installs an in-memory `chrome.storage.local` and returns the backing store. */
export function installChromeStorage(initial: Store = {}): Store {
  const store: Store = { ...initial };
  const local = {
    async get(keys?: string | string[] | Store | null): Promise<Store> {
      if (keys == null) return { ...store };
      if (typeof keys === "string") return keys in store ? { [keys]: store[keys] } : {};
      if (Array.isArray(keys)) return Object.fromEntries(keys.filter((k) => k in store).map((k) => [k, store[k]]));
      return Object.fromEntries(Object.keys(keys).map((k) => [k, k in store ? store[k] : keys[k]]));
    },
    async set(items: Store): Promise<void> {
      Object.assign(store, items);
    },
  };
  (globalThis as unknown as { chrome: unknown }).chrome = { storage: { local } };
  return store;
}

export interface FakePort {
  name: string;
  postMessage: ReturnType<typeof vi.fn>;
  onMessage: { addListener: (fn: (m: unknown) => void) => void };
  onDisconnect: { addListener: (fn: () => void) => void };
  receive: (m: unknown) => void;
  /** Delivers a message to listeners registered with `port.onMessage` (content-script side). */
  receiveFromBackground: (m: unknown) => void;
  disconnect: () => void;
  sent: () => unknown[];
}

export function makeFakePort(name = "guardian-check"): FakePort {
  const msg: ((m: unknown) => void)[] = [];
  const disc: (() => void)[] = [];
  const postMessage = vi.fn();
  return {
    name,
    postMessage,
    onMessage: { addListener: (fn) => void msg.push(fn) },
    onDisconnect: { addListener: (fn) => void disc.push(fn) },
    receive: (m) => msg.forEach((f) => f(m)),
    receiveFromBackground: (m) => msg.forEach((f) => f(m)),
    disconnect: () => disc.forEach((f) => f()),
    sent: () => postMessage.mock.calls.map((c) => c[0] as unknown),
  };
}

export function stage2Line(tier: DecisionTier = "HARD_HOLD", redAlert = true): string {
  return JSON.stringify({
    event: "stage2",
    request_id: "r1",
    provisional_tier: tier,
    provisional_reason_codes: ["RC_AUTHORITY_COERCION"],
    red_alert: redAlert,
    urls: [],
    prefilter_score: 0.4,
    elapsed_ms: 20,
  });
}

export function makeResponse(overrides: Partial<CheckResponse> = {}): CheckResponse {
  return {
    request_id: "r1",
    verdict_id: "v1",
    channel: "FLOW_B",
    verdict: {
      decision_tier: "HARD_HOLD",
      reason_codes: ["RC_AUTHORITY_COERCION"],
      evidence_bullets: ["Người gửi tự xưng là công an và đòi chuyển tiền gấp."],
      system2_check_questions: ["Cơ quan chức năng có bao giờ yêu cầu chuyển tiền qua tin nhắn không?"],
      cooling_off_seconds: 60,
    },
    ui_hints: { calm_shield: false, hotline: null },
    ...overrides,
  };
}

export function finalLine(response: CheckResponse = makeResponse()): string {
  return JSON.stringify({ event: "final", response });
}

export function ndjsonResponse(lines: string[], status = 200): Response {
  return new Response(lines.map((l) => `${l}\n`).join(""), {
    status,
    headers: { "Content-Type": "application/x-ndjson" },
  });
}