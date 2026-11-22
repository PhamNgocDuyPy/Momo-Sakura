// Per-domain "Tự động bảo vệ" switch, stored in chrome.storage.local as { [hostname]: true }.
// Off by default: a host without an entry is off. Only hostnames are stored, never page content.

export const AUTO_PROTECT_KEY = "guardianAutoProtect";

export type AutoProtectMap = Record<string, true>;

/** Lower-cases and trims a hostname; accepts a pasted URL. Returns null when it is not a usable host. */
export function normalizeHost(input: string): string | null {
  let s = input.trim().toLowerCase();
  if (!s) return null;
  if (s.includes("://")) {
    try {
      s = new URL(s).hostname;
    } catch {
      return null;
    }
  }
  s = s.replace(/\/.*$/, "").replace(/:\d+$/, "").replace(/^\.+|\.+$/g, "");
  return /^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$/.test(s) ? s : null;
}

function readMap(raw: unknown): AutoProtectMap {
  const out: AutoProtectMap = {};
  if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) if (v === true) out[k] = true;
  }
  return out;
}

export async function getAutoProtectMap(): Promise<AutoProtectMap> {
  const stored = await chrome.storage.local.get(AUTO_PROTECT_KEY);
  return readMap(stored[AUTO_PROTECT_KEY]);
}

export async function isAutoProtectEnabled(host: string): Promise<boolean> {
  const h = normalizeHost(host);
  if (!h) return false;
  return (await getAutoProtectMap())[h] === true;
}

export async function setAutoProtect(host: string, enabled: boolean): Promise<void> {
  const h = normalizeHost(host);
  if (!h) throw new Error("Tên miền không hợp lệ.");
  const map = await getAutoProtectMap();
  if (enabled) map[h] = true;
  else delete map[h];
  await chrome.storage.local.set({ [AUTO_PROTECT_KEY]: map });
}

/** Calls `cb` with the new map whenever it changes (any tab, options page). Returns an unsubscribe. */
export function onAutoProtectChange(cb: (map: AutoProtectMap) => void): () => void {
  const events = chrome.storage?.onChanged;
  if (!events) return () => undefined;
  const listener = (changes: Record<string, { newValue?: unknown }>, area: string): void => {
    if (area !== "local" || !(AUTO_PROTECT_KEY in changes)) return;
    cb(readMap(changes[AUTO_PROTECT_KEY]?.newValue));
  };
  events.addListener(listener);
  return () => events.removeListener(listener);
}
