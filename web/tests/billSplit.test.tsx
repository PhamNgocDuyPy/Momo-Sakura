import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("qrcode", () => ({
  default: { toDataURL: vi.fn().mockResolvedValue("data:image/png;base64,AAA") },
}));
vi.mock("../src/services/api", async (orig) => {
  const actual = await orig<typeof import("../src/services/api")>();
  return { ...actual, api: { splitCompute: vi.fn() } };
});

import BillSplit from "../src/components/split/BillSplit";
import { ApiError, api } from "../src/services/api";
import type { SplitComputeResponse } from "../src/types/api";

const compute = vi.mocked(api.splitCompute);
const ITEMS = [
  { name: "Lẩu", quantity: 1, unit_price_vnd: 300000 },
  { name: "Bia", quantity: 2, unit_price_vnd: 50000 },
];

const OK: SplitComputeResponse = {
  status: "OK",
  total_vnd: 400000,
  items_sum_vnd: 400000,
  mismatch_vnd: 0,
  shares: [
    { participant_id: "p1", amount_vnd: 200000, is_payee: true, qr_payload: null, qr_status: "SKIPPED_PAYEE" },
    { participant_id: "p2", amount_vnd: 200000, is_payee: false, qr_payload: "0002...", qr_status: "VALID_VIETQR" },
  ],
};

beforeEach(() => vi.clearAllMocks());

describe("BillSplit", () => {
  it("shows editable items and sends an EQUAL split to /api/split/compute", async () => {
    compute.mockResolvedValue(OK);
    render(<BillSplit items={ITEMS} totalVnd={400000} />);
    expect(screen.getByLabelText("Tên món 1")).toHaveValue("Lẩu");
    fireEvent.change(screen.getByLabelText("Tên món 2"), { target: { value: "Bia lon" } });
    fireEvent.click(screen.getByTestId("split-compute"));
    await screen.findByTestId("split-result");
    const req = compute.mock.calls[0]![0];
    expect(req.mode).toBe("EQUAL");
    expect(req.receipt_total_vnd).toBe(400000);
    expect(req.items[1]!.name).toBe("Bia lon");
    expect(req.participants.map((p) => p.id)).toEqual(["p1", "p2"]);
    expect(req.assignments).toBeNull();
    // QR only for the non-payee person.
    await screen.findByTestId("share-qr-p2");
    expect(screen.queryByTestId("share-qr-p1")).toBeNull();
  });

  it("adds a person and blocks BY_ITEM until every item is assigned", async () => {
    compute.mockResolvedValue(OK);
    render(<BillSplit items={ITEMS} totalVnd={400000} />);
    fireEvent.change(screen.getByLabelText("Tên người mới"), { target: { value: "Lan" } });
    fireEvent.click(screen.getByText("Thêm"));
    expect(screen.getByText("Lan")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "Gán theo món" }));
    expect(screen.getByTestId("split-compute")).toBeDisabled();
    fireEvent.click(screen.getByTestId("assign-0-p1"));
    fireEvent.click(screen.getByTestId("assign-0-p3"));
    fireEvent.click(screen.getByTestId("assign-1-p2"));
    expect(screen.getByTestId("split-compute")).toBeEnabled();
    fireEvent.click(screen.getByTestId("split-compute"));
    await waitFor(() => expect(compute).toHaveBeenCalled());
    const req = compute.mock.calls[0]![0];
    expect(req.mode).toBe("BY_ITEM");
    expect(req.assignments).toEqual([
      { item_index: 0, participant_ids: ["p1", "p3"] },
      { item_index: 1, participant_ids: ["p2"] },
    ]);
  });

  it("shows the TOTAL_MISMATCH difference and no shares", async () => {
    compute.mockResolvedValue({
      status: "TOTAL_MISMATCH",
      total_vnd: 450000,
      items_sum_vnd: 400000,
      mismatch_vnd: 50000,
      shares: [],
    });
    render(<BillSplit items={ITEMS} totalVnd={450000} />);
    fireEvent.click(screen.getByTestId("split-compute"));
    const box = await screen.findByTestId("split-mismatch");
    expect(screen.getByTestId("split-mismatch-amount")).toHaveTextContent("50.000 đ");
    expect(box).toHaveTextContent("400.000 đ");
    expect(screen.queryByTestId("split-result")).toBeNull();
  });

  it("hides the QR for QR_ERROR shares and keeps the amount", async () => {
    compute.mockResolvedValue({
      ...OK,
      shares: [
        OK.shares[0]!,
        { participant_id: "p2", amount_vnd: 200000, is_payee: false, qr_payload: null, qr_status: "QR_ERROR" },
      ],
    });
    render(<BillSplit items={ITEMS} totalVnd={400000} />);
    fireEvent.click(screen.getByTestId("split-compute"));
    await screen.findByTestId("split-result");
    expect(screen.queryByTestId("share-qr-p2")).toBeNull();
    expect(screen.getByTestId("share-amount-p2")).toHaveTextContent("200.000 đ");
    expect(screen.getByTestId("split-qr-error")).toBeInTheDocument();
  });

  it("shows the Vietnamese message for API errors", async () => {
    compute.mockRejectedValue(new ApiError(422, { error: "UNASSIGNED_ITEMS", message_vi: "Còn món chưa có người chia." }));
    render(<BillSplit items={ITEMS} totalVnd={400000} />);
    fireEvent.click(screen.getByTestId("split-compute"));
    expect(await screen.findByTestId("split-error")).toHaveTextContent("Còn món chưa có người chia.");
  });
});
