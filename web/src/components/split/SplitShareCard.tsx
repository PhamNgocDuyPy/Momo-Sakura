import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { formatVnd } from "../../lib/amount";
import type { SplitShare } from "../../types/api";

interface Props {
  name: string;
  share: SplitShare;
}

/** One person's share. A QR is drawn only for a valid payload; QR_ERROR shares show the amount alone. */
export default function SplitShareCard({ name, share }: Props) {
  const [dataUrl, setDataUrl] = useState<string | null>(null);
  const payload = share.qr_status === "VALID_VIETQR" ? share.qr_payload : null;

  useEffect(() => {
    let cancelled = false;
    setDataUrl(null);
    if (!payload) return;
    QRCode.toDataURL(payload, { margin: 1, width: 240, errorCorrectionLevel: "M" })
      .then((url) => {
        if (!cancelled) setDataUrl(url);
      })
      .catch(() => {
        if (!cancelled) setDataUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [payload]);

  return (
    <li
      data-testid={`share-${share.participant_id}`}
      className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3"
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-slate-900">{name}</p>
        <p data-testid={`share-amount-${share.participant_id}`} className="text-lg font-bold text-pink-700">
          {formatVnd(share.amount_vnd)}
        </p>
        {share.is_payee && <p className="text-xs text-slate-500">Phần của bạn, không cần chuyển.</p>}
      </div>
      {dataUrl && (
        <img
          src={dataUrl}
          alt={`Mã QR chuyển ${formatVnd(share.amount_vnd)} cho bạn`}
          data-testid={`share-qr-${share.participant_id}`}
          className="h-24 w-24 shrink-0 rounded-lg border border-slate-200"
        />
      )}
    </li>
  );
}
