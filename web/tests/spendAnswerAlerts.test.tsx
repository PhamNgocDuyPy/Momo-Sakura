import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("recharts", () => {
  const Box = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  return {
    ResponsiveContainer: Box,
    BarChart: ({ data }: { data: unknown[] }) => <div data-testid="bars" data-count={data.length} />,
    Bar: Box,
    XAxis: Box,
    YAxis: Box,
    Tooltip: Box,
  };
});

import SpendAnswer from "../src/components/guardian/SpendAnswer";
import AlertsList from "../src/components/dashboard/AlertsList";
import type { SpendAnswerResult, WalletAlert } from "../src/types/api";

const ANSWER: SpendAnswerResult = {
  type: "SPEND_ANSWER",
  value: 1500000,
  unit: "VND",
  previous_value: 1000000,
  delta_percent: 50,
  range: { from: "2026-06-01T00:00:00+07:00", to: "2026-06-30T00:00:00+07:00" },
  series: [
    { bucket: "2026-06-01", value: 500000 },
    { bucket: "2026-06-02", value: 1000000 },
  ],
  bucket_unit: "DAY",
  answer_vi: "Tháng này bạn đã chi 1.500.000 đ.",
};

describe("SpendAnswer", () => {
  it("renders the template answer, value, delta and a chart with one bar per bucket", () => {
    render(<SpendAnswer answer={ANSWER} />);
    expect(screen.getByTestId("spend-answer-text")).toHaveTextContent("Tháng này bạn đã chi 1.500.000 đ.");
    expect(screen.getByTestId("spend-value")).toHaveTextContent("1.500.000 đ");
    expect(screen.getByTestId("spend-delta")).toHaveTextContent("Tăng 50%");
    expect(screen.getByTestId("bars")).toHaveAttribute("data-count", "2");
  });

  it("handles week buckets, COUNT unit, no delta and empty series", () => {
    render(
      <SpendAnswer
        answer={{ ...ANSWER, unit: "COUNT", value: 7, delta_percent: null, series: [], bucket_unit: "WEEK" }}
      />,
    );
    expect(screen.getByTestId("spend-value")).toHaveTextContent("7");
    expect(screen.queryByTestId("spend-delta")).toBeNull();
    expect(screen.queryByTestId("spend-chart")).toBeNull();
  });
});

describe("AlertsList", () => {
  const alerts: WalletAlert[] = [
    { type: "BILL_SPIKE", provider_id: "evn", current_vnd: 1300000, avg3_vnd: 1000000, increase_percent: 30 },
    { type: "RENEWAL_SOON", subscription_id: "s1", renewal_date: "2026-07-03", amount_vnd: 79000, days_left: 3 },
    { type: "UNUSED_SUBSCRIPTION", subscription_id: "s2", days_since_last_use: 45 },
  ];

  it("shows spike percent, renewal amount and date, and a cancel hint for unused plans", () => {
    render(
      <AlertsList
        alerts={alerts}
        bills={[{ provider_id: "evn", provider_name: "Điện EVN", period: "2026-06", amount_vnd: 1, due_date: "x", status: "UNPAID" }]}
        subscriptions={[
          { id: "s1", name: "Nhạc VIP", amount_vnd: 79000, renewal_date: "2026-07-03", last_used_at: null },
          { id: "s2", name: "Phim Plus", amount_vnd: 99000, renewal_date: "2026-07-10", last_used_at: null },
        ]}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Điện EVN");
    expect(items[0]).toHaveTextContent("tăng 30%");
    expect(items[1]).toHaveTextContent("Nhạc VIP");
    expect(items[1]).toHaveTextContent("79.000 đ");
    expect(items[1]).toHaveTextContent("03/07/2026");
    expect(items[2]).toHaveTextContent("45 ngày");
    expect(screen.getByTestId("alert-hint")).toHaveTextContent(/hủy/);
    expect(screen.getAllByTestId("alert-hint")).toHaveLength(1);
  });
});
