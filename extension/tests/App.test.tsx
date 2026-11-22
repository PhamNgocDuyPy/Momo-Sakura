import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/content/App";
import { mountGuardian } from "../src/content/mountGuardian";
import { finalLine, installChromeStorage, makeFakePort, makeResponse, type FakePort } from "./helpers";
import { parseNdjsonLine } from "../src/shared/ndjson";
import type { FinalEvent } from "../src/shared/types";

let port: FakePort;
let runtimeListeners: ((m: unknown) => void)[];

function installRuntime(): void {
  installChromeStorage();
  port = makeFakePort();
  runtimeListeners = [];
  const g = globalThis as unknown as { chrome: Record<string, unknown> };
  g.chrome = {
    ...g.chrome,
    runtime: {
      connect: vi.fn(() => port),
      onMessage: {
        addListener: (f: (m: unknown) => void) => void runtimeListeners.push(f),
        removeListener: (f: (m: unknown) => void) => void (runtimeListeners = runtimeListeners.filter((x) => x !== f)),
      },
    },
  };
}

beforeEach(installRuntime);
afterEach(() => {
  document.getElementById("m")?.remove();
  document.documentElement.querySelectorAll("momo-guardian-root").forEach((n) => n.remove());
  window.getSelection()?.removeAllRanges();
  vi.restoreAllMocks();
});

function select(text: string): void {
  const p = document.createElement("p");
  p.id = "m";
  p.textContent = text;
  document.body.append(p);
  const range = document.createRange();
  range.selectNodeContents(document.getElementById("m") as HTMLElement);
  window.getSelection()?.removeAllRanges();
  window.getSelection()?.addRange(range);
}

describe("App", () => {
  it("sends the selection as EXTENSION_SELECTION when the bubble is tapped, then shows the result", async () => {
    render(<App />);
    select("Đây là Công an quận 1");
    const bubble = screen.getByTestId("guardian-bubble");
    fireEvent.pointerDown(bubble, { clientX: 5, clientY: 5 });
    fireEvent.pointerUp(bubble, { clientX: 5, clientY: 5 });

    expect(port.postMessage).toHaveBeenCalledWith({
      type: "check",
      text: "Đây là Công an quận 1",
      origin: "EXTENSION_SELECTION",
    });
    expect(screen.getByTestId("scan-animation")).toBeInTheDocument();

    const final = parseNdjsonLine(finalLine(makeResponse())) as FinalEvent;
    act(() => port.receiveFromBackground({ type: "final", response: final.response }));
    expect(await screen.findByTestId("result-panel")).toHaveAttribute("data-tier", "HARD_HOLD");
  });

  it("tells the user when there is nothing to check, without calling the backend", () => {
    render(<App />);
    const bubble = screen.getByTestId("guardian-bubble");
    fireEvent.pointerDown(bubble, { clientX: 5, clientY: 5 });
    fireEvent.pointerUp(bubble, { clientX: 5, clientY: 5 });
    expect(port.postMessage).not.toHaveBeenCalled();
    expect(screen.getByTestId("error-message")).toHaveTextContent("Không thấy đoạn văn bản");
  });

  it("starts a check from the service worker's trigger message (menu / Alt+G)", () => {
    render(<App />);
    act(() => runtimeListeners.forEach((f) => f({ type: "guardian-trigger", selectionText: "văn bản từ menu" })));
    expect(port.postMessage).toHaveBeenCalledWith({
      type: "check",
      text: "văn bản từ menu",
      origin: "EXTENSION_SELECTION",
    });
  });

  it("shows a Vietnamese error, not a verdict, when the worker reports a failure; Esc closes", async () => {
    render(<App />);
    act(() => runtimeListeners.forEach((f) => f({ type: "guardian-trigger", selectionText: "abc" })));
    act(() => port.receiveFromBackground({ type: "error", message_vi: "Không kết nối được tới MoMo Guardian." }));
    expect(await screen.findByTestId("error-message")).toHaveTextContent("Không kết nối được");
    expect(screen.queryByTestId("result-panel")).toBeNull();
    fireEvent.keyDown(window, { key: "Escape" });
    await vi.waitFor(() => expect(screen.queryByTestId("guardian-overlay")).toBeNull());
  });
});

describe("mountGuardian", () => {
  it("creates a Shadow DOM host with inlined CSS and reads nothing from the page before a user action", () => {
    const walker = vi.spyOn(document, "createTreeWalker");
    const getSelection = vi.spyOn(window, "getSelection");
    const mounted = mountGuardian(".x{color:red}");
    expect(mounted).not.toBeNull();
    const host = document.querySelector("momo-guardian-root") as HTMLElement;
    expect(host.shadowRoot).not.toBeNull();
    expect(host.shadowRoot?.querySelector("style")?.textContent).toBe(".x{color:red}");
    // React walks its own roots; the page body (what capture.ts walks) must stay untouched.
    expect(walker.mock.calls.some(([root]) => root === document.body)).toBe(false);
    expect(getSelection).not.toHaveBeenCalled();
    expect(mountGuardian(".x{}")).toBeNull(); // no duplicate host
    mounted?.root.unmount();
  });
});