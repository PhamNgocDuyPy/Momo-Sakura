import { parseAmount } from "../../lib/amount";

export interface TransferFormValues {
  bankBin: string;
  accountNumber: string;
  amountText: string;
  memo: string;
}

export function parsedAmount(values: TransferFormValues): number | null {
  const n = parseAmount(values.amountText);
  return n !== null && n > 0 ? n : null;
}

export function isFormValid(values: TransferFormValues): boolean {
  return (
    /^\d{6}$/.test(values.bankBin) &&
    /^\d{6,19}$/.test(values.accountNumber) &&
    parsedAmount(values) !== null
  );
}

interface Props {
  values: TransferFormValues;
  onChange: (values: TransferFormValues) => void;
  onSubmit: () => void;
}

const INPUT = "mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm";

export default function TransferForm({ values, onChange, onSubmit }: Props) {
  const set = (patch: Partial<TransferFormValues>): void => onChange({ ...values, ...patch });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <label className="block text-sm">
        Mã ngân hàng (BIN)
        <input
          className={INPUT}
          inputMode="numeric"
          value={values.bankBin}
          onChange={(e) => set({ bankBin: e.target.value.trim() })}
        />
      </label>
      <label className="block text-sm">
        Số tài khoản
        <input
          className={INPUT}
          inputMode="numeric"
          value={values.accountNumber}
          onChange={(e) => set({ accountNumber: e.target.value.trim() })}
        />
      </label>
      <label className="block text-sm">
        Số tiền
        <input
          className={INPUT}
          value={values.amountText}
          onChange={(e) => set({ amountText: e.target.value })}
        />
      </label>
      <label className="block text-sm">
        Lời nhắn
        <input
          className={INPUT}
          maxLength={100}
          value={values.memo}
          onChange={(e) => set({ memo: e.target.value })}
        />
      </label>
      <button
        type="submit"
        disabled={!isFormValid(values)}
        className="w-full rounded-lg bg-pink-600 px-4 py-2 text-white disabled:bg-gray-300"
      >
        Tiếp tục
      </button>
    </form>
  );
}
