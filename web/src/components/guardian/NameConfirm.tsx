import { useState } from "react";
import { digitsOnly, splitDigits } from "../../lib/digits";
import type { NameConfirmation } from "../../types/api";
import SandboxBadge from "./SandboxBadge";

interface Props {
  confirmation: NameConfirmation;
  busy?: boolean;
  /** User tapped "Đúng người nhận". */
  onConfirm: () => void;
  /** User tapped "Sai, sửa số" (lets the parent record the rejection). */
  onReject?: () => void;
  /** User submitted a corrected account number; parent re-runs /api/name/inquiry. */
  onCorrect: (accountNumber: string) => void;
}

/** Two-step confirmation of an OCR-read account (R2): NAPAS sandbox name + spaced digits. */
export default function NameConfirm({ confirmation, busy = false, onConfirm, onReject, onCorrect }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const digits = splitDigits(confirmation.account_digits_spaced);

  const startEdit = (): void => {
    setDraft(digits.join(""));
    setEditing(true);
    onReject?.();
  };

  const submit = (): void => {
    const next = digitsOnly(draft);
    if (next.length === 0) return;
    onCorrect(next);
    setEditing(false);
  };

  return (
    <section aria-label="Xác nhận người nhận" className="rounded-xl border border-gray-200 bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium">Guardian đọc được tài khoản từ ảnh. Bạn kiểm tra lại nhé.</p>
        {confirmation.sandbox && <SandboxBadge />}
      </div>
      <p className="mt-2 text-xs text-gray-500">{confirmation.bank_name ?? "Ngân hàng chưa xác định"}</p>
      <p data-testid="name-confirm-digits" className="mt-1 font-mono text-lg tracking-widest">
        {digits.join(" ")}
      </p>
      <p data-testid="name-confirm-name" className="mt-1 text-sm font-semibold">
        {confirmation.found && confirmation.display_name
          ? confirmation.display_name
          : "Không tìm thấy tên chủ tài khoản"}
      </p>

      {editing ? (
        <div className="mt-3 flex gap-2">
          <input
            aria-label="Số tài khoản đúng"
            inputMode="numeric"
            className="min-w-0 flex-1 rounded-lg border border-gray-300 p-2 text-sm"
            value={draft}
            onChange={(e) => setDraft(digitsOnly(e.target.value))}
          />
          <button
            type="button"
            disabled={busy || draft.length === 0}
            onClick={submit}
            className="rounded-lg bg-pink-600 px-3 py-2 text-sm text-white disabled:bg-gray-300"
          >
            Tra lại
          </button>
        </div>
      ) : (
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className="flex-1 rounded-lg bg-pink-600 px-3 py-2 text-sm text-white disabled:bg-gray-300"
          >
            Đúng người nhận
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={startEdit}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            Sai, sửa số
          </button>
        </div>
      )}
    </section>
  );
}
