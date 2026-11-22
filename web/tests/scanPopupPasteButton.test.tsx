import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GuardianProvider, initialGuardianState } from "../src/state/guardianStore";
import ScanPopup from "../src/components/guardian/ScanPopup";
import {
  CLIPBOARD_DENIED_MESSAGE_VI,
  CLIPBOARD_EMPTY_MESSAGE_VI,
  resetClipboardDedupe,
} from "../src/services/clipboard";

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
  return { ...actual, api: { nameConfirm: vi.fn(), nameInquiry: vi.fn() } };
});
import { streamFlowBCheck } from "../src/services/ndjson";

const stream = vi.mocked(streamFlowBCheck);

function setClipboard(readText: (() => Promise<string>) | undefined): void {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: readText ? { readText } : undefined,
  });
}

function renderPopup() {
  return render(
    <GuardianProvider
      initialState={{ ...initialGuardianState, popup: { ...initialGuardianState.popup, open: true } }}
    >
      <ScanPopup />
    </GuardianProvider>,
  );
}

beforeEach(() => {
  localStorage.clear(); // auto-scan opt-in stays off: only the button reads the clipboard
  resetClipboardDedupe();
  vi.clearAllMocks();
  stream.mockResolvedValue({ stage2: null, final: null, interrupted: true });
});
afterEach(() => {
  setClipboard(undefined);
});

describe("ScanPopup · Dán & kiểm tra", () => {
  it("renders as the first, prominent action above the paste box", () => {
    renderPopup();
    const btn = screen.getByTestId("paste-and-check");
    expect(btn).toHaveTextContent("Dán & kiểm tra");
    const box = screen.getByLabelText(/Dán nội dung/);
    expect(btn.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("reads the clipboard on click and submits to Flow B with origin CLIPBOARD", async () => {
    const readText = vi.fn().mockResolvedValue("ck gấp 2 lít vào stk 0123456789");
    setClipboard(readText);
    renderPopup();
    expect(readText).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("paste-and-check"));
    expect(readText).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(stream).toHaveBeenCalledTimes(1));
    expect(stream.mock.calls[0]![0]).toMatchObject({
      content: { origin: "CLIPBOARD", text: "ck gấp 2 lít vào stk 0123456789" },
    });
  });

  it("submits the same text again on a second tap (no dedupe for an explicit action)", async () => {
    setClipboard(vi.fn().mockResolvedValue("abc"));
    renderPopup();
    fireEvent.click(screen.getByTestId("paste-and-check"));
    await waitFor(() => expect(stream).toHaveBeenCalledTimes(1));
    await screen.findByTestId("paste-and-check");
    fireEvent.click(screen.getByTestId("paste-and-check"));
    await waitFor(() => expect(stream).toHaveBeenCalledTimes(2));
  });

  it("shows the Vietnamese notice and focuses the paste box on NotAllowedError", async () => {
    setClipboard(vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError")));
    renderPopup();
    fireEvent.click(screen.getByTestId("paste-and-check"));
    expect(await screen.findByTestId("popup-notice")).toHaveTextContent(CLIPBOARD_DENIED_MESSAGE_VI);
    expect(screen.getByLabelText(/Dán nội dung/)).toHaveFocus();
    expect(stream).not.toHaveBeenCalled();
  });

  it("shows the same notice and focuses the paste box when the Clipboard API is unsupported", async () => {
    setClipboard(undefined);
    renderPopup();
    fireEvent.click(screen.getByTestId("paste-and-check"));
    expect(await screen.findByTestId("popup-notice")).toHaveTextContent(CLIPBOARD_DENIED_MESSAGE_VI);
    expect(screen.getByLabelText(/Dán nội dung/)).toHaveFocus();
    expect(stream).not.toHaveBeenCalled();
  });

  it("shows a short notice for an empty clipboard and does not submit", async () => {
    setClipboard(vi.fn().mockResolvedValue("   "));
    renderPopup();
    fireEvent.click(screen.getByTestId("paste-and-check"));
    expect(await screen.findByTestId("popup-notice")).toHaveTextContent(CLIPBOARD_EMPTY_MESSAGE_VI);
    expect(stream).not.toHaveBeenCalled();
  });
});
