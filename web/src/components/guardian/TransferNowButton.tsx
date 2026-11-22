import { useState } from "react";
import { parseAmount } from "../../lib/amount";
import type { CheckResponse, Prefill } from "../../types/api";

/** Router state handed to TransferPage. */
export interface TransferNavState {
  prefill: Prefill;
  /** Absent when the prefill comes from an assistant command (F2), not from a Flow B verdict. */
  origin_verdict_id?: string;
  /** Present only after the user confirmed an OCR-read account (R2). */
  confirmation_token?: string;
}

interface Props {
  response: CheckResponse;
  /** Token from /api/name/confirm; makes Flow A send OCR_CONFIRMED_BY_USER. */
  confirmationToken?: string | null;
  onTransfer: (state: TransferNavState) => void;
}

const FIELD_LABEL: Record<string, string> = {
  bank_bin: "Mã ngân hàng (BIN)",
  account_number: "Số tài khoản",
  amount_vnd: "Số tiền",
};

export function canShowTransferNow(response: CheckResponse): boolean {
  if (response.verdict.decision_tier === "HARD_HOLD") return false;
  const { show_transfer_now, missing_fields } = response.ui_hints;
  return show_transfer_now || (missing_fields.length > 0 && response.prefill !== null);
}

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm";

/** F1 "Chuyển ngay": opens TransferPage with the prefill; asks for any missing field first. */
export default function TransferNowButton({ response, confirmationToken, onTransfer }: Props) {
  const missing = response.ui_hints.missing_fields.filter((f) => f in FIELD_LABEL);
  const [asking, setAsking] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});

  if (!canShowTransferNow(response)) return null;

  const base: Prefill = response.prefill ?? {
    bank_bin: null,
    account_number: null,
    amount_vnd: null,
    memo: null,
    source_integrity_for_flow_a: "USER_TYPED",
  };

  const go = (prefill: Prefill): void => {
    onTransfer({
      prefill,
      origin_verdict_id: response.verdict_id,
      ...(confirmationToken ? { confirmation_token: confirmationToken } : {}),
    });
  };

  const amountOk = !missing.includes("amount_vnd") || (parseAmount(draft.amount_vnd ?? "") ?? 0) > 0;
  const complete = missing.every((f) => (draft[f] ?? "").trim() !== "") && amountOk;

  const submitForm = (): void => {
    const next: Prefill = { ...base };
    if (missing.includes("bank_bin")) next.bank_bin = (draft.bank_bin ?? "").trim();
    if (missing.includes("account_number")) next.account_number = (draft.account_number ?? "").trim();
    if (missing.includes("amount_vnd")) next.amount_vnd = parseAmount(draft.amount_vnd ?? "");
    // Typing a missing field by hand makes the whole set user-reviewed, not machine-read.
    go(next);
  };

  if (missing.length > 0 && asking) {
    return (
      <form
        data-testid="transfer-now-form"
        className="space-y-2 rounded-xl border border-pink-200 bg-white p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (complete) submitForm();
        }}
      >
        <p className="text-sm font-medium text-slate-800">Bổ sung thông tin còn thiếu để chuyển:</p>
        {missing.map((f) => (
          <label key={f} className="block text-sm">
            {FIELD_LABEL[f]}
            <input
              className={INPUT}
              inputMode={f === "amount_vnd" ? "text" : "numeric"}
              value={draft[f] ?? ""}
              onChange={(e) => setDraft({ ...draft, [f]: e.target.value })}
            />
          </label>
        ))}
        <button
          type="submit"
          disabled={!complete}
          className="w-full rounded-lg bg-pink-600 px-4 py-3 text-sm font-semibold text-white disabled:bg-slate-300"
        >
          Tiếp tục
        </button>
      </form>
    );
  }

  return (
    <button
      type="button"
      data-testid="transfer-now"
      onClick={() => (missing.length > 0 ? setAsking(true) : go(base))}
      className="w-full rounded-xl bg-pink-600 px-4 py-3 text-base font-semibold text-white shadow-sm active:bg-pink-700"
    >
      Chuyển ngay
    </button>
  );
}
