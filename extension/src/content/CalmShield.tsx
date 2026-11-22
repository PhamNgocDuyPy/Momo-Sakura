import { motion } from "framer-motion";
import type { CheckResponse } from "../shared/types";
import OpenGuardianButton from "./OpenGuardianButton";
import { CALM_BANNER_VI, CALM_MAX_BULLETS, TIER_STYLE, telHref } from "./tier";

interface Props {
  response: CheckResponse;
  webUrl: string;
  onClose: () => void;
}

// Compact, high-contrast mode adapted from web/src/components/guardian/CalmShield.tsx.
export default function CalmShield({ response, webUrl, onClose }: Props) {
  const { verdict, ui_hints: hints } = response;
  const style = TIER_STYLE[verdict.decision_tier];
  const bullets = verdict.evidence_bullets.slice(0, CALM_MAX_BULLETS);
  return (
    <motion.section
      aria-label="Kết quả kiểm tra"
      data-testid="calm-shield"
      data-tier={verdict.decision_tier}
      className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-3 text-[1.125rem] leading-relaxed text-slate-900"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <p
        role="alert"
        data-testid="calm-banner"
        className="rounded-xl bg-slate-900 px-3 py-3 text-[1.25rem] font-bold text-white"
      >
        {CALM_BANNER_VI}
      </p>
      <h2 data-testid="tier-label" className={`text-[1.25rem] font-bold ${style.title}`}>
        {style.label}
      </h2>
      {bullets.length > 0 && (
        <ul data-testid="evidence" className="list-disc space-y-1 pl-6 font-medium">
          {bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      )}
      {hints.hotline && (
        <a
          href={telHref(hints.hotline)}
          data-testid="calm-hotline"
          className="block rounded-xl border-2 border-slate-900 px-4 py-3 text-center font-bold text-slate-900"
        >
          Gọi tổng đài {hints.hotline}
        </a>
      )}
      <OpenGuardianButton webUrl={webUrl} />
      <button
        type="button"
        onClick={onClose}
        data-testid="result-close"
        className="w-full rounded-xl border-2 border-slate-400 px-4 py-3 text-base font-semibold text-slate-700"
      >
        Đóng
      </button>
    </motion.section>
  );
}