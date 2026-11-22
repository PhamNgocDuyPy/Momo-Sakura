import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatVnd } from "../../lib/amount";
import type { WalletSummary } from "../../types/api";

export default function SpendingChart({ data }: { data: WalletSummary["spending_by_category"] }) {
  return (
    <section aria-labelledby="spending-title" className="rounded-xl bg-white p-4 shadow-sm">
      <h2 id="spending-title" className="mb-2 text-base font-semibold">
        Chi tiêu theo danh mục
      </h2>
      {data.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa có chi tiêu trong tháng này.</p>
      ) : (
        <>
          <div className="h-48 w-full" data-testid="spending-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                <XAxis dataKey="label_vi" tick={{ fontSize: 10 }} interval={0} />
                <YAxis hide />
                <Tooltip formatter={(v) => (typeof v === "number" ? formatVnd(v) : String(v ?? ""))} />
                <Bar dataKey="total_vnd" fill="#a50064" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-2 space-y-1 text-sm">
            {data.map((c) => (
              <li key={c.category} className="flex justify-between">
                <span>{c.label_vi}</span>
                <span className="font-medium">{formatVnd(c.total_vnd)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
