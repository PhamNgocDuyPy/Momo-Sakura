import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AlertsList from "../components/dashboard/AlertsList";
import BillsAndSubscriptions from "../components/dashboard/BillsAndSubscriptions";
import BudgetList from "../components/dashboard/BudgetList";
import RecentTransactions from "../components/dashboard/RecentTransactions";
import ShieldCard from "../components/dashboard/ShieldCard";
import SpendingChart from "../components/dashboard/SpendingChart";
import SandboxBadge from "../components/guardian/SandboxBadge";
import { api } from "../services/api";
import { emptyShieldStats, useGuardianOptional } from "../state/guardianStore";
import type { WalletSummary } from "../types/api";

export default function DashboardPage() {
  const guardian = useGuardianOptional();
  const [summary, setSummary] = useState<WalletSummary | null>(null);
  const [error, setError] = useState(false);
  const dispatch = guardian?.dispatch;

  useEffect(() => {
    let cancelled = false;
    api
      .walletSummary()
      .then((s) => {
        if (cancelled) return;
        setSummary(s);
        dispatch?.({ type: "SYNC_SHIELD_STATS", stats: s.shield_stats });
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  const stats = guardian?.state.shieldStats ?? summary?.shield_stats ?? emptyShieldStats;

  return (
    <main className="mx-auto max-w-md space-y-3 bg-gray-50 p-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Tổng quan</h1>
        <div className="flex items-center gap-2">
          <Link to="/demo" className="text-sm text-pink-600 underline">
            Kịch bản demo
          </Link>
          {(summary?.sandbox ?? true) && <SandboxBadge />}
        </div>
      </header>
      {error && (
        <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">
          Không tải được dữ liệu ví. Vui lòng thử lại sau.
        </p>
      )}
      {!summary && !error && <p className="text-sm text-gray-500">Đang tải...</p>}
      <ShieldCard stats={stats} />
      {summary && (
        <>
          <SpendingChart data={summary.spending_by_category} />
          <BudgetList budgets={summary.budgets} />
          <RecentTransactions transactions={summary.recent_transactions} />
          <BillsAndSubscriptions bills={summary.bills} subscriptions={summary.subscriptions} />
          <AlertsList alerts={summary.alerts} bills={summary.bills} subscriptions={summary.subscriptions} />
        </>
      )}
    </main>
  );
}
