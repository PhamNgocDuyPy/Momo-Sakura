interface SwitchRowProps {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function SwitchRow({ id, label, description, checked, onChange }: SwitchRowProps) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-3 py-2">
      <input
        id={id}
        type="checkbox"
        role="switch"
        className="mt-1 h-4 w-4 accent-pink-600"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="text-sm">
        <span className="block font-medium text-slate-800">{label}</span>
        <span className="block text-xs text-slate-500">{description}</span>
      </span>
    </label>
  );
}

/** Explicit consent for storing evidence (Luật 91/2025). Off by default. */
export default function ConsentToggle(props: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <SwitchRow
      id="guardian-consent"
      label="Cho phép lưu bằng chứng"
      description="Mặc định tắt. Khi tắt, Guardian chỉ lưu mã băm của nội dung, không lưu nội dung."
      {...props}
    />
  );
}

/** Opt-in clipboard check. Off by default; wired up in a later task. */
export function ClipboardToggle(props: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <SwitchRow
      id="guardian-clipboard"
      label="Kiểm tra clipboard"
      description="Mặc định tắt. Chỉ đọc khi bạn mở Guardian hoặc quay lại tab, không đọc định kỳ."
      {...props}
    />
  );
}
