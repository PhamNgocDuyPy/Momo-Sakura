import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("qrcode", () => ({
  default: { toDataURL: vi.fn().mockResolvedValue("data:image/png;base64,AAA") },
}));
vi.mock("../src/services/api", async (orig) => {
  const actual = await orig<typeof import("../src/services/api")>();
  return { ...actual, api: { encodeQr: vi.fn() } };
});

import BankHandoff from "../src/components/transfer/BankHandoff";
import { ApiError, api } from "../src/services/api";

const encode = vi.mocked(api.encodeQr);

function renderHandoff(over: Partial<React.ComponentProps<typeof BankHandoff>> = {}) {
  return render(
    <BankHandoff
      verdictId="v_9"
      tier="ALLOW"
      handoffAllowed
      bankBin="970436"
      accountNumber="0123456789"
      amountVnd={200000}
      memo="tien an"
      {...over}
    />,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("BankHandoff", () => {
  it("encodes with BANK_HANDOFF + verdict_id and shows QR, download and deeplink", async () => {
    encode.mockResolvedValue({
      payload: "000201...",
      verify: { result: "VALID_VIETQR" },
      deeplink: "vcb://pay?x=1",
    });
    renderHandoff();
    fireEvent.click(screen.getByTestId("bank-handoff-button"));
    await screen.findByTestId("bank-handoff-result");
    expect(encode).toHaveBeenCalledWith({
      purpose: "BANK_HANDOFF",
      verdict_id: "v_9",
      bank_bin: "970436",
      account_number: "0123456789",
      amount_vnd: 200000,
      memo: "tien an",
    });
    expect(screen.getByTestId("bank-handoff-download")).toHaveAttribute("download");
    expect(screen.getByTestId("bank-handoff-deeplink")).toHaveAttribute("href", "vcb://pay?x=1");
  });

  it("omits the deeplink when the bank has none", async () => {
    encode.mockResolvedValue({ payload: "000201...", verify: { result: "VALID_VIETQR" }, deeplink: null });
    renderHandoff();
    fireEvent.click(screen.getByTestId("bank-handoff-button"));
    await screen.findByTestId("bank-handoff-download");
    expect(screen.queryByTestId("bank-handoff-deeplink")).toBeNull();
  });

  it("is disabled for HARD_HOLD and never calls the API", () => {
    renderHandoff({ tier: "HARD_HOLD", handoffAllowed: false });
    const btn = screen.getByTestId("bank-handoff-button");
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(encode).not.toHaveBeenCalled();
    expect(screen.getByTestId("bank-handoff-blocked")).toBeInTheDocument();
  });

  it("is disabled when handoff_allowed is false", () => {
    renderHandoff({ handoffAllowed: false });
    expect(screen.getByTestId("bank-handoff-button")).toBeDisabled();
  });

  it("shows Vietnamese text for 403 and 409", async () => {
    encode.mockRejectedValueOnce(new ApiError(403, { error: "HANDOFF_BLOCKED_HARD_HOLD" }));
    renderHandoff();
    fireEvent.click(screen.getByTestId("bank-handoff-button"));
    await waitFor(() => expect(screen.getByTestId("bank-handoff-error")).toHaveTextContent(/tạm giữ/));
    expect(screen.queryByTestId("bank-handoff-result")).toBeNull();

    encode.mockRejectedValueOnce(new ApiError(409, { error: "COOLDOWN_NOT_FINISHED" }));
    fireEvent.click(screen.getByTestId("bank-handoff-button"));
    await waitFor(() => expect(screen.getByTestId("bank-handoff-error")).toHaveTextContent(/thời gian chờ/));
  });
});
