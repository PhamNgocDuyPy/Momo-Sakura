import type { ShieldStats } from "../../types/api";

export default function ShieldCard({ stats }: { stats: ShieldStats }) {
  const rows: [string, number][] = [
    ["Cho phép", stats.ALLOW],
    ["Cần cân nhắc", stats.SOFT_FRICTION],
    ["Tạm giữ", stats.HARD_HOLD],
  ];
  return (
    <section aria-labelledby="shield-title" className="rounded-xl bg-white p-4 shadow-sm">
      <h2 id="shield-title" className="mb-2 text-base font-semibold">
        Guardian đã bảo vệ bạn
      </h2>
      <p className="text-sm">
        Số lần kiểm tra: <strong data-testid="shield-checks">{stats.checks}</strong>
      </p>
      <ul className="mt-1 text-sm text-gray-700">
        {rows.map(([label, n]) => (
          <li key={label} className="flex justify-between">
            <span>{label}</span>
            <span>{n}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
