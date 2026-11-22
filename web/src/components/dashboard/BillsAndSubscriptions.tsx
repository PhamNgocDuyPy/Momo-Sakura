import { formatVnd } from "../../lib/amount";
import type { WalletSummary } from "../../types/api";
import { formatDate } from "./RecentTransactions";

export default function BillsAndSubscriptions({
  bills,
  subscriptions,
}: {
  bills: WalletSummary["bills"];
  subscriptions: WalletSummary["subscriptions"];
}) {
  return (
    <section aria-labelledby="bills-title" className="rounded-xl bg-white p-4 shadow-sm">
      <h2 id="bills-title" className="mb-2 text-base font-semibold">
        Hóa đơn và gói định kỳ
      </h2>
      {bills.length === 0 && subscriptions.length === 0 ? (
        <p className="text-sm text-gray-500">Không có hóa đơn hay gói định kỳ.</p>
      ) : (
        <ul className="divide-y text-sm">
          {bills.map((b) => (
            <li key={b.provider_id} className="flex justify-between py-2">
              <div>
                <div className="font-medium">{b.provider_name}</div>
                <div className="text-xs text-gray-500">Đến hạn {formatDate(b.due_date)}</div>
              </div>
              <div>{formatVnd(b.amount_vnd)}</div>
            </li>
          ))}
          {subscriptions.map((s) => (
            <li key={s.id} className="flex justify-between py-2">
              <div>
                <div className="font-medium">{s.name}</div>
                <div className="text-xs text-gray-500">Gia hạn {formatDate(s.renewal_date)}</div>
              </div>
              <div>{formatVnd(s.amount_vnd)}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
