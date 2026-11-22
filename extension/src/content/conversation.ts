// One-tap chat capture (Requirement 38): find the main conversation panel, read its latest messages
// and fall back to the viewport text (Requirement 35.4) when no panel is found. Pure DOM reads; it
// never touches the network and only runs after a user action.
import type { ExtensionOrigin } from "../shared/types";
import { TIME_ONLY, directTextLength, isIgnored, messageText } from "./autoProtect";
import {
  HOST_TAG,
  MAX_CAPTURE_CHARS,
  captureViewportText,
  getSelectionText,
  keepTail,
  type CaptureOptions,
  type RectLike,
} from "./capture";

export const MAX_MESSAGES = 15;
/** Minimum score for a candidate to count as the conversation panel. */
export const PANEL_THRESHOLD = 30;
const MIN_MESSAGE_BLOCKS = 3;
const MAX_MESSAGE_BLOCK_CHARS = 500;
const MIN_SHORT_RATIO = 0.6;
const MAX_SCAN_ELEMENTS = 20000;
const MAX_CANDIDATES = 30;

export type CaptureSource = "panel" | "viewport" | "selection";

export interface ChatCapture {
  text: string;
  messages: string[];
  source: CaptureSource;
  origin: ExtensionOrigin;
}

export interface Viewport {
  width: number;
  height: number;
}

export interface PanelOptions {
  viewport?: Viewport;
  /** Bounding rect of an element; defaults to getBoundingClientRect. */
  elementRect?: (el: Element) => RectLike;
}

const NAV_SELECTOR =
  "nav, aside, header, footer, [role=navigation], [role=complementary], [role=banner], [role=contentinfo], [role=search], [role=listbox], [role=menu], [role=tablist], [role=toolbar]";
const EDITABLE_SELECTOR = "input, textarea, select, [contenteditable]:not([contenteditable=false])";
const INTERACTIVE_SELECTOR = "a[href], button, [role=option], [role=button], [role=link], [role=tab], [role=menuitem]";
const AVATAR_SELECTOR = "img, [class*=avatar i], [data-avatar]";

function rectFn(options: PanelOptions): (el: Element) => RectLike {
  return options.elementRect ?? ((el) => el.getBoundingClientRect());
}

function viewportOf(doc: Document, options: PanelOptions): Viewport {
  const win = doc.defaultView;
  return options.viewport ?? { width: win?.innerWidth ?? 0, height: win?.innerHeight ?? 0 };
}

function intersect(a: RectLike, b: RectLike): RectLike | null {
  const left = Math.max(a.left, b.left);
  const top = Math.max(a.top, b.top);
  const right = Math.min(a.right, b.right);
  const bottom = Math.min(a.bottom, b.bottom);
  if (right <= left || bottom <= top) return null;
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}

function viewportRect(vp: Viewport): RectLike {
  return { left: 0, top: 0, right: vp.width, bottom: vp.height, width: vp.width, height: vp.height };
}

function isEditable(el: Element): boolean {
  return el.matches(EDITABLE_SELECTOR);
}

function overflowY(el: Element): string {
  const win = el.ownerDocument.defaultView;
  const computed = win?.getComputedStyle(el).overflowY ?? "";
  return computed || (el as HTMLElement).style?.overflowY || "";
}

function isScrollable(el: Element): boolean {
  if (el.scrollHeight <= el.clientHeight) return false;
  const o = overflowY(el);
  return o === "auto" || o === "scroll";
}

function isLogLike(el: Element): boolean {
  const live = el.getAttribute("aria-live");
  return el.getAttribute("role") === "log" || live === "polite" || live === "assertive";
}

function isStyledHidden(el: Element): boolean {
  const win = el.ownerDocument.defaultView;
  if (!win) return false;
  const s = win.getComputedStyle(el);
  return s.display === "none" || s.visibility === "hidden";
}

/**
 * Message-like blocks inside `panel`, in DOM order: the outermost element that owns visible text
 * (so a bubble wins over the span inside it). Skips timestamps, inputs, hidden nodes and the
 * Guardian host. A block must be on screen and inside the panel's own rectangle.
 */
export function extractPanelMessages(panel: Element, doc: Document = panel.ownerDocument, options: PanelOptions = {}): string[] {
  const rectOf = rectFn(options);
  const vpRect = viewportRect(viewportOf(doc, options));
  const clip = intersect(rectOf(panel), vpRect);
  if (!clip) return [];
  const out: string[] = [];
  const visit = (el: Element): void => {
    if (el.matches(AVATAR_SELECTOR) || isIgnored(el) || el.tagName.toUpperCase() === HOST_TAG.toUpperCase() || isStyledHidden(el)) return;
    if (directTextLength(el) > 0) {
      const text = messageText(el);
      if (text && !TIME_ONLY.test(text)) {
        const r = rectOf(el);
        if ((r.width > 0 || r.height > 0) && intersect(r, clip)) out.push(text);
      }
      return;
    }
    for (const child of Array.from(el.children)) visit(child);
  };
  if (panel.closest(HOST_TAG)) return [];
  for (const child of Array.from(panel.children)) visit(child);
  return out;
}

