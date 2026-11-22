import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EvalScenario } from "../src/types/api";
import { makeCheckResponse } from "./fixtures";

const apiMock = vi.hoisted(() => ({ scenarios: vi.fn(), runCase: vi.fn() }));
vi.mock("../src/services/api", () => ({ evalApi: apiMock }));

import DemoScenariosPage from "../src/pages/DemoScenariosPage";
import { GuardianProvider, useGuardian } from "../src/state/guardianStore";

function scenario(id: string, over: Partial<EvalScenario> = {}): EvalScenario {
  return {
    id,
    title_vi: `Tiêu đề ${id}`,
    description_vi: `Mô tả ${id}`,
    group: "red-risk",
    channel: "FLOW_B",
    requires_debug: false,
    cases: [
      {
        endpoint: "POST /api/flow-b/check?stream=false",
        request: { content: { origin: "PASTE", text: id } },
        expect: { decision_tier: "HARD_HOLD", reason_codes_include: ["RC_OK"] },
        headers: {},
      },
    ],
    ...over,
  };
}

const hard = (codes: string[]) => makeCheckResponse("HARD_HOLD", {}, { verdict: { ...makeCheckResponse("HARD_HOLD").verdict, reason_codes: codes } });

function Stats() {
  const { state } = useGuardian();
  return <p data-testid="checks">{state.shieldStats.checks}</p>;
}

function renderPage() {
  return render(
    <GuardianProvider>
      <Stats />
      <DemoScenariosPage />
    </GuardianProvider>,
  );
}

describe("DemoScenariosPage", () => {
  beforeEach(() => {
    apiMock.scenarios.mockReset();
    apiMock.runCase.mockReset();
  });

  it("lists scenarios with description and expectation", async () => {
    apiMock.scenarios.mockResolvedValue([scenario("T01"), scenario("T02")]);
    renderPage();
    const row = await screen.findByTestId("scenario-T01");
    expect(within(row).getByText("Mô tả T01")).toBeInTheDocument();
    expect(within(row).getByText(/HARD_HOLD · RC_OK/)).toBeInTheDocument();
    expect(screen.getByTestId("scenario-T02")).toBeInTheDocument();
  });

  it("runs one scenario, marks passed, and does not count it in shield stats", async () => {
    apiMock.scenarios.mockResolvedValue([scenario("T01")]);
    apiMock.runCase.mockResolvedValue(hard(["RC_OK"]));
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Chạy T01" }));
    expect(await within(screen.getByTestId("scenario-T01")).findByText("Đạt")).toBeInTheDocument();
    expect(apiMock.runCase).toHaveBeenCalledWith("POST /api/flow-b/check?stream=false", { content: { origin: "PASTE", text: "T01" } });
    expect(screen.getByTestId("checks")).toHaveTextContent("0");
  });

  it("shows actual tier and codes next to expected on failure", async () => {
    apiMock.scenarios.mockResolvedValue([scenario("T01")]);
    apiMock.runCase.mockResolvedValue(makeCheckResponse("ALLOW"));
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Chạy T01" }));
    const row = screen.getByTestId("scenario-T01");
    expect(await within(row).findByText("Không đạt")).toBeInTheDocument();
    expect(within(row).getAllByText("Mong đợi: HARD_HOLD · RC_OK")).toHaveLength(2);
    expect(within(row).getByText("Thực tế: ALLOW")).toBeInTheDocument();
  });

  it("runs all sequentially and reports passed/total, resolving prev placeholders", async () => {
    const chained = scenario("A01", {
      cases: [
        { endpoint: "POST /api/flow-b/check?stream=false", request: { x: 1 }, expect: { decision_tier: "HARD_HOLD" }, headers: {} },
        {
          endpoint: "POST /api/flow-a/check",
          request: { bank_bin: "{{prev.prefill.bank_bin}}" },
          expect: { decision_tier: "HARD_HOLD" },
          headers: {},
        },
      ],
    });
    apiMock.scenarios.mockResolvedValue([scenario("T01"), chained, scenario("T03")]);
    const order: string[] = [];
    apiMock.runCase.mockImplementation(async (endpoint: string, body: Record<string, unknown>) => {
      order.push(`${endpoint}|${JSON.stringify(body)}`);
      if (body["content"] && JSON.stringify(body).includes("T03")) return makeCheckResponse("ALLOW");
      return { ...hard(["RC_OK"]), prefill: { bank_bin: "970436" } };
    });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Chạy tất cả" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Đạt 2/3"));
    expect(order).toContain('POST /api/flow-a/check|{"bank_bin":"970436"}');
    expect(order.indexOf(order.find((o) => o.includes("T01")) as string)).toBeLessThan(order.findIndex((o) => o.includes("flow-a")));
    expect(screen.getByTestId("checks")).toHaveTextContent("0");
  });

  it("disables debug-only scenarios when the debug block is hidden", async () => {
    apiMock.scenarios.mockResolvedValue([scenario("T22", { requires_debug: true }), scenario("T01")]);
    renderPage();
    expect(await screen.findByRole("button", { name: "Chạy T22" })).toBeDisabled();
    expect(screen.getByText(/GUARDIAN_DEBUG/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Đạt 0/1");
  });

  it("shows an error when the list cannot be loaded", async () => {
    apiMock.scenarios.mockRejectedValue(new Error("down"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được");
  });
});
