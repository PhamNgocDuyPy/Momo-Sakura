import { useState } from "react";
import QRCode from "qrcode";
import { ApiError, api } from "../../services/api";
import type { DecisionTier } from "../../types/api";

interface Props {
  verdictId: string;
  tier: DecisionTier;
  /** `ui_hints.handoff_allowed` from the verdict. */
  handoffAllowed: boolean;
  bankBin: string;
  accountNumber: string;
  amountVnd: number | null;
  memo?: string | null;
}

const ERROR_VI: Record<string, string> = {
  HANDOFF_BLOCKED_HARD_HOLD:
    "Guardian đang tạm giữ giao dịch này nên không xuất mã QR sang app ngân hàng.",
  COOLDOWN_NOT_FINISHED:
    "Bạn cần hoàn tất thời gian chờ và các câu hỏi kiểm tra trước khi chuyển sang app ngân hàng.",
};

export function handoffErrorText(e: unknown): string {
  if (e instanceof ApiError) {
    const fixed = ERROR_VI[e.code];
    if (fixed) return fixed;
    if (e.messageVi) return e.messageVi;
  }
  return "Chưa tạo được mã QR lúc này. Bạn thử lại sau nhé.";
}

/** Exports the checked transfer as a VietQR for the user's own banking app. Never offered on HARD_HOLD. */
export default function BankHandoff({
  verdictId,
  tier,
  handoffAllowed,
  bankBin,
  accountNumber,
  amountVnd,
  memo,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [deeplink, setDeeplink] = useState<string | null>(null);
  const blocked = tier === "HARD_HOLD" || !handoffAllowed;

  const generate = async (): Promise<void> => {
    if (blocked) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.encodeQr({
        purpose: "BANK_HANDOFF",
        verdict_id: verdictId,
        bank_bin: bankBin,
        account_number: accountNumber,
        amount_vnd: amountVnd,
        memo: (memo ?? "").slice(0, 25),
      });
      setQrUrl(await QRCode.toDataURL(res.payload, { margin: 1, width: 280, errorCorrectionLevel: "M" }));
      setDeeplink(res.deeplink);
    } catch (e) {
      setQrUrl(null);
      setDeeplink(null);
      setError(handoffErrorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="bank-handoff" className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
      <button
        type="button"
        data-testid="bank-handoff-button"
        disabled={blocked || busy}
        onClick={() => void generate()}
        className="w-full rounded-xl border border-pink-600 px-4 py-3 text-sm font-semibold text-pink-700 disabled:border-slate-300 disabled:text-slate-400"
      >
        {busy ? "Đang tạo mã QR…" : "Chuyển sang app ngân hàng"}
      </button>
      {blocked && (
        <p data-testid="bank-handoff-blocked" className="text-xs text-slate-600">
          {tier === "HARD_HOLD" ? ERROR_VI.HANDOFF_BLOCKED_HARD_HOLD : "Giao dịch này chưa được phép chuyển sang app ngân hàng."}
        </p>
      )}
      {error && (
        <p role="alert" data-testid="bank-handoff-error" className="rounded-lg bg-red-50 p-2 text-sm text-red-800">
          {error}
        </p>
      )}
      {qrUrl && (
        <div className="space-y-2 text-center" data-testid="bank-handoff-result">
          <img src={qrUrl} alt="Mã VietQR để mở trong app ngân hàng" className="mx-auto h-56 w-56 rounded-lg border border-slate-200" />
          <a
            href={qrUrl}
            download="momo-guardian-vietqr.png"
            data-testid="bank-handoff-download"
            className="block rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-800"
          >
            Tải mã QR
          </a>
          {deeplink && (
            <a
              href={deeplink}
              data-testid="bank-handoff-deeplink"
              className="block rounded-lg bg-pink-600 px-3 py-2 text-sm font-semibold text-white"
            >
              Mở app ngân hàng
            </a>
          )}
        </div>
      )}
    </div>
  );
}
