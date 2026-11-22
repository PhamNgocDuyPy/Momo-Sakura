import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TransferNowButton from "../src/components/guardian/TransferNowButton";
import ResultCard from "../src/components/guardian/ResultCard";
import { resolveIntegrity } from "../src/pages/TransferPage";
import { makeCheckResponse } from "./fixtures";

describe("TransferNowButton", () => {
  it("shows on ALLOW and opens transfer with prefill and origin verdict", () => {
    const onTransfer = vi.fn();
    const res = makeCheckResponse("ALLOW", { show_transfer_now: true });
    render(<TransferNowButton response={res} confirmationToken="tok_1" onTransfer={onTransfer} />);
    fireEvent.click(screen.getByRole("button", { name: "Chuyển ngay" }));
    expect(onTransfer).toHaveBeenCalledWith({
      prefill: res.prefill,
      origin_verdict_id: "v_1",
      confirmation_token: "tok_1",
    });
  });

  it("is hidden on HARD_HOLD even if hints say show", () => {
    const res = makeCheckResponse("HARD_HOLD", { show_transfer_now: true });
    render(
      <ResultCard response={res}>
        <TransferNowButton response={res} onTransfer={vi.fn()} />
      </ResultCard>,
    );
    expect(screen.queryByText("Chuyển ngay")).toBeNull();
  });

  it("asks for missing fields before navigating", () => {
    const onTransfer = vi.fn();
    const res = makeCheckResponse("SOFT_FRICTION", { missing_fields: ["amount_vnd"] });
    render(<TransferNowButton response={res} onTransfer={onTransfer} />);
    fireEvent.click(screen.getByTestId("transfer-now"));
    const submit = screen.getByRole("button", { name: "Tiếp tục" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Số tiền"), { target: { value: "2 lít" } });
    fireEvent.click(submit);
    expect(onTransfer.mock.calls[0][0].prefill.amount_vnd).toBe(200000);
  });
});

describe("resolveIntegrity", () => {
  const values = { bankBin: "970436", accountNumber: "0123456789", amountText: "1", memo: "" };
  const prefill = makeCheckResponse().prefill!;

  it("uses OCR_CONFIRMED_BY_USER with token when account is unchanged", () => {
    expect(resolveIntegrity({ prefill, confirmation_token: "t" }, values)).toEqual({
      sourceIntegrity: "OCR_CONFIRMED_BY_USER",
      confirmationToken: "t",
    });
  });

  it("falls back to USER_TYPED after two-step confirm or edits", () => {
    expect(resolveIntegrity({ prefill }, values).sourceIntegrity).toBe("USER_TYPED");
    expect(
      resolveIntegrity({ prefill, confirmation_token: "t" }, { ...values, accountNumber: "999999" }),
    ).toEqual({ sourceIntegrity: "USER_TYPED", confirmationToken: null });
    expect(resolveIntegrity(null, values).sourceIntegrity).toBe("USER_TYPED");
  });
});

describe("ResultCard extensions", () => {
  it("shows listing prices, percent cheaper and safe payment tips", () => {
    const res = makeCheckResponse(
      "SOFT_FRICTION",
      { safe_payment_tips: true },
      {
        extensions: {
          listing: {
            product_category: "phone",
            product_key: null,
            listed_price_vnd: 5000000,
            reference_price_vnd: 10000000,
            discount_percent: 50,
            requires_deposit: true,
          },
          promo: {
            brand: "Shopee",
            promo_code: null,
            matched: true,
            official_promo: { title_vi: "Giảm 10%", valid_to: "2026-06-30" },
          },
        },
      },
    );
    render(<ResultCard response={res} />);
    expect(screen.getByTestId("listing-listed")).toHaveTextContent("5.000.000");
    expect(screen.getByTestId("listing-reference")).toHaveTextContent("10.000.000");
    expect(screen.getByTestId("listing-cheaper")).toHaveTextContent("50%");
    expect(screen.getByTestId("safe-payment-tips")).toHaveTextContent("COD");
    expect(screen.getByTestId("promo-official")).toHaveTextContent("30/06/2026");
    expect(document.body.textContent).not.toMatch(/100% an toàn/);
  });
});
