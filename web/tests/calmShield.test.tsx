import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CalmShield, { CALM_BANNER_VI } from "../src/components/guardian/CalmShield";
import ResultCard from "../src/components/guardian/ResultCard";
import { makeCheckResponse } from "./fixtures";

function installVoices(voices: { lang: string; name: string }[]) {
  Object.defineProperty(window, "speechSynthesis", {
    value: {
      getVoices: () => voices,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      speak: vi.fn(),
      cancel: vi.fn(),
    },
    configurable: true,
  });
  vi.stubGlobal("SpeechSynthesisUtterance", class {});
}

afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(window, "speechSynthesis");
});

function renderShield(calm: boolean) {
  const response = makeCheckResponse(
    "SOFT_FRICTION",
    {
      calm_shield: calm,
      hotline: "1900 5454 41",
      trusted_contacts: [{ name: "Mẹ", phone: "0901 234 567" }],
    },
    {
      extensions: {
        promo: { brand: "Shop", promo_code: null, matched: false, official_promo: null },
      },
    },
  );
  render(
    <CalmShield hints={response.ui_hints} bullets={response.verdict.evidence_bullets} onContinue={() => undefined}>
      <ResultCard response={response} />
    </CalmShield>,
  );
}

describe("CalmShield", () => {
  it("shows banner, at most 3 bullets, hides promo, and the primary button", () => {
    renderShield(true);
    expect(screen.getByTestId("calm-banner")).toHaveTextContent(CALM_BANNER_VI);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.queryByTestId("promo-panel")).toBeNull();
    expect(screen.getByRole("button", { name: "Tạm dừng & xác minh" })).toBeInTheDocument();
    expect(screen.getByTestId("calm-continue")).toBeInTheDocument();
  });

  it("links tel: to the hotline and trusted contacts", () => {
    renderShield(true);
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("tel:1900545441");
    expect(hrefs).toContain("tel:0901234567");
  });

  it("renders nothing extra when calm_shield is off", () => {
    renderShield(false);
    expect(screen.queryByTestId("calm-shield")).toBeNull();
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    expect(screen.getByTestId("promo-panel")).toBeInTheDocument();
  });

  it("shows the read-aloud button only with a Vietnamese voice", async () => {
    installVoices([{ lang: "vi-VN", name: "vi" }]);
    renderShield(true);
    await waitFor(() => expect(screen.getByTestId("calm-read-aloud")).toBeInTheDocument());
  });

  it("hides the read-aloud button without a Vietnamese voice", async () => {
    installVoices([{ lang: "en-US", name: "en" }]);
    vi.useFakeTimers();
    renderShield(true);
    await vi.advanceTimersByTimeAsync(1200);
    vi.useRealTimers();
    expect(screen.queryByTestId("calm-read-aloud")).toBeNull();
  });
});
