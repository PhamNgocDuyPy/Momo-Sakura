import { formatVnd } from "../../lib/amount";
import type { WalletSummary } from "../../types/api";

export function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

export default function RecentTransactions({
  transactions,
}: {
  transactions: WalletSummary["recent_transactions"];
}) {
  return (
    <section aria-labelledby="recent-title" className="rounded-xl bg-white p-4 shadow-sm">
      <h2 id="recent-title" className="mb-2 text-base font-semibold">
        Giao dịch gần đây
      </h2>
      {transactions.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa có giao dịch.</p>
      ) : (
        <ul className="divide-y">
          {transactions.slice(0, 10).map((t) => (
            <li key={t.id} className="flex items-center justify-between py-2 text-sm">
              <div>
                <div className="font-medium">{t.counterparty}</div>
                <div className="text-xs text-gray-500">{formatDate(t.at)}</div>
              </div>
              <div className={t.direction === "IN" ? "text-green-600" : "text-gray-900"}>
                {t.direction === "IN" ? "+" : "-"}
                {formatVnd(t.amount_vnd)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
