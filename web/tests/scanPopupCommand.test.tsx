import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GuardianProvider, initialGuardianState, useGuardian } from "../src/state/guardianStore";
import ScanPopup from "../src/components/guardian/ScanPopup";
import { resetClipboardDedupe } from "../src/services/clipboard";
import type { AssistantCommandResponse, AssistantResult } from "../src/types/api";
import { makeCheck } from "./helpers/checkResponse";

vi.mock("recharts", () => {
  const Box = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  return { ResponsiveContainer: Box, BarChart: Box, Bar: Box, XAxis: Box, YAxis: Box, Tooltip: Box };
});
vi.mock("qrcode", () => ({ default: { toDataURL: vi.fn().mockResolvedValue("data:image/png;base64,AAA") } }));
vi.mock("../src/services/ndjson", () => ({ streamFlowBCheck: vi.fn() }));
vi.mock("../src/services/ocr", () => ({ recognizeText: vi.fn() }));
vi.mock("../src/services/qrDecode", () => ({
  decodeQrFromImage: vi.fn(),
  openQrCamera: vi.fn(),
  scanVideoForQr: vi.fn(),
  stopCamera: vi.fn(),
}));
vi.mock("../src/services/api", async (orig) => {
  const actual = await orig<typeof import("../src/services/api")>();
  return { ...actual, api: { assistantCommand: vi.fn(), nameConfirm: vi.fn(), nameInquiry: vi.fn(), splitCompute: vi.fn(), encodeQr: vi.fn() } };
});

import { streamFlowBCheck } from "../src/services/ndjson";
import { api } from "../src/services/api";

const command = vi.mocked(api.assistantCommand);
const stream = vi.mocked(streamFlowBCheck);

function reply(result: AssistantResult): AssistantCommandResponse {
  return { intent: "X", result, trace: [] };
}

const PREFILL = {
  bank_bin: "970436",
  account_number: "0123456789",
  amount_vnd: 200000,
  memo: null,
  source_integrity_for_flow_a: "USER_TYPED" as const,
};

function ModeProbe() {
  return <span data-testid="mode">{useGuardian().state.popup.mode}</span>;
}

function renderPopup(onTransferNow = vi.fn()) {
  render(
    <GuardianProvider initialState={{ ...initialGuardianState, popup: { ...initialGuardianState.popup, open: true } }}>
      <ScanPopup onTransferNow={onTransferNow} />
      <ModeProbe />
    </GuardianProvider>,
  );
  return onTransferNow;
}

function send(text: string): void {
  fireEvent.change(screen.getByLabelText("Lệnh cho Guardian"), { target: { value: text } });
  fireEvent.click(screen.getByTestId("command-send"));
}

beforeEach(() => {
  localStorage.clear();
  resetClipboardDedupe();
  vi.clearAllMocks();
});