interface Scored {
  el: Element;
  score: number;
  messages: string[];
}

function scoreCandidate(el: Element, doc: Document, vp: Viewport, options: PanelOptions): Scored | null {
  const rectOf = rectFn(options);
  if (isEditable(el) || el.closest(HOST_TAG) || isIgnored(el)) return null;
  const visibleRect = intersect(rectOf(el), viewportRect(vp));
  if (!visibleRect) return null;
  const messages = extractPanelMessages(el, doc, options);
  const short = messages.filter((m) => m.length <= MAX_MESSAGE_BLOCK_CHARS).length;
  if (messages.length < MIN_MESSAGE_BLOCKS || short / messages.length < MIN_SHORT_RATIO) return null;

  const vpArea = Math.max(vp.width * vp.height, 1);
  let score = (visibleRect.width * visibleRect.height * 30) / vpArea;
  const cx = (visibleRect.left + visibleRect.right) / 2;
  score += 10 * Math.min(Math.max(cx / Math.max(vp.width, 1), 0), 1);
  score += Math.min(messages.length, MAX_MESSAGES) * 3;
  if (isLogLike(el)) score += 10;
  // Narrow strip on the left: a sidebar rather than the conversation.
  if (visibleRect.width < vp.width * 0.4 && cx < vp.width * 0.35) score -= 15;
  if (el.closest(NAV_SELECTOR)) score -= 60;
  if (el.querySelector(EDITABLE_SELECTOR)) score -= 10;
  // Conversation list: several clickable rows that each carry an avatar.
  const rowsWithAvatar = Array.from(el.querySelectorAll(INTERACTIVE_SELECTOR)).filter((i) => i.querySelector(AVATAR_SELECTOR)).length;
  if (rowsWithAvatar >= 3) score -= 45;
  return { el, score, messages };
}

/**
 * The element most likely to be the open conversation, or null. Candidates are scrollable
 * elements or role=log / aria-live regions that intersect the viewport.
 */
export function findConversationPanel(doc: Document, viewport?: Viewport, options: PanelOptions = {}): Element | null {
  const root = doc.body;
  if (!root) return null;
  const vp = viewport ?? viewportOf(doc, options);
  const opts: PanelOptions = { ...options, viewport: vp };
  const rectOf = rectFn(opts);
  const vpRect = viewportRect(vp);
  const candidates: Element[] = [];
  const all = root.querySelectorAll("*");
  const limit = Math.min(all.length, MAX_SCAN_ELEMENTS);
  for (let i = 0; i < limit; i++) {
    const el = all[i]!;
    if (!(isLogLike(el) || isScrollable(el))) continue;
    if (!intersect(rectOf(el), vpRect)) continue;
    candidates.push(el);
  }
  const scored = candidates
    .slice(0, MAX_CANDIDATES)
    .map((el) => scoreCandidate(el, doc, vp, opts))
    .filter((s): s is Scored => s !== null && s.score >= PANEL_THRESHOLD)
    .sort((a, b) => b.score - a.score);
  const best = scored[0];
  if (!best) return null;
  // Prefer the innermost scroller when the winner merely wraps another strong candidate.
  const inner = scored.find((s) => s !== best && best.el.contains(s.el) && s.score >= best.score * 0.6);
  return (inner ?? best).el;
}

/** Last 15 messages that fit in 4,000 characters, keeping the latest and the display order. */
export function limitMessages(messages: string[], maxMessages = MAX_MESSAGES, maxChars = MAX_CAPTURE_CHARS): string[] {
  const kept: string[] = [];
  let total = 0;
  for (let i = messages.length - 1; i >= 0 && kept.length < maxMessages; i--) {
    const m = messages[i]!;
    const cost = m.length + (kept.length > 0 ? 1 : 0);
    if (total + cost > maxChars) {
      if (kept.length === 0) kept.unshift(keepTail(m, maxChars));
      break;
    }
    kept.unshift(m);
    total += cost;
  }
  return kept;
}

/** Reads the main conversation panel, or null when none is found. */
export function captureConversation(doc: Document = document, options: PanelOptions = {}): ChatCapture | null {
  const vp = viewportOf(doc, options);
  const panel = findConversationPanel(doc, vp, options);
  if (!panel) return null;
  const messages = limitMessages(extractPanelMessages(panel, doc, { ...options, viewport: vp }));
  if (messages.length === 0) return null;
  return { text: messages.join("\n"), messages, source: "panel", origin: "EXTENSION_PAGE_TEXT" };
}

/** Selection, else the conversation panel, else visible viewport text. Runs only on a user action. */
export function captureChat(doc: Document = document, options: CaptureOptions & PanelOptions = {}): ChatCapture | null {
  const win = doc.defaultView;
  const selected = win ? getSelectionText(win) : "";
  if (selected) return { text: selected, messages: [selected], source: "selection", origin: "EXTENSION_SELECTION" };
  const panel = captureConversation(doc, options);
  if (panel) return panel;
  const text = captureViewportText(doc, options);
  if (!text) return null;
  return { text, messages: text.split("\n").filter(Boolean), source: "viewport", origin: "EXTENSION_PAGE_TEXT" };
}
