import { useState } from "react";
import { formatVnd } from "../../lib/amount";

interface Props {
  bankBin: string;
  accountNumber: string;
  amountVnd: number;
  memo: string;
  busy?: boolean;
  /** Called only after both steps. Flow A runs here. */
  onConfirm: () => void;
  onBack: () => void;
}

export default function TwoStepConfirm({
  bankBin,
  accountNumber,
  amountVnd,
  memo,
  busy = false,
  onConfirm,
  onBack,
}: Props) {
  const [step, setStep] = useState<1 | 2>(1);
  return (
    <section aria-label="Xác nhận chuyển tiền" className="space-y-3">
      <dl className="rounded-xl bg-gray-50 p-3 text-sm">
        <dt className="text-gray-500">Ngân hàng (BIN)</dt>
        <dd>{bankBin}</dd>
        <dt className="mt-1 text-gray-500">Số tài khoản</dt>
        <dd>{accountNumber}</dd>
        <dt className="mt-1 text-gray-500">Số tiền</dt>
        <dd>{formatVnd(amountVnd)}</dd>
        {memo !== "" && (
          <>
            <dt className="mt-1 text-gray-500">Lời nhắn</dt>
            <dd>{memo}</dd>
          </>
        )}
      </dl>
      {step === 1 ? (
        <button
          type="button"
          onClick={() => setStep(2)}
          className="w-full rounded-lg bg-pink-600 px-4 py-2 text-white"
        >
          Kiểm tra thông tin
        </button>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={onConfirm}
          className="w-full rounded-lg bg-pink-600 px-4 py-2 text-white disabled:bg-gray-300"
        >
          Xác nhận chuyển
        </button>
      )}
      <button type="button" onClick={onBack} className="w-full text-sm text-gray-600">
        Sửa thông tin
      </button>
    </section>
  );
}
