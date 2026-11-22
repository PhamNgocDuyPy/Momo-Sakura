import { STORAGE_KEYS } from "../shared/settings";

export interface Point {
  x: number;
  y: number;
}
export interface Viewport {
  width: number;
  height: number;
}

export const BUBBLE_SIZE = 56;
/** Movement (px) below which a pointer gesture counts as a tap, not a drag. */
export const TAP_THRESHOLD_PX = 6;

/** Snaps a bubble (top-left position) to the nearest left or right edge, clamped vertically. */
export function snapToEdge(pos: Point, viewport: Viewport, size: number = BUBBLE_SIZE): Point {
  const maxX = Math.max(0, viewport.width - size);
  const maxY = Math.max(0, viewport.height - size);
  const x = pos.x + size / 2 < viewport.width / 2 ? 0 : maxX;
  const y = Math.min(Math.max(pos.y, 0), maxY);
  return { x, y };
}

export function isTap(start: Point, end: Point, threshold: number = TAP_THRESHOLD_PX): boolean {
  return Math.hypot(end.x - start.x, end.y - start.y) < threshold;
}

export async function savePosition(pos: Point): Promise<void> {
  try {
    await chrome.storage.local.set({ [STORAGE_KEYS.bubble]: pos });
  } catch {
    // Storage unavailable (extension reloaded): position is session-only.
  }
}

export async function loadPosition(): Promise<Point | null> {
  try {
    const stored = await chrome.storage.local.get(STORAGE_KEYS.bubble);
    const p: unknown = stored[STORAGE_KEYS.bubble];
    if (
      typeof p === "object" &&
      p !== null &&
      Number.isFinite((p as Point).x) &&
      Number.isFinite((p as Point).y)
    ) {
      return { x: (p as Point).x, y: (p as Point).y };
    }
  } catch {
    // fall through
  }
  return null;
}