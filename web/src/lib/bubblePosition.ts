export interface Point {
  x: number;
  y: number;
}

export interface Viewport {
  width: number;
  height: number;
}

export const BUBBLE_SIZE = 56;
export const BUBBLE_STORAGE_KEY = "guardian.bubble.pos";
/** Movement (px) below which a pointer gesture counts as a tap, not a drag. */
export const TAP_THRESHOLD_PX = 6;

/**
 * Snap a bubble (top-left position) to the nearest left or right viewport edge.
 * The vertical position is clamped so the bubble stays fully visible.
 */
export function snapToEdge(pos: Point, viewport: Viewport, size: number = BUBBLE_SIZE): Point {
  const maxX = Math.max(0, viewport.width - size);
  const maxY = Math.max(0, viewport.height - size);
  const centerX = pos.x + size / 2;
  const x = centerX < viewport.width / 2 ? 0 : maxX;
  const y = Math.min(Math.max(pos.y, 0), maxY);
  return { x, y };
}

export function savePosition(pos: Point, storage: Pick<Storage, "setItem"> = localStorage): void {
  try {
    storage.setItem(BUBBLE_STORAGE_KEY, JSON.stringify(pos));
  } catch {
    // Storage may be unavailable (private mode); position is then session-only.
  }
}

export function loadPosition(storage: Pick<Storage, "getItem"> = localStorage): Point | null {
  try {
    const raw = storage.getItem(BUBBLE_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      typeof (parsed as Point).x === "number" &&
      typeof (parsed as Point).y === "number" &&
      Number.isFinite((parsed as Point).x) &&
      Number.isFinite((parsed as Point).y)
    ) {
      return { x: (parsed as Point).x, y: (parsed as Point).y };
    }
  } catch {
    // fall through
  }
  return null;
}

export function isTap(start: Point, end: Point, threshold: number = TAP_THRESHOLD_PX): boolean {
  return Math.hypot(end.x - start.x, end.y - start.y) < threshold;
}
