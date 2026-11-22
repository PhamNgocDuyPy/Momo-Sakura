import { useEffect, useRef, useState } from "react";
import { animate, motion, useMotionValue } from "framer-motion";
import { useGuardian } from "../../state/guardianStore";
import {
  BUBBLE_SIZE,
  isTap,
  loadPosition,
  savePosition,
  snapToEdge,
  type Point,
} from "../../lib/bubblePosition";

function viewport() {
  return { width: window.innerWidth, height: window.innerHeight };
}

function initialPosition(): Point {
  const vp = viewport();
  const stored = loadPosition();
  if (stored) return snapToEdge(stored, vp);
  return snapToEdge({ x: vp.width, y: vp.height * 0.6 }, vp);
}

export default function GuardianBubble() {
  const { state, dispatch } = useGuardian();
  const start = useRef<Point | null>(null);
  const [initial] = useState(initialPosition);
  const x = useMotionValue(initial.x);
  const y = useMotionValue(initial.y);

  // Keep the bubble on an edge when the viewport changes (rotation, resize).
  useEffect(() => {
    const onResize = () => {
      const snapped = snapToEdge({ x: x.get(), y: y.get() }, viewport());
      x.set(snapped.x);
      y.set(snapped.y);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [x, y]);

  if (state.popup.open) return null;

  const open = () => dispatch({ type: "OPEN_POPUP" });

  return (
    <motion.button
      type="button"
      aria-label="Mở Guardian"
      data-testid="guardian-bubble"
      className="fixed left-0 top-0 z-40 flex touch-none items-center justify-center rounded-full bg-gradient-to-br from-pink-500 to-fuchsia-600 text-white shadow-lg shadow-pink-500/40"
      style={{ x, y, width: BUBBLE_SIZE, height: BUBBLE_SIZE }}
      drag
      dragMomentum={false}
      dragElastic={0}
      whileTap={{ scale: 0.92 }}
      onPointerDown={(e) => {
        start.current = { x: e.clientX, y: e.clientY };
      }}
      onPointerUp={(e) => {
        const s = start.current;
        start.current = null;
        if (s && isTap(s, { x: e.clientX, y: e.clientY })) open();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      }}
      onDragEnd={() => {
        const snapped = snapToEdge({ x: x.get(), y: y.get() }, viewport());
        savePosition(snapped);
        animate(x, snapped.x, { type: "spring", stiffness: 400, damping: 32 });
        animate(y, snapped.y, { type: "spring", stiffness: 400, damping: 32 });
      }}
    >
      <ShieldIcon className="h-7 w-7" />
    </motion.button>
  );
}

export function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M12 2.5 4.5 5.5v5.8c0 4.6 3.1 8.6 7.5 10.2 4.4-1.6 7.5-5.6 7.5-10.2V5.5L12 2.5Z"
        fill="currentColor"
        fillOpacity="0.2"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="m8.8 12.2 2.2 2.2 4.4-4.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
