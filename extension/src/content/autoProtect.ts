// "Tự động bảo vệ": watches new chat messages on the current page, scores them locally with
// localScreen.ts and attaches a small "Guardian: nên kiểm tra" chip next to flagged ones.
// Nothing is sent anywhere until the user clicks a chip.
import { HOST_TAG, keepTail } from "./capture";
import { screenMessage } from "./localScreen";

export const CHIP_TAG = "momo-guardian-chip";
export const CHIP_LABEL = "Guardian: nên kiểm tra";
export const MAX_CHIPS = 20;
export const MAX_MESSAGE_CHARS = 2000;
export const MIN_MESSAGE_CHARS = 8;
export const DEBOUNCE_MS = 300;
const MAX_ELEMENTS_PER_BATCH = 5000;
const LIST_SELECTOR = "nav, aside, [role=navigation], [role=complementary], [role=listbox]";

const SKIP_TAGS = new Set([
  "SCRIPT",
  "STYLE",
  "NOSCRIPT",
  "TEMPLATE",
  "INPUT",
  "TEXTAREA",
  "SELECT",
  "OPTION",
  "SVG",
  "CANVAS",
  "IFRAME",
  "HEAD",
  "CODE",
  "PRE",
  HOST_TAG.toUpperCase(),
  CHIP_TAG.toUpperCase(),
]);

export interface AutoProtectOptions {
  /** Called with exactly the flagged message's text when the user clicks its chip. */
  onCheck: (text: string) => void;
  doc?: Document;
  debounceMs?: number;
  maxChips?: number;
  /** Whether an element is on screen; defaults to a viewport intersection test. */
  isVisible?: (el: Element) => boolean;
}

export interface AutoProtect {
  stop: () => void;
  /** Number of chips currently attached. */
  chipCount: () => number;
}

function normalizeText(s: string): string {
  return s.replace(/\s+/g, " ").trim();
}

export const TIME_ONLY =
  /^(?:\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]m)?|\d{1,3}\s?(?:phút|giờ|ngày|p|h)(?:\s+trước)?|hôm qua|hôm nay|thứ\s?(?:[2-7]|hai|ba|tư|năm|sáu|bảy)|chủ nhật|\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?)$/i;

/** Visible message text: text nodes joined by spaces, minus bare timestamps ("09:12") and ignored subtrees. */
export function messageText(el: Element): string {
  const parts: string[] = [];
  const walk = (n: Node): void => {
    for (const c of Array.from(n.childNodes)) {
      if (c.nodeType === Node.TEXT_NODE) {
        const s = normalizeText(c.nodeValue ?? "");
        if (s && !TIME_ONLY.test(s)) parts.push(s);
      } else if (c.nodeType === Node.ELEMENT_NODE && !isIgnored(c as Element)) {
        walk(c);
      }
    }
  };
  walk(el);
  return parts.join(" ");
}

export function isIgnored(el: Element): boolean {
  if (SKIP_TAGS.has(el.tagName.toUpperCase())) return true;
  if (el.hasAttribute("hidden") || el.getAttribute("aria-hidden") === "true") return true;
  const ce = el.getAttribute("contenteditable");
  return ce !== null && ce.toLowerCase() !== "false";
}

export function insideIgnored(el: Element): boolean {
  for (let n: Element | null = el; n; n = n.parentElement) if (isIgnored(n)) return true;
  return false;
}

/** Text the element itself owns (direct text nodes), used to find the innermost message block. */
export function directTextLength(el: Element): number {
  let len = 0;
  for (const c of Array.from(el.childNodes)) if (c.nodeType === Node.TEXT_NODE) len += normalizeText(c.nodeValue ?? "").length;
  return len;
}

function defaultIsVisible(el: Element): boolean {
  const r = el.getBoundingClientRect();
  if (r.width <= 0 && r.height <= 0) return false;
  const win = el.ownerDocument.defaultView;
  const vh = win?.innerHeight ?? 0;
  const vw = win?.innerWidth ?? 0;
  return r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw;
}

function makeChip(doc: Document, onClick: () => void): HTMLElement {
  const host = doc.createElement(CHIP_TAG);
  host.style.cssText = "all: initial; display: block; margin: 2px 0; line-height: 1;";
  const shadow = host.attachShadow({ mode: "open" });
  const style = doc.createElement("style");
  style.textContent = `
    button { all: initial; box-sizing: border-box; display: inline-flex; align-items: center; gap: 4px;
      cursor: pointer; font: 600 11px/1.2 system-ui, "Segoe UI", Roboto, Arial, sans-serif;
      color: #92400e; background: #fef3c7; border: 1px solid #f59e0b; border-radius: 999px; padding: 3px 8px; }
    button:hover { background: #fde68a; }
    button:focus-visible { outline: 2px solid #b45309; outline-offset: 1px; }
  `;
  const btn = doc.createElement("button");
  btn.type = "button";
  btn.setAttribute("data-testid", "guardian-chip");
  btn.title = "Tin nhắn có dấu hiệu cần xem lại. Bấm để Guardian kiểm tra (đây chưa phải kết luận).";
  btn.textContent = CHIP_LABEL;
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    onClick();
  });
  shadow.append(style, btn);
  return host;
}

export function startAutoProtect(options: AutoProtectOptions): AutoProtect {
  const doc = options.doc ?? document;
  const win = doc.defaultView;
  const debounceMs = options.debounceMs ?? DEBOUNCE_MS;
  const maxChips = options.maxChips ?? MAX_CHIPS;
  const isVisible = options.isVisible ?? defaultIsVisible;

  const chips: { host: HTMLElement; target: Element }[] = [];
  const seenText = new Set<string>();
  const pending = new Set<Node>();
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  const liveChips = (): number => {
    for (let i = chips.length - 1; i >= 0; i--) {
      const c = chips[i]!;
      if (!c.host.isConnected) {
        chips.splice(i, 1);
        seenText.delete((c.host as HTMLElement & { _key?: string })._key ?? "");
      }
    }
    return chips.length;
  };

  const alreadyCovered = (el: Element): boolean =>
    chips.some((c) => c.target === el || c.target.contains(el) || el.contains(c.target));

  const consider = (el: Element, requireVisible: boolean): void => {
    if (liveChips() >= maxChips) return;
    if (el.closest(`${HOST_TAG}, ${CHIP_TAG}`) || insideIgnored(el)) return;
    // Conversation lists and navigation only hold previews of other chats, not the open conversation.
    if (el.closest(LIST_SELECTOR)) return;
    if (directTextLength(el) < MIN_MESSAGE_CHARS) return;
    const text = messageText(el);
    if (text.length < MIN_MESSAGE_CHARS || text.length > MAX_MESSAGE_CHARS) return;
    if (alreadyCovered(el) || seenText.has(text)) return;
    if (requireVisible && !isVisible(el)) return;
    if (!screenMessage(text).flagged) return;
    const message = keepTail(text);
    const host = makeChip(doc, () => options.onCheck(message));
    (host as HTMLElement & { _key?: string })._key = text;
    el.insertAdjacentElement("afterend", host);
    chips.push({ host, target: el });
    seenText.add(text);
  };

  const scanSubtree = (root: Element, requireVisible: boolean): void => {
    // Outer blocks first (so a whole message wins over a styled word inside it). On huge pages keep
    // the tail of the document, where the newest chat messages are.
    const all = [root, ...Array.from(root.querySelectorAll("*")).slice(-MAX_ELEMENTS_PER_BATCH)];
    for (const el of all) consider(el, requireVisible);
  };

  const flush = (): void => {
    timer = null;
    if (stopped) return;
    const nodes = Array.from(pending);
    pending.clear();
    for (const n of nodes) {
      if (!n.isConnected) continue;
      const el = n.nodeType === Node.ELEMENT_NODE ? (n as Element) : n.parentElement;
      if (el) scanSubtree(el, false);
    }
  };

  const observer = new (win?.MutationObserver ?? MutationObserver)((records) => {
    for (const r of records) {
      for (const n of Array.from(r.addedNodes)) {
        if (n.nodeType !== Node.ELEMENT_NODE && n.nodeType !== Node.TEXT_NODE) continue;
        if (n.nodeType === Node.ELEMENT_NODE) {
          const tag = (n as Element).tagName.toUpperCase();
          if (tag === HOST_TAG.toUpperCase() || tag === CHIP_TAG.toUpperCase()) continue;
        }
        pending.add(n);
      }
    }
    if (pending.size > 0 && timer === null) timer = setTimeout(flush, debounceMs);
  });
  if (doc.body) observer.observe(doc.body, { childList: true, subtree: true });

  // One pass over what is already on screen when the switch is turned on.
  if (doc.body) scanSubtree(doc.body, true);

  return {
    chipCount: liveChips,
    stop: () => {
      stopped = true;
      observer.disconnect();
      if (timer !== null) clearTimeout(timer);
      timer = null;
      pending.clear();
      for (const c of chips) c.host.remove();
      chips.length = 0;
      seenText.clear();
    },
  };
}