describe("ScanPopup command box (F2)", () => {
  it("RESOLVED opens TransferPage with the prefill", async () => {
    command.mockResolvedValue(
      reply({
        type: "TRANSFER_RESOLUTION",
        status: "RESOLVED",
        contact: { id: "c1", display_name: "Lan", bank_bin: "970436", account_number: "0123456789" },
        candidates: [],
        prefill: PREFILL,
        message_vi: "Chuyển 200.000 đ cho Lan",
      }),
    );
    const onTransferNow = renderPopup();
    send("chuyển cho Lan 2 lít");
    await waitFor(() => expect(onTransferNow).toHaveBeenCalledWith({ prefill: PREFILL }));
    expect(command).toHaveBeenCalledWith("chuyển cho Lan 2 lít");
    expect(stream).not.toHaveBeenCalled();
  });

  it("AMBIGUOUS shows the ContactPicker and picking a contact opens TransferPage with the amount", async () => {
    command.mockResolvedValue(
      reply({
        type: "TRANSFER_RESOLUTION",
        status: "AMBIGUOUS",
        contact: null,
        candidates: [
          { id: "c1", display_name: "Lan A", bank_bin: "970436", account_number: "1111" },
          { id: "c2", display_name: "Lan B", bank_bin: "970415", account_number: "2222" },
        ],
        prefill: { ...PREFILL, bank_bin: null, account_number: null },
        message_vi: "Bạn muốn chuyển cho Lan nào?",
      }),
    );
    const onTransferNow = renderPopup();
    send("chuyển cho Lan 2 lít");
    await screen.findByTestId("contact-picker");
    fireEvent.click(screen.getByTestId("contact-c2"));
    expect(onTransferNow).toHaveBeenCalledTimes(1);
    const nav = onTransferNow.mock.calls[0]![0];
    expect(nav.prefill).toMatchObject({ bank_bin: "970415", account_number: "2222", amount_vnd: 200000 });
    expect(nav.prefill.source_integrity_for_flow_a).toBe("USER_TYPED");
  });

  it.each([
    [{ type: "TRANSFER_RESOLUTION", status: "NOT_FOUND", contact: null, candidates: [], prefill: null, message_vi: "Không thấy Lan trong danh bạ." }, "Không thấy Lan"],
    [{ type: "TRANSFER_RESOLUTION", status: "NEEDS_AMOUNT", contact: null, candidates: [], prefill: null, message_vi: "Bạn muốn chuyển bao nhiêu?" }, "bao nhiêu"],
    [{ type: "REPHRASE", message_vi: "Guardian chưa hiểu lệnh này.", examples_vi: ["chuyển cho Lan 2 lít"] }, "chưa hiểu"],
  ] as [AssistantResult, string][])("shows message_vi and examples for %#", async (result, text) => {
    command.mockResolvedValue(reply(result));
    renderPopup();
    send("abc");
    const box = await screen.findByTestId("command-message");
    expect(box).toHaveTextContent(text);
    expect(box).toHaveTextContent("Bạn có thể thử");
  });

  it.each(["SHOP", "PROMO", "SPLIT_BILL", "GENERAL"] as const)("OPEN_MODE switches the popup to %s", async (mode) => {
    command.mockResolvedValue(reply({ type: "OPEN_MODE", mode, message_vi: "Hãy dán nội dung." }));
    renderPopup();
    send("kiểm tra giúp mình");
    await screen.findByTestId("command-message");
    expect(screen.getByTestId("mode")).toHaveTextContent(mode);
  });

  it("SPEND_ANSWER renders SpendAnswer", async () => {
    command.mockResolvedValue(
      reply({
        type: "SPEND_ANSWER",
        value: 90000,
        unit: "VND",
        previous_value: null,
        delta_percent: null,
        range: { from: "2026-06-01T00:00:00+07:00", to: "2026-06-30T00:00:00+07:00" },
        series: [{ bucket: "2026-06-01", value: 90000 }],
        bucket_unit: "DAY",
        answer_vi: "Bạn đã chi 90.000 đ.",
      }),
    );
    renderPopup();
    send("tháng này tôi tiêu bao nhiêu");
    expect(await screen.findByTestId("spend-answer-text")).toHaveTextContent("Bạn đã chi 90.000 đ.");
  });

  it("in SPLIT_BILL mode a receipt verdict shows BillSplit with the OCR items", async () => {
    stream.mockImplementation(async (_req, o) => {
      const response = makeCheck({
        extensions: { receipt: { items: [{ name: "Lẩu", quantity: 1, unit_price_vnd: 300000 }], total_vnd: 300000, items_sum_vnd: 300000 } },
      });
      o?.onFinal?.({ event: "final", response });
      return { stage2: null, final: { event: "final", response }, interrupted: false };
    });
    render(
      <GuardianProvider
        initialState={{ ...initialGuardianState, popup: { ...initialGuardianState.popup, open: true, mode: "SPLIT_BILL" } }}
      >
        <ScanPopup />
      </GuardianProvider>,
    );
    fireEvent.change(screen.getByLabelText(/Dán nội dung/), { target: { value: "Lẩu 300.000" } });
    fireEvent.click(screen.getByText("Kiểm tra nội dung"));
    await screen.findByTestId("bill-split");
    expect(screen.getByLabelText("Tên món 1")).toHaveValue("Lẩu");
    expect(screen.queryByText(/100% an toàn/)).toBeNull();
  });

  it("attaches BankHandoff to the result card when the verdict has an account", async () => {
    stream.mockImplementation(async (_req, o) => {
      const response = makeCheck({ prefill: PREFILL });
      o?.onFinal?.({ event: "final", response });
      return { stage2: null, final: { event: "final", response }, interrupted: false };
    });
    renderPopup();
    fireEvent.change(screen.getByLabelText(/Dán nội dung/), { target: { value: "ck 2 lít vào 0123456789" } });
    fireEvent.click(screen.getByText("Kiểm tra nội dung"));
    expect(await screen.findByTestId("bank-handoff-button")).toBeEnabled();
  });
});
