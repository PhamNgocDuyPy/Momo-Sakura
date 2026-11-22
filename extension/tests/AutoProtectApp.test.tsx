import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/content/App";
import { CHIP_TAG } from "../src/content/autoProtect";
import { AUTO_PROTECT_KEY } from "../src/shared/autoProtect";
import { installChromeStorage, makeFakePort, type FakePort } from "./helpers";

const SCAM = "Chuyển gấp cho em 100k đi chị, em vừa mới đổi tài khoản nên chuyển vào tài khoản này nhé : 0378582085 tpbank";
let port: FakePort;
let store: Record<string, unknown>;

function install(initial: Record<string, unknown> = {}): void {
  store = installChromeStorage(initial);
  port = makeFakePort();
  const g = globalThis as unknown as { chrome: Record<string, unknown> };
  g.chrome = {
    ...g.chrome,
    runtime: {
      connect: vi.fn(() => port),
      onMessage: { addListener: vi.fn(), removeListener: vi.fn() },
    },
  };
}
const chips = (): HTMLElement[] => Array.from(document.querySelectorAll<HTMLElement>(CHIP_TAG));
function addMessage(text: string): void {
  const d = document.createElement("div");
  d.textContent = text;
  document.body.append(d);
}

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("App · Tự động bảo vệ", () => {
  beforeEach(() => install());

  it("is off by default: no chips appear and the toggle shows Tắt", async () => {
    render(<App />);
    expect(await screen.findByTestId("guardian-auto-toggle")).toHaveTextContent("Tắt");
    addMessage(SCAM);
    await new Promise((r) => setTimeout(r, 450));
    expect(chips()).toHaveLength(0);
  });

  it("toggle turns it on for this hostname and persists it", async () => {
    render(<App />);
    const toggle = await screen.findByTestId("guardian-auto-toggle");
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveTextContent("Bật"));
    await waitFor(() => expect(store[AUTO_PROTECT_KEY]).toEqual({ [window.location.hostname]: true }));
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveTextContent("Tắt"));
    await waitFor(() => expect(store[AUTO_PROTECT_KEY]).toEqual({}));
  });

  it("when on, a new scam message gets a chip; clicking it posts that text with EXTENSION_SELECTION and opens the overlay", async () => {
    install({ [AUTO_PROTECT_KEY]: { [window.location.hostname]: true } });
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("guardian-auto-toggle")).toHaveTextContent("Bật"));
    addMessage(SCAM);
    await waitFor(() => expect(chips()).toHaveLength(1), { timeout: 2000 });
    expect(port.postMessage).not.toHaveBeenCalled(); // nothing leaves until the click
    await act(async () => {
      chips()[0]!.shadowRoot!.querySelector("button")!.click();
    });
    expect(port.postMessage).toHaveBeenCalledWith({ type: "check", text: SCAM, origin: "EXTENSION_SELECTION" });
    expect(await screen.findByTestId("guardian-overlay")).toBeInTheDocument();
  });

  it("turning it off removes the chips", async () => {
    install({ [AUTO_PROTECT_KEY]: { [window.location.hostname]: true } });
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("guardian-auto-toggle")).toHaveTextContent("Bật"));
    addMessage(SCAM);
    await waitFor(() => expect(chips()).toHaveLength(1), { timeout: 2000 });
    fireEvent.click(screen.getByTestId("guardian-auto-toggle"));
    await waitFor(() => expect(chips()).toHaveLength(0));
  });
});