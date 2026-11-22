import { motion } from "framer-motion";
import ShieldIcon from "./ShieldIcon";

// Adapted from web/src/components/guardian/ScanAnimation.tsx (not imported, to avoid a second React).
const BLIPS = [
  { top: "18%", left: "62%", delay: 0.35 },
  { top: "34%", left: "20%", delay: 1.6 },
  { top: "70%", left: "72%", delay: 0.9 },
  { top: "78%", left: "30%", delay: 2.0 },
  { top: "50%", left: "84%", delay: 1.2 },
];
const SIZE = 192;
const SWEEP_SECONDS = 2.2;

export type ScanPhase = "scanning" | "stage2";

const STEPS = [
  "Đọc nội dung cần kiểm tra",
  "Kiểm tra liên kết, mã QR và dấu hiệu nhanh",
  "Phân tích kịch bản lừa đảo",
] as const;

function stepState(index: number, phase: ScanPhase): "done" | "active" | "todo" {
  const active = phase === "scanning" ? 1 : 2;
  if (index < active) return "done";
  return index === active ? "active" : "todo";
}

export default function ScanAnimation({ phase, charCount }: { phase: ScanPhase; charCount?: number }) {
  return (
    <div role="status" aria-live="polite" data-testid="scan-animation" className="flex flex-col items-center gap-4 py-3">
      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <div
          className="absolute inset-0 rounded-full border border-pink-300/70 bg-slate-900"
          style={{
            backgroundImage:
              "repeating-radial-gradient(circle at center, transparent 0 23px, rgba(244,114,182,0.28) 23px 24px)," +
              "linear-gradient(rgba(244,114,182,0.2),rgba(244,114,182,0.2)) center/1px 100% no-repeat," +
              "linear-gradient(rgba(244,114,182,0.2),rgba(244,114,182,0.2)) center/100% 1px no-repeat",
          }}
        />
        {[0, 1].map((i) => (
          <motion.div
            key={i}
            className="absolute inset-0 rounded-full border-2 border-pink-400"
            initial={{ scale: 0.35, opacity: 0.7 }}
            animate={{ scale: 1.2, opacity: 0 }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeOut", delay: i }}
          />
        ))}
        <motion.div
          data-testid="scan-sweep"
          className="absolute inset-0 rounded-full"
          style={{
            background:
              "conic-gradient(from 0deg, rgba(236,72,153,0) 0deg, rgba(236,72,153,0.05) 200deg, rgba(244,114,182,0.55) 330deg, rgba(255,255,255,0.9) 359deg, rgba(236,72,153,0) 360deg)",
            WebkitMask: "radial-gradient(circle, transparent 0 16px, #000 17px)",
            mask: "radial-gradient(circle, transparent 0 16px, #000 17px)",
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: SWEEP_SECONDS, repeat: Infinity, ease: "linear" }}
        />
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
        key={phase}
        className="text-sm font-semibold text-slate-800"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {phase === "scanning" ? "Đang quét nội dung…" : "Đang phân tích sâu hơn…"}
        {typeof charCount === "number" && charCount > 0 && (
          <span className="ml-1 font-normal text-slate-500">({charCount} ký tự)</span>
        )}
      </motion.p>

      <ol className="w-full max-w-xs space-y-1.5 text-sm" data-testid="scan-steps">
        {STEPS.map((label, i) => {
          const s = stepState(i, phase);
          return (
            <li key={label} data-step-state={s} className="flex items-center gap-2">
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                  s === "done"
                    ? "bg-pink-600 text-white"
                    : s === "active"
                      ? "border-2 border-pink-500 text-pink-600"
                      : "border border-slate-300 text-slate-300"
                }`}
              >
                {s === "done" ? (
                  "✓"
                ) : s === "active" ? (
                  <motion.span
                    className="h-2 w-2 rounded-full bg-pink-500"
                    animate={{ opacity: [1, 0.2, 1] }}
                    transition={{ duration: 0.9, repeat: Infinity }}
                  />
                ) : (
                  ""
                )}
              </span>
              <span className={s === "todo" ? "text-slate-400" : s === "active" ? "font-medium text-slate-900" : "text-slate-600"}>
                {label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}