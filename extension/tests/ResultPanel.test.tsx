import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ErrorPanel from "../src/content/ErrorPanel";
import Overlay from "../src/content/Overlay";
import ResultPanel from "../src/content/ResultPanel";
import { CALM_BANNER_VI } from "../src/content/tier";
import { makeResponse } from "./helpers";

const WEB = "http://localhost:5173";

describe("ResultPanel", () => {
  it("shows only verdict text, HARD styling, cooling note and small reason codes", () => {
    const { container } = render(<ResultPanel response={makeResponse()} webUrl={WEB} onClose={() => {}} />);
    const panel = screen.getByTestId("result-panel");
    expect(panel).toHaveAttribute("data-tier", "HARD_HOLD");
    expect(panel.className).toContain("border-red-400");
    expect(panel.className).toContain("bg-red-50");
    expect(screen.getByTestId("tier-label")).toHaveTextContent("Rất có dấu hiệu lừa đảo");
    expect(screen.getByText("Người gửi tự xưng là công an và đòi chuyển tiền gấp.")).toBeInTheDocument();
    expect(screen.getByTestId("system2")).toHaveTextContent("Cơ quan chức năng có bao giờ");
    expect(screen.getByTestId("cooling")).toHaveTextContent("1 phút");
    expect(screen.getByTestId("reason-codes")).toHaveTextContent("RC_AUTHORITY_COERCION");
    expect(container.textContent).not.toMatch(/100\s*%\s*an toàn/i);
    expect(screen.getByTestId("open-guardian")).toHaveAttribute("href", WEB);
    expect(screen.getByTestId("open-guardian")).toHaveAttribute("target", "_blank");
  });

  it("renders no free text beyond verdict fields and fixed labels", () => {
    const response = makeResponse();
    // Extra fields an LLM could fill must never reach the DOM.
    (response as unknown as Record<string, unknown>).reasoning_summary = "TEXT-FROM-LLM-SHOULD-NOT-APPEAR";
    (response.verdict as unknown as Record<string, unknown>).reasoning_summary = "TEXT-FROM-LLM-SHOULD-NOT-APPEAR";
    const { container } = render(<ResultPanel response={response} webUrl={WEB} onClose={() => {}} />);
    expect(container.textContent).not.toContain("TEXT-FROM-LLM");
  });

  it("styles ALLOW as green without claiming absolute safety", () => {
    const response = makeResponse();
    response.verdict = {
      decision_tier: "ALLOW",
      reason_codes: ["RC_NO_SCAM_SIGNAL_FOUND"],
      evidence_bullets: [],
      system2_check_questions: [],
      cooling_off_seconds: 0,
    };
    const { container } = render(<ResultPanel response={response} webUrl={WEB} onClose={() => {}} />);
    expect(screen.getByTestId("result-panel").className).toContain("bg-green-50");
    expect(screen.getByTestId("tier-label")).toHaveTextContent("Chưa thấy dấu hiệu bất thường");
    expect(container.textContent).not.toMatch(/100\s*%/);
    expect(container.textContent).not.toMatch(/tuyệt đối an toàn|hoàn toàn an toàn/i);
    expect(screen.queryByTestId("cooling")).toBeNull();
  });

  it("closes through the close button", () => {
    const onClose = vi.fn();
    render(<ResultPanel response={makeResponse()} webUrl={WEB} onClose={onClose} />);
    fireEvent.click(screen.getByTestId("result-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("Calm Shield", () => {
  const calm = () =>
    makeResponse({
      ui_hints: { calm_shield: true, hotline: "1900 5454 41" },
      verdict: {
        decision_tier: "HARD_HOLD",
        reason_codes: ["RC_AUTHORITY_COERCION"],
        evidence_bullets: ["Một", "Hai", "Ba", "Bốn"],
        system2_check_questions: ["Câu hỏi?"],
        cooling_off_seconds: 60,
      },
    });

  it("shows the banner, at most 3 bullets and a tel: link to the hotline", () => {
    render(<ResultPanel response={calm()} webUrl={WEB} onClose={() => {}} />);
    expect(screen.getByTestId("calm-shield")).toBeInTheDocument();
    expect(screen.getByTestId("calm-banner")).toHaveTextContent(CALM_BANNER_VI);
    expect(CALM_BANNER_VI).toBe("MoMo không bao giờ gọi điện yêu cầu bạn chuyển tiền");
    expect(screen.getByTestId("evidence").querySelectorAll("li")).toHaveLength(3);
    expect(screen.queryByText("Bốn")).toBeNull();
    expect(screen.getByTestId("calm-hotline")).toHaveAttribute("href", "tel:1900545441");
    expect(screen.getByTestId("tier-label").parentElement?.className).toContain("text-[1.125rem]");
  });

  it("omits the call link when there is no hotline", () => {
    const r = calm();
    r.ui_hints.hotline = null;
    render(<ResultPanel response={r} webUrl={WEB} onClose={() => {}} />);
    expect(screen.queryByTestId("calm-hotline")).toBeNull();
  });
});

describe("error path", () => {
  it("ErrorPanel shows the Vietnamese message and no verdict", () => {
    const { container } = render(<ErrorPanel message="Không kết nối được tới MoMo Guardian." onClose={() => {}} />);
    expect(screen.getByTestId("error-message")).toHaveTextContent("Không kết nối được");
    expect(container.textContent).not.toMatch(/ALLOW|Chưa thấy dấu hiệu bất thường/);
    expect(container.querySelector("[data-tier]")).toBeNull();
  });

  it("Overlay in error state shows no result panel and no ALLOW wording", () => {
    const { container } = render(
      <Overlay state={{ phase: "error", message: "MoMo Guardian phản hồi quá lâu. Vui lòng thử lại sau." }} webUrl={WEB} onClose={() => {}} />,
    );
    expect(screen.getByTestId("error-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("result-panel")).toBeNull();
    expect(container.textContent).not.toMatch(/ALLOW|Chưa thấy dấu hiệu bất thường/);
  });
});

describe("Overlay", () => {
  it("closes on Escape and on the close button", () => {
    const onClose = vi.fn();
    render(<Overlay state={{ phase: "scanning", charCount: 10 }} webUrl={WEB} onClose={onClose} />);
    expect(screen.getByTestId("scan-animation")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId("overlay-close"));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("shows the red alert on stage2 with red_alert", () => {
    render(
      <Overlay
        state={{
          phase: "stage2",
          charCount: 10,
          stage2: {
            event: "stage2",
            request_id: "r",
            provisional_tier: "HARD_HOLD",
            provisional_reason_codes: [],
            red_alert: true,
          },
        }}
        webUrl={WEB}
        onClose={() => {}}
      />,
    );
    expect(screen.getByTestId("stage2-red-alert")).toBeInTheDocument();
    expect(screen.getByTestId("scan-animation")).toBeInTheDocument();
  });

  it("renders nothing while idle", () => {
    const { container } = render(<Overlay state={{ phase: "idle" }} webUrl={WEB} onClose={() => {}} />);
    expect(container.textContent).toBe("");
  });
});