import { motion } from "framer-motion";
import { ShieldIcon } from "./GuardianBubble";
import type { PopupStatus } from "../../state/guardianStore";

export const SCANNING_STATUSES: readonly PopupStatus[] = ["ocr", "stage1", "stage2"];

const LABELS: Partial<Record<PopupStatus, string>> = {
  ocr: "Đang đọc nội dung từ ảnh…",
  stage1: "Đang kiểm tra nhanh trên máy chủ…",
  stage2: "Đang phân tích nội dung đáng ngờ…",
};

// Fixed "blips" that flash as the sweep passes over them.
const BLIPS = [
  { top: "18%", left: "62%", delay: 0.35 },
  { top: "34%", left: "20%", delay: 1.6 },
  { top: "70%", left: "72%", delay: 0.9 },
  { top: "78%", left: "30%", delay: 2.0 },
];

const SIZE = 176;
const SWEEP_SECONDS = 2.4;

export default function ScanAnimation({ status }: { status: PopupStatus }) {
  const label = LABELS[status] ?? "Đang xử lý…";
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="scan-animation"
      className="flex flex-col items-center gap-3 py-4"
    >
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        {/* Radar disc with grid */}
        <div
          className="absolute inset-0 rounded-full border border-pink-300/70 bg-slate-900"
          style={{
            backgroundImage:
              "repeating-radial-gradient(circle at center, transparent 0 21px, rgba(244,114,182,0.28) 21px 22px)," +
              "linear-gradient(rgba(244,114,182,0.2),rgba(244,114,182,0.2)) center/1px 100% no-repeat," +
              "linear-gradient(rgba(244,114,182,0.2),rgba(244,114,182,0.2)) center/100% 1px no-repeat",
          }}
        />

        {/* Expanding pulse rings */}
        {[0, 1].map((i) => (
          <motion.div
            key={i}
            className="absolute inset-0 rounded-full border-2 border-pink-400"
            initial={{ scale: 0.35, opacity: 0.7 }}
            animate={{ scale: 1.15, opacity: 0 }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeOut", delay: i }}
          />
        ))}

        {/* Rotating conic sweep with bright leading edge */}
        <motion.div
          data-testid="scan-sweep"
          className="absolute inset-0 rounded-full"
          style={{
            background:
              "conic-gradient(from 0deg, rgba(236,72,153,0) 0deg, rgba(236,72,153,0.05) 200deg, rgba(244,114,182,0.55) 330deg, rgba(255,255,255,0.9) 359deg, rgba(236,72,153,0) 360deg)",
            WebkitMask: "radial-gradient(circle, transparent 0 14px, #000 15px)",
            mask: "radial-gradient(circle, transparent 0 14px, #000 15px)",
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: SWEEP_SECONDS, repeat: Infinity, ease: "linear" }}
        />

        {/* Blips */}
        {BLIPS.map((b, i) => (
          <motion.span
            key={i}
            className="absolute h-2 w-2 rounded-full bg-pink-300 shadow-[0_0_8px_2px_rgba(244,114,182,0.9)]"
            style={{ top: b.top, left: b.left }}
            initial={{ opacity: 0, scale: 0.4 }}
            animate={{ opacity: [0, 1, 0], scale: [0.4, 1.3, 0.6] }}
            transition={{ duration: SWEEP_SECONDS, repeat: Infinity, delay: b.delay, times: [0, 0.1, 1] }}
          />
        ))}

        {/* Shield core */}
        <motion.div
          className="absolute left-1/2 top-1/2 flex h-16 w-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-slate-900/90 text-pink-300 ring-2 ring-pink-400"
          animate={{
            scale: [1, 1.08, 1],
            boxShadow: [
              "0 0 8px 0 rgba(244,114,182,0.5)",
              "0 0 26px 6px rgba(244,114,182,0.85)",
              "0 0 8px 0 rgba(244,114,182,0.5)",
            ],
          }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        >
          <ShieldIcon className="h-9 w-9" />
        </motion.div>
      </div>

      <motion.p
        key={status}
        className="text-sm font-medium text-slate-700"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {label}
      </motion.p>
    </div>
  );
}
