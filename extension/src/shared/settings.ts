export const DEFAULT_BACKEND_URL = "http://localhost:8000";
export const DEFAULT_WEB_URL = "http://localhost:5173";

export const STORAGE_KEYS = {
  sessionId: "guardianSessionId",
  backendUrl: "guardianBackendUrl",
  webUrl: "guardianWebUrl",
  bubble: "guardianBubblePos",
} as const;

export interface Settings {
  sessionId: string;
  backendUrl: string;
  webUrl: string;
}

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function isUuidV4(value: unknown): value is string {
  return typeof value === "string" && UUID_V4.test(value);
}

export function generateUuidV4(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** Returns the URL without trailing slashes, or null unless it is a valid http(s) URL. */
export function normalizeUrl(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  try {
    const u = new URL(trimmed);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return `${u.origin}${u.pathname}`.replace(/\/+$/, "");
  } catch {
    return null;
  }
}

/** Reads settings; creates and stores a session id (uuid v4) on first use. */
export async function getSettings(): Promise<Settings> {
  const stored = await chrome.storage.local.get([
    STORAGE_KEYS.sessionId,
    STORAGE_KEYS.backendUrl,
    STORAGE_KEYS.webUrl,
  ]);
  let sessionId: unknown = stored[STORAGE_KEYS.sessionId];
  if (!isUuidV4(sessionId)) {
    sessionId = generateUuidV4();
    await chrome.storage.local.set({ [STORAGE_KEYS.sessionId]: sessionId });
  }
  const backend = normalizeUrl(String(stored[STORAGE_KEYS.backendUrl] ?? ""));
  const web = normalizeUrl(String(stored[STORAGE_KEYS.webUrl] ?? ""));
  return {
    sessionId: sessionId as string,
    backendUrl: backend ?? DEFAULT_BACKEND_URL,
    webUrl: web ?? DEFAULT_WEB_URL,
  };
}

/** Saves backend/web URLs. Throws when a URL is invalid. */
export async function saveUrls(backendUrl: string, webUrl: string): Promise<void> {
  const backend = normalizeUrl(backendUrl);
  const web = normalizeUrl(webUrl);
  if (!backend || !web) throw new Error("Địa chỉ không hợp lệ. Hãy nhập địa chỉ bắt đầu bằng http:// hoặc https://");
  await chrome.storage.local.set({ [STORAGE_KEYS.backendUrl]: backend, [STORAGE_KEYS.webUrl]: web });
}
/** Web app URL only (content script use: it must not create or read the session id). */
export async function getWebUrl(): Promise<string> {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.webUrl);
  return normalizeUrl(String(stored[STORAGE_KEYS.webUrl] ?? "")) ?? DEFAULT_WEB_URL;
}