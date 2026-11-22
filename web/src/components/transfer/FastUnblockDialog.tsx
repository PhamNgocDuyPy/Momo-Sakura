import { useState } from "react";
import { ApiError, api } from "../../services/api";
import type { CheckResponse, FastUnblockPurpose } from "../../types/api";

const PURPOSES: { value: FastUnblockPurpose; label: string }[] = [
  { value: "PAY_FAMILY", label: "Gửi tiền cho người nhà" },
  { value: "PAY_GOODS_SERVICES", label: "Thanh toán hàng hóa, dịch vụ" },
  { value: "PAY_RENT", label: "Tiền thuê nhà" },
  { value: "TUITION", label: "Học phí" },
  { value: "LOAN_REPAYMENT", label: "Trả nợ vay" },
  { value: "BUSINESS_PAYMENT", label: "Thanh toán kinh doanh" },
  { value: "OTHER", label: "Mục đích khác" },
];

interface Props {
  verdictId: string;
  onUnblocked: (response: CheckResponse) => void;
  onCancel: () => void;
}

export default function FastUnblockDialog({ verdictId, onUnblocked, onCancel }: Props) {
  const [code, setCode] = useState("");
  const [purpose, setPurpose] = useState<FastUnblockPurpose>("PAY_FAMILY");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (): Promise<void> => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.fastUnblock({
        verdict_id: verdictId,
        identity_check: { method: "SANDBOX_OTP", code },
        purpose,
      });
      onUnblocked(res);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? (e.messageVi ?? "Không thể mở chặn nhanh. Vui lòng kiểm tra lại mã xác thực.")
          : "Không thể kết nối tới Guardian. Vui lòng thử lại.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div role="dialog" aria-label="Mở chặn nhanh" className="space-y-3 rounded-xl border border-gray-300 bg-white p-4">
      <h3 className="text-base font-semibold">Mở chặn nhanh</h3>
      <label className="block text-sm">
        Mã OTP (mô phỏng)
        <input
          className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
          inputMode="numeric"
          value={code}
          onChange={(e) => setCode(e.target.value.trim())}
        />
      </label>
      <label className="block text-sm">
        Mục đích chuyển tiền
        <select
          className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
          value={purpose}
          onChange={(e) => setPurpose(e.target.value as FastUnblockPurpose)}
        >
          {PURPOSES.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      {error !== null && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy || code === ""}
          onClick={() => void submit()}
          className="flex-1 rounded-lg bg-pink-600 px-4 py-2 text-white disabled:bg-gray-300"
        >
          Xác thực
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg border border-gray-300 px-4 py-2">
          Hủy
        </button>
      </div>
    </div>
  );
}
