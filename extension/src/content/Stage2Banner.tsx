import { motion } from "framer-motion";
import type { Stage2Event } from "../shared/types";

/** Provisional Stage 2 notice. Own fixed wording; nothing from the backend is echoed except tier/red_alert. */
export default function Stage2Banner({ event }: { event: Stage2Event }) {
  if (event.red_alert || event.provisional_tier === "HARD_HOLD") {
    return (
      <motion.div
        role="alert"
        data-testid="stage2-red-alert"
        data-tier={event.provisional_tier}
        className="w-full rounded-xl bg-red-600 px-3 py-2 text-center text-sm font-bold text-white"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1, boxShadow: ["0 0 0 0 rgba(220,38,38,0.7)", "0 0 0 10px rgba(220,38,38,0)"] }}
        transition={{ duration: 0.3, boxShadow: { duration: 1.2, repeat: Infinity } }}
      >
        Cảnh báo: phát hiện dấu hiệu rủi ro cao. Đang phân tích sâu hơn…
      </motion.div>
    );
  }
  if (event.provisional_tier === "SOFT_FRICTION") {
    return (
      <motion.div
        role="status"
        data-testid="stage2-warning"
        data-tier={event.provisional_tier}
        className="w-full rounded-xl bg-amber-100 px-3 py-2 text-center text-sm font-semibold text-amber-900"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        Phát hiện dấu hiệu đáng ngờ. Đang phân tích sâu hơn…
      </motion.div>
    );
  }
  return null;
}