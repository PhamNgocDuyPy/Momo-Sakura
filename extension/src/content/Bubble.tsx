import { useEffect, useRef } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { BUBBLE_SIZE, isTap, loadPosition, savePosition, snapToEdge, type Point } from "./bubblePosition";
import ShieldIcon from "./ShieldIcon";

function viewport() {
  return { width: window.innerWidth, height: window.innerHeight };
}

const SPRING = { type: "spring", stiffness: 400, damping: 32 } as const;

/** Draggable floating bubble. Snaps to the left/right edge and remembers its position. */
export const AUTO_PILL_WIDTH = 92;

interface BubbleProps {
  onTap: () => void;
  /** Current state of "Tự động bảo vệ" for this site. */
  autoProtect?: boolean;
  onToggleAutoProtect?: () => void;
}

export default function Bubble({ onTap, autoProtect = false, onToggleAutoProtect }: BubbleProps) {
  const start = useRef<Point | null>(null);
  const initial = snapToEdge({ x: viewport().width, y: viewport().height * 0.6 }, viewport());
  const x = useMotionValue(initial.x);
  const y = useMotionValue(initial.y);

  // Small switch under the bubble, aligned to the bubble's inner edge so it stays on screen.
  const pillX = useTransform(x, (v) => (v + BUBBLE_SIZE / 2 < viewport().width / 2 ? v : v + BUBBLE_SIZE - AUTO_PILL_WIDTH));
  const pillY = useTransform(y, (v) => v + BUBBLE_SIZE + 4);
  useEffect(() => {
    let cancelled = false;
    void loadPosition().then((saved) => {
      if (cancelled || !saved) return;
      const snapped = snapToEdge(saved, viewport());
      x.set(snapped.x);
      y.set(snapped.y);
    });
    const onResize = () => {
      const snapped = snapToEdge({ x: x.get(), y: y.get() }, viewport());
      x.set(snapped.x);
      y.set(snapped.y);
    };
    window.addEventListener("resize", onResize);
    return () => {
      cancelled = true;
      window.removeEventListener("resize", onResize);
    };
  }, [x, y]);

  return (
    <>
    <motion.button
      type="button"
      aria-label="Kiểm tra bằng MoMo Guardian"
      title="Kiểm tra bằng MoMo Guardian (Alt+G)"
      data-testid="guardian-bubble"
      className="pointer-events-auto fixed left-0 top-0 flex cursor-pointer touch-none select-none items-center justify-center rounded-full bg-gradient-to-br from-pink-500 to-fuchsia-600 text-white shadow-lg shadow-pink-500/40"
      style={{ x, y, width: BUBBLE_SIZE, height: BUBBLE_SIZE }}
      drag
      dragMomentum={false}
      dragElastic={0}
      whileTap={{ scale: 0.92 }}
      // Keep the page's text selection alive when the bubble is pressed.
      onMouseDown={(e) => e.preventDefault()}
      onPointerDown={(e) => {
        start.current = { x: e.clientX, y: e.clientY };
      }}
      onPointerUp={(e) => {
        const s = start.current;
        start.current = null;
        if (s && isTap(s, { x: e.clientX, y: e.clientY })) onTap();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onTap();
        }
      }}
      onDragEnd={() => {
        const snapped = snapToEdge({ x: x.get(), y: y.get() }, viewport());
        void savePosition(snapped);
        void animate(x, snapped.x, SPRING);
        void animate(y, snapped.y, SPRING);
      }}
    >
      <ShieldIcon className="h-7 w-7" />
    </motion.button>
    {onToggleAutoProtect && (
      <motion.button
        type="button"
        role="switch"
        aria-checked={autoProtect}
        data-testid="guardian-auto-toggle"
        title={autoProtect ? "Tự động bảo vệ đang bật trên trang này. Bấm để tắt." : "Bật Tự động bảo vệ cho trang này"}
        className={`pointer-events-auto fixed left-0 top-0 cursor-pointer select-none rounded-full border px-2 py-1 text-[11px] font-semibold shadow ${
          autoProtect ? "border-amber-400 bg-amber-100 text-amber-900" : "border-slate-300 bg-white text-slate-600"
        }`}
        style={{ x: pillX, y: pillY, width: AUTO_PILL_WIDTH }}
        onMouseDown={(e) => e.preventDefault()}
        onClick={onToggleAutoProtect}
      >
        Tự động: {autoProtect ? "Bật" : "Tắt"}
      </motion.button>
    )}
    </>
  );
}