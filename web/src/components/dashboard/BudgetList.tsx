import { formatVnd } from "../../lib/amount";
import type { WalletSummary } from "../../types/api";

type Budget = WalletSummary["budgets"][number];

/** Bar colour from the integer percentage: yellow from 80%, red from 100%. */
export function budgetColor(percentUsed: number): "green" | "yellow" | "red" {
  if (percentUsed >= 100) return "red";
  if (percentUsed >= 80) return "yellow";
  return "green";
}

const BAR_CLASS = { green: "bg-green-500", yellow: "bg-yellow-400", red: "bg-red-500" } as const;

export default function BudgetList({ budgets }: { budgets: Budget[] }) {
  return (
    <section aria-labelledby="budget-title" className="rounded-xl bg-white p-4 shadow-sm">
      <h2 id="budget-title" className="mb-2 text-base font-semibold">
        Ngân sách tháng này
      </h2>
      {budgets.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa đặt ngân sách.</p>
      ) : (
        <ul className="space-y-3">
          {budgets.map((b) => {
            const color = budgetColor(b.percent_used);
            return (
              <li key={b.category} data-testid={`budget-${b.category}`} data-color={color}>
                <div className="flex justify-between text-sm">
                  <span>{b.label_vi}</span>
                  <span>
                    {formatVnd(b.spent_vnd)} / {formatVnd(b.limit_vnd)} ({b.percent_used}%)
                  </span>
                </div>
                <div className="mt-1 h-2 w-full rounded bg-gray-200">
                  <div
                    className={`h-2 rounded ${BAR_CLASS[color]}`}
                    style={{ width: `${Math.min(b.percent_used, 100)}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
