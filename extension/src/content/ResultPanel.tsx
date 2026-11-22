import { motion } from "framer-motion";
import type { CheckResponse } from "../shared/types";
import CalmShield from "./CalmShield";
import OpenGuardianButton from "./OpenGuardianButton";
import { TIER_STYLE, coolingText } from "./tier";

interface Props {
  response: CheckResponse;
  /** Web app URL from settings; the "Mở MoMo Guardian" button opens it in a new tab. */
  webUrl: string;
  onClose: () => void;
}

/**
 * Final result. Renders only strings from GuardianVerdict / ui_hints (backend templates) plus fixed
 * extension labels. Never claims a message is 100% safe.
 */
export default function ResultPanel({ response, webUrl, onClose }: Props) {
  const { verdict, ui_hints: hints } = response;
  if (hints.calm_shield) return <CalmShield response={response} webUrl={webUrl} onClose={onClose} />;

  const style = TIER_STYLE[verdict.decision_tier];
  const cooling = coolingText(verdict.cooling_off_seconds);
  return (
    <motion.section
      aria-label="Kết quả kiểm tra"
      data-testid="result-panel"
      data-tier={verdict.decision_tier}
      className={`rounded-xl border-2 p-4 ${style.box}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-start gap-2">
        <span className={`mt-1 h-3 w-3 shrink-0 rounded-full ${style.chip}`} aria-hidden="true" />
        <h2 data-testid="tier-label" className={`text-base font-bold ${style.title}`}>
          {style.label}
        </h2>
      </div>

      {verdict.evidence_bullets.length > 0 && (
        <ul data-testid="evidence" className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-800">
          {verdict.evidence_bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      )}

      {verdict.system2_check_questions.length > 0 && (
        <div data-testid="system2" className="mt-3 rounded-lg bg-white/80 p-3 text-sm">
          <p className="font-semibold text-slate-900">Hãy tự hỏi trước khi chuyển tiền</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-800">
            {verdict.system2_check_questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </div>
      )}

      {cooling && (
        <p data-testid="cooling" className="mt-3 text-sm font-medium text-slate-800">
          {cooling}
        </p>
      )}

      <p className="mt-3 text-[11px] leading-snug text-slate-500">
        Kết quả chỉ để tham khảo. Hãy xác minh qua kênh chính thức trước khi chuyển tiền.
      </p>
      {verdict.reason_codes.length > 0 && (
        <p data-testid="reason-codes" className="mt-1 break-words text-[11px] text-slate-400">
          {verdict.reason_codes.join(" · ")}
        </p>
      )}

      <div className="mt-3 flex flex-col gap-2">
        <OpenGuardianButton webUrl={webUrl} />
        <button
          type="button"
          onClick={onClose}
          data-testid="result-close"
          className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Đóng
        </button>
      </div>
    </motion.section>
  );
}