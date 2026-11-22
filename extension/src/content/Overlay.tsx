import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ErrorPanel from "./ErrorPanel";
import ReadSummary, { type ReadInfo } from "./ReadSummary";
import ResultPanel from "./ResultPanel";
import ScanAnimation from "./ScanAnimation";
import ShieldIcon from "./ShieldIcon";
import Stage2Banner from "./Stage2Banner";
import type { CheckState } from "./state";

interface Props {
  state: CheckState;
  webUrl: string;
  onClose: () => void;
  onRetry?: () => void;
  /** What the last capture read; shown while scanning and on the result. */
  read?: ReadInfo | null;
}

/** Dim backdrop + scan animation / result card over the page. Esc and backdrop click close it. */
export default function Overlay({ state, webUrl, onClose, onRetry, read }: Props) {
  const open = state.phase !== "idle";

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, onClose]);

  const scanning = state.phase === "scanning" || state.phase === "stage2";

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="overlay"
          data-testid="guardian-overlay"
          className="pointer-events-auto fixed inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          <div
            data-testid="guardian-backdrop"
            className="absolute inset-0 bg-slate-950/65 backdrop-blur-[2px]"
            onClick={onClose}
          />
          {scanning && (
            <motion.div
              aria-hidden="true"
              data-testid="page-scan-line"
              className="pointer-events-none absolute inset-x-0 h-24"
              style={{
                background:
                  "linear-gradient(to bottom, rgba(244,114,182,0) 0%, rgba(244,114,182,0.28) 85%, rgba(255,255,255,0.85) 100%)",
                borderBottom: "2px solid rgba(255,255,255,0.9)",
              }}
              initial={{ top: "-6rem" }}
              animate={{ top: ["-6rem", "100%"] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: "linear" }}
            />
          )}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-4">
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label="MoMo Guardian"
              className="pointer-events-auto max-h-[92vh] w-full max-w-sm overflow-y-auto rounded-2xl bg-white p-4 text-slate-900 shadow-2xl"
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ type: "spring", stiffness: 380, damping: 30 }}
            >
              <header className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 text-pink-600">
                  <ShieldIcon className="h-6 w-6" />
                  <span className="text-sm font-bold">MoMo Guardian</span>
                </div>
                <button
                  type="button"
                  aria-label="Đóng"
                  data-testid="overlay-close"
                  onClick={onClose}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-lg leading-none text-slate-500 hover:bg-slate-100"
                >
                  ×
                </button>
              </header>

              {read && state.phase !== "error" && <ReadSummary info={read} />}
              {state.phase === "scanning" && <ScanAnimation phase="scanning" charCount={state.charCount} />}
              {state.phase === "stage2" && (
                <div className="space-y-2">
                  <Stage2Banner event={state.stage2} />
                  <ScanAnimation phase="stage2" charCount={state.charCount} />
                </div>
              )}
              {state.phase === "final" && <ResultPanel response={state.response} webUrl={webUrl} onClose={onClose} />}
              {state.phase === "error" && <ErrorPanel message={state.message} onRetry={onRetry} onClose={onClose} />}
            </motion.div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}