import type { ResolvedContact } from "../../types/api";

interface Props {
  candidates: ResolvedContact[];
  message?: string;
  onPick: (contact: ResolvedContact) => void;
}

/** Lets the user choose between several contacts that match a typed name (F2 AMBIGUOUS). */
export default function ContactPicker({ candidates, message, onPick }: Props) {
  return (
    <section data-testid="contact-picker" aria-label="Chọn người nhận" className="space-y-2">
      <p className="text-sm font-medium text-slate-800">
        {message && message.length > 0 ? message : "Có nhiều người trùng tên. Bạn muốn chuyển cho ai?"}
      </p>
      <ul className="space-y-2">
        {candidates.map((c) => (
          <li key={c.id}>
            <button
              type="button"
              data-testid={`contact-${c.id}`}
              onClick={() => onPick(c)}
              className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-3 text-left active:bg-pink-50"
            >
              <span className="text-sm font-semibold text-slate-900">{c.display_name}</span>
              <span className="text-xs text-slate-500">…{c.account_number.slice(-4)}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
