import type { ContextChoice } from "../../types/api";

const CHOICES: { value: ContextChoice; label: string }[] = [
  { value: "IN_STORE", label: "Mua tại cửa hàng" },
  { value: "ONLINE_ORDER", label: "Đơn hàng online" },
  { value: "URGENT_RELATIVE", label: "Người thân nhờ gấp" },
  { value: "AUTHORITY_REQUEST", label: "Cơ quan chức năng yêu cầu" },
];

interface Props {
  onChoose: (choice: ContextChoice) => void;
  disabled?: boolean;
  /** Opens the Guardian popup so the user can share a chat screenshot (origin CONTEXT_CHAT). */
  onInviteChatImage?: () => void;
}

export default function ContextElicitation({ onChoose, disabled = false, onInviteChatImage }: Props) {
  return (
    <section aria-label="Bối cảnh giao dịch" className="rounded-xl border border-gray-200 bg-white p-3">
      <p className="text-sm font-medium">Bạn chuyển tiền này vì lý do gì?</p>
      <div className="mt-2 grid grid-cols-2 gap-2">
        {CHOICES.map((c) => (
          <button
            key={c.value}
            type="button"
            disabled={disabled}
            onClick={() => onChoose(c.value)}
            className="rounded-lg border border-gray-300 px-2 py-2 text-sm disabled:opacity-50"
          >
            {c.label}
          </button>
        ))}
      </div>
      {onInviteChatImage && (
        <button
          type="button"
          disabled={disabled}
          onClick={onInviteChatImage}
          className="mt-2 w-full rounded-lg border border-pink-300 px-2 py-2 text-sm text-pink-700 disabled:opacity-50"
        >
          Chia sẻ ảnh chụp đoạn chat để Guardian xem giúp
        </button>
      )}
    </section>
  );
}
