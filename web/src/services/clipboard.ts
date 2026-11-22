import { createClipboardDedupe, type ClipboardDedupe } from "../lib/clipboardDedupe";

export const CLIPBOARD_OPTIN_KEY = "guardian.clipboard.optin";
export const CLIPBOARD_DENIED_MESSAGE_VI =
  "Trình duyệt chưa cho phép đọc clipboard. Bạn hãy dán nội dung vào ô bên dưới.";

export const CLIPBOARD_EMPTY_MESSAGE_VI =
  "Clipboard đang trống. Bạn hãy sao chép tin nhắn cần kiểm tra rồi bấm lại, hoặc dán vào ô bên dưới.";

export type ClipboardEventKind = "popup_open" | "tab_visible";

export type ClipboardReadResult =
  | { status: "text"; text: string }
  | { status: "duplicate" }
  | { status: "empty" }
  | { status: "disabled" }
  | { status: "denied"; messageVi: string }
  | { status: "unsupported" };

export function isClipboardOptedIn(): boolean {
  try {
    return localStorage.getItem(CLIPBOARD_OPTIN_KEY) === "1";
  } catch {
    return false;
  }
}

export function setClipboardOptIn(enabled: boolean): void {
  try {
    if (enabled) localStorage.setItem(CLIPBOARD_OPTIN_KEY, "1");
    else localStorage.removeItem(CLIPBOARD_OPTIN_KEY);
  } catch {
    /* storage unavailable: opt-in stays off */
  }
}

const defaultDedupe: ClipboardDedupe = createClipboardDedupe();

/**
 * Read the clipboard exactly once for a `popup_open` / `tab_visible` event.
 * Does nothing when the opt-in is off. Never polls.
 */
export async function readClipboardOnce(
  _event: ClipboardEventKind,
  dedupe: ClipboardDedupe = defaultDedupe,
): Promise<ClipboardReadResult> {
  if (!isClipboardOptedIn()) return { status: "disabled" };
  const clip = typeof navigator === "undefined" ? undefined : navigator.clipboard;
  if (!clip || typeof clip.readText !== "function") return { status: "unsupported" };
  let text: string;
  try {
    text = await clip.readText();
  } catch {
    return { status: "denied", messageVi: CLIPBOARD_DENIED_MESSAGE_VI };
  }
  if (text.trim().length === 0) return { status: "empty" };
  if (!(await dedupe.accept(text))) return { status: "duplicate" };
  return { status: "text", text };
}

export function resetClipboardDedupe(): void {
  defaultDedupe.reset();
}

/**
 * Reads the clipboard once for an explicit tap on "Dán & kiểm tra". Call it synchronously inside
 * the click handler (user gesture). Ignores the auto-scan opt-in and the dedupe window because the
 * user asked for this check.
 */
export async function readClipboardOnDemand(): Promise<ClipboardReadResult> {
  const clip = typeof navigator === "undefined" ? undefined : navigator.clipboard;
  if (!clip || typeof clip.readText !== "function") return { status: "unsupported" };
  let text: string;
  try {
    text = await clip.readText();
  } catch {
    return { status: "denied", messageVi: CLIPBOARD_DENIED_MESSAGE_VI };
  }
  if (text.trim().length === 0) return { status: "empty" };
  return { status: "text", text };
}