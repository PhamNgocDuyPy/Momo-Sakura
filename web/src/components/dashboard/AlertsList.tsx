import { formatVnd } from "../../lib/amount";
import type { WalletAlert, WalletSummary } from "../../types/api";

export interface AlertNames {
  bills?: WalletSummary["bills"];
  subscriptions?: WalletSummary["subscriptions"];
}

/** `2026-06-30` or an ISO timestamp to `30/06/2026`; anything else is shown unchanged. */
function viDate(s: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : s;
}

function providerName(id: string, names: AlertNames): string {
  return names.bills?.find((b) => b.provider_id === id)?.provider_name ?? id;
}

function subscriptionName(id: string, names: AlertNames): string {
  return names.subscriptions?.find((s) => s.id === id)?.name ?? id;
}

export function alertText(a: WalletAlert, names: AlertNames = {}): string {
  switch (a.type) {
    case "BILL_SPIKE":
      return `Hóa đơn ${providerName(a.provider_id, names)} tăng ${a.increase_percent}% so với trung bình 3 kỳ (${formatVnd(a.current_vnd)} so với ${formatVnd(a.avg3_vnd)}).`;
    case "RENEWAL_SOON":
      return `Gói ${subscriptionName(a.subscription_id, names)} gia hạn ${
        a.days_left === 0 ? "hôm nay" : `sau ${a.days_left} ngày`
      }, ngày ${viDate(a.renewal_date)}, số tiền ${formatVnd(a.amount_vnd)}.`;
    case "UNUSED_SUBSCRIPTION":
      return `Gói ${subscriptionName(a.subscription_id, names)} chưa dùng trong ${a.days_since_last_use} ngày.`;
  }
}

/** Short follow-up suggestion shown under the alert, when there is one. */
export function alertHint(a: WalletAlert): string | null {
  return a.type === "UNUSED_SUBSCRIPTION"
    ? "Bạn có thể cân nhắc hủy gói này để tiết kiệm chi phí."
    : null;
}

const STYLE: Record<WalletAlert["type"], { box: string; label: string }> = {
  BILL_SPIKE: { box: "bg-red-50 text-red-900", label: "Hóa đơn tăng" },
  RENEWAL_SOON: { box: "bg-yellow-50 text-yellow-900", label: "Sắp gia hạn" },
  UNUSED_SUBSCRIPTION: { box: "bg-sky-50 text-sky-900", label: "Gói ít dùng" },
};

function alertKey(a: WalletAlert): string {
  return a.type === "BILL_SPIKE" ? `${a.type}:${a.provider_id}` : `${a.type}:${a.subscription_id}`;
}

export default function AlertsList({ alerts, ...names }: { alerts: WalletAlert[] } & AlertNames) {
  return (
    <section aria-labelledby="alerts-title" className="rounded-xl bg-white p-4 shadow-sm">
      <h2 id="alerts-title" className="mb-2 text-base font-semibold">
        Cảnh báo
      </h2>
      {alerts.length === 0 ? (
        <p className="text-sm text-gray-500">Không có cảnh báo nào.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {alerts.map((a) => {
            const hint = alertHint(a);
            return (
              <li key={alertKey(a)} data-alert-type={a.type} className={`rounded-lg p-3 ${STYLE[a.type].box}`}>
                <p className="text-xs font-semibold uppercase tracking-wide opacity-80">{STYLE[a.type].label}</p>
                <p>{alertText(a, names)}</p>
                {hint && (
                  <p data-testid="alert-hint" className="mt-1 text-xs font-medium">
                    {hint}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
