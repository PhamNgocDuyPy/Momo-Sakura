import type { ExtensionOrigin } from "../shared/types";

export const MAX_CAPTURE_CHARS = 4000;
export const HOST_TAG = "momo-guardian-root";

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
  HOST_TAG.toUpperCase(),
]);

export interface Captured {
  text: string;
  origin: ExtensionOrigin;
}

export interface RectLike {
  top: number;
  bottom: number;
  left: number;
  right: number;
  width: number;
  height: number;
}

export interface CaptureOptions {
  /** Bounding rect of a text node; defaults to Range#getBoundingClientRect. */
  rectOf?: (node: Text) => RectLike | null;
  viewport?: { width: number; height: number };
}

/** Keeps the last `max` characters (the end of a chat is the newest part). */
export function keepTail(text: string, max: number = MAX_CAPTURE_CHARS): string {
  return text.length > max ? text.slice(text.length - max) : text;
}

/** The user's current text selection, trimmed, or "" when nothing is selected. */
export function getSelectionText(win: Window = window): string {
  return keepTail(win.getSelection()?.toString().trim() ?? "");
}

function defaultRectOf(node: Text): RectLike | null {
  const doc = node.ownerDocument;
  if (!doc || typeof doc.createRange !== "function") return null;
  const range = doc.createRange();
  range.selectNodeContents(node);
  if (typeof range.getBoundingClientRect !== "function") return null;
  return range.getBoundingClientRect();
}

function isHiddenElement(el: Element, win: Window): boolean {
  if (el.hasAttribute("hidden") || el.getAttribute("aria-hidden") === "true") return true;
  const style = win.getComputedStyle(el);
  return style.display === "none";
}

function isInViewport(rect: RectLike, vp: { width: number; height: number }): boolean {
  if (rect.width <= 0 && rect.height <= 0) return false;
  return rect.bottom > 0 && rect.right > 0 && rect.top < vp.height && rect.left < vp.width;
}

/**
 * Visible text in the viewport, in DOM order, skipping inputs, scripts, styles and hidden
 * elements. Keeps the last 4000 characters. Only call this after a user action.
 */
export function captureViewportText(doc: Document = document, options: CaptureOptions = {}): string {
  const win = doc.defaultView;
  if (!win || !doc.body) return "";
  const vp = options.viewport ?? { width: win.innerWidth, height: win.innerHeight };
  const rectOf = options.rectOf ?? defaultRectOf;
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode(node: Node): number {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const el = node as Element;
        if (SKIP_TAGS.has(el.tagName.toUpperCase()) || isHiddenElement(el, win)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_SKIP;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const parts: string[] = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = (n.nodeValue ?? "").replace(/\s+/g, " ").trim();
    if (!text) continue;
    const parent = n.parentElement;
    if (parent && win.getComputedStyle(parent).visibility === "hidden") continue;
    const rect = rectOf(n as Text);
    if (!rect || !isInViewport(rect, vp)) continue;
    parts.push(text);
  }
  return keepTail(parts.join("\n"));
}

/** Selection first (EXTENSION_SELECTION); otherwise visible viewport text (EXTENSION_PAGE_TEXT). */
export function capture(doc: Document = document, options: CaptureOptions = {}): Captured | null {
  const win = doc.defaultView;
  const selected = win ? getSelectionText(win) : "";
  if (selected) return { text: selected, origin: "EXTENSION_SELECTION" };
  const pageText = captureViewportText(doc, options);
  return pageText ? { text: pageText, origin: "EXTENSION_PAGE_TEXT" } : null;
}