import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { UiHints } from "../../types/api";
import { findVietnameseVoice, speak, stopSpeaking } from "../../services/tts";

export const CALM_BANNER_VI = "MoMo không bao giờ gọi điện yêu cầu bạn chuyển tiền";
export const CALM_MAX_BULLETS = 3;

const CalmContext = createContext(false);

/** True inside an active CalmShield: ResultCard uses it to cap bullets, enlarge text, hide promos. */
export function useCalm(): boolean {
  return useContext(CalmContext);
}

function telHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, "")}`;
}

interface Props {
  hints: UiHints;
  /** Evidence bullets, read aloud with the banner. At most 3 are used. */
  bullets?: string[];
  /** Called when the user taps the primary "Tạm dừng & xác minh" button. */
  onPause?: () => void;
  /** When provided, a dimmed "continue" button is shown; the parent decides what continuing means. */
  onContinue?: () => void;
  /** After the user chose to continue, the shield steps aside and shows the normal layout. */
  dismissed?: boolean;
  children: ReactNode;
}

/** Wraps a ResultCard in a calm, high-contrast layout when `ui_hints.calm_shield` is on. */
export default function CalmShield({ hints, bullets = [], onPause, onContinue, dismissed = false, children }: Props) {
  const active = hints.calm_shield && !dismissed;
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    void findVietnameseVoice().then((v) => {
      if (!cancelled) setVoice(v);
    });
    return () => {
      cancelled = true;
      stopSpeaking();
    };
  }, [active]);

  if (!active) return <>{children}</>;

  const shown = bullets.slice(0, CALM_MAX_BULLETS);
  const callTargets: { key: string; label: string; phone: string }[] = [];
  if (hints.hotline) {
    callTargets.push({ key: "hotline", label: `Gọi tổng đài ${hints.hotline}`, phone: hints.hotline });
  }
  hints.trusted_contacts.forEach((c, i) => {
    callTargets.push({ key: `tc${i}`, label: `Gọi ${c.name}`, phone: c.phone });
  });

  const readAloud = (): void => {
    void speak([CALM_BANNER_VI, ...shown].join(". "), voice);
  };

  return (
    <CalmContext.Provider value={true}>
      <div
        data-testid="calm-shield"
        className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-3 text-[1.125rem] leading-relaxed text-slate-900"
      >
        <p
          role="alert"
          data-testid="calm-banner"
          className="rounded-xl bg-slate-900 px-3 py-3 text-[1.25rem] font-bold text-white"
        >
          {CALM_BANNER_VI}
        </p>

        {children}

        <button
          type="button"
          data-testid="calm-pause"
          onClick={() => {
            setPaused(true);
            onPause?.();
          }}
          className="w-full rounded-xl bg-pink-700 px-4 py-4 text-[1.25rem] font-bold text-white shadow focus:outline-none focus-visible:ring-4 focus-visible:ring-pink-300"
        >
          Tạm dừng &amp; xác minh
        </button>

        {paused && (
          <p data-testid="calm-paused" role="status" className="rounded-xl bg-amber-100 p-3 font-semibold text-amber-950">
            Bạn chưa cần làm gì thêm. Hãy gọi người thân hoặc tổng đài để xác minh trước khi chuyển tiền.
          </p>
        )}

        {callTargets.length > 0 && (
          <div className="flex flex-col gap-2" data-testid="calm-call-list">
            {callTargets.map((t) => (
              <a
                key={t.key}
                href={telHref(t.phone)}
                className="block rounded-xl border-2 border-slate-900 px-4 py-3 text-center font-bold text-slate-900"
              >
                {t.label}
              </a>
            ))}
          </div>
        )}

        {voice && (
          <button
            type="button"
            data-testid="calm-read-aloud"
            onClick={readAloud}
            className="w-full rounded-xl border border-slate-400 px-4 py-3 font-semibold text-slate-800"
          >
            Đọc to cho tôi nghe
          </button>
        )}

        {onContinue && (
          <button
            type="button"
            data-testid="calm-continue"
            onClick={onContinue}
            className="w-full px-4 py-2 text-base text-slate-400 underline"
          >
            Tôi đã hiểu, tiếp tục
          </button>
        )}
      </div>
    </CalmContext.Provider>
  );
}
