import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GuardianProvider, initialGuardianState, type GuardianState } from "../src/state/guardianStore";
import ScanPopup from "../src/components/guardian/ScanPopup";
import { resetClipboardDedupe, CLIPBOARD_OPTIN_KEY } from "../src/services/clipboard";
import type {
  CheckResponse,
  FlowBCheckRequest,
  FlowBStage2Event,
  NameConfirmation,
} from "../src/types/api";

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
import { recognizeText } from "../src/services/ocr";
import { decodeQrFromImage, openQrCamera } from "../src/services/qrDecode";
import { api } from "../src/services/api";

const stream = vi.mocked(streamFlowBCheck);

const NAME_CONF: NameConfirmation = {
  pending_id: "pc_1",
  display_name: "NGUYEN VAN MINH",
  bank_name: "Vietcombank",
  account_digits_spaced: "0 1 2 3",
  found: true,
  sandbox: true,
};

function makeResponse(over: Partial<CheckResponse> = {}): CheckResponse {
  return {
    request_id: "req_1",
    verdict_id: "v_1",
    channel: "FLOW_B",
    verdict: {
      decision_tier: "SOFT_FRICTION",
      reason_codes: [],
      evidence_bullets: ["Bằng chứng mẫu"],
      system2_check_questions: [],
      cooling_off_seconds: 15,
      requires_user_account_confirm: false,
      allow_fast_unblock: false,
    },
    ui_hints: {
      calm_shield: false,
      show_context_elicitation: false,
      safe_payment_tips: false,
      show_transfer_now: false,
      handoff_allowed: false,
      missing_fields: [],
      trusted_contacts: [],
      hotline: null,
    },
    qr: null,
    prefill: null,
    name_confirmation: null,
    signals: { scam_playbook: null, manipulation_cues: [], url_flags: [], prefilter_score: null },
    sandbox_sources: [],
    trace: [],
    rules_fired: [],
    stop_codes: [],
    stage_timings_ms: { stage2: 5, stage3: 100, total: 120 },
    latency_ms: 120,
    ...over,
  };
}

function makeStage2(over: Partial<FlowBStage2Event> = {}): FlowBStage2Event {
  return {
    event: "stage2",
    request_id: "req_1",
    provisional_tier: "HARD_HOLD",
    provisional_reason_codes: ["RC_VIETQR_TAMPERED_BAD_CRC"],
    red_alert: true,
    qr: null,
    urls: [],
    prefilter_score: 0,
    recipient_risk: null,
    elapsed_ms: 6,
    ...over,
  };
}

/** Flow B mock that resolves with a stage2 then final event, with a gate between them. */
function mockStream(opts: { stage2?: FlowBStage2Event; final?: CheckResponse; gate?: Promise<void> }) {
  stream.mockImplementation(async (_req, o) => {
    if (opts.stage2) o?.onStage2?.(opts.stage2);
    if (opts.gate) await opts.gate;
    if (opts.final) o?.onFinal?.({ event: "final", response: opts.final });
    return {
      stage2: opts.stage2 ?? null,
      final: opts.final ? { event: "final", response: opts.final } : null,
      interrupted: !opts.final,
    };
  });
}

function lastRequest(): FlowBCheckRequest {
  const call = stream.mock.calls[stream.mock.calls.length - 1];
  if (!call) throw new Error("streamFlowBCheck not called");
  return call[0];
}

function renderPopup(popup: Partial<GuardianState["popup"]> = {}) {
  return render(
    <GuardianProvider
      initialState={{
        ...initialGuardianState,
        popup: { ...initialGuardianState.popup, open: true, ...popup },
      }}
    >
      <ScanPopup />
    </GuardianProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  resetClipboardDedupe();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ScanPopup ↔ Flow B", () => {
  it("sends pasted text with origin PASTE, consent flag and mode, then shows stage2 and final", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((r) => {
      release = r;
    });
    mockStream({ stage2: makeStage2(), final: makeResponse(), gate });
    renderPopup({ mode: "SHOP" });

    fireEvent.click(screen.getByLabelText(/Cho phép lưu bằng chứng/));
    fireEvent.change(screen.getByLabelText(/Dán nội dung/), { target: { value: "ck 2 lít vào stk 0123" } });
    fireEvent.click(screen.getByText("Kiểm tra nội dung"));

    // Stage 2 arrived, final not yet: animation stays, provisional + red alert visible.
    expect(await screen.findByTestId("red-alert")).toBeInTheDocument();
    expect(screen.getByTestId("scan-animation")).toBeInTheDocument();
    expect(screen.getByTestId("stage2-provisional")).toBeInTheDocument();
    expect(screen.queryByTestId("final-result")).toBeNull();

    await act(async () => release());
    expect(await screen.findByTestId("final-result")).toBeInTheDocument();
    expect(screen.getByText("Bằng chứng mẫu")).toBeInTheDocument();
    expect(screen.getByText("Guardian đã quyết định thế nào")).toBeInTheDocument();
    expect(screen.queryByTestId("scan-animation")).toBeNull();
    expect(screen.queryByTestId("red-alert")).toBeNull();

    expect(lastRequest()).toMatchObject({
      content: { origin: "PASTE", text: "ck 2 lít vào stk 0123" },
      mode: "SHOP",
      explicit_consent_flag: true,
      linked_transaction: null,
    });
  });

  it("shows a neutral interruption note, no green and no transfer button, when the stream breaks", async () => {
    mockStream({ stage2: makeStage2({ red_alert: false, provisional_tier: "ALLOW" }) });
    renderPopup();
    fireEvent.change(screen.getByLabelText(/Dán nội dung/), { target: { value: "abc" } });
    fireEvent.click(screen.getByText("Kiểm tra nội dung"));
    expect(await screen.findByTestId("stream-interrupted")).toHaveTextContent("Chưa có kết luận, hãy thử lại");
    expect(screen.queryByTestId("stage2-provisional")).toBeNull();
    expect(screen.queryByTestId("final-result")).toBeNull();
    expect(screen.queryByText("Chuyển ngay")).toBeNull();
    expect(screen.queryByText(/Chưa thấy dấu hiệu/)).toBeNull();
    expect(document.body.innerHTML).not.toMatch(/green-/);
  });
  it("never shows a green or ALLOW label for a provisional ALLOW stage2, then the amber SOFT card at final", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((r) => {
      release = r;
    });
    mockStream({
      stage2: makeStage2({ red_alert: false, provisional_tier: "ALLOW", provisional_reason_codes: [] }),
      final: makeResponse(),
      gate,
    });
    renderPopup();
    fireEvent.change(screen.getByLabelText(/Dán nội dung/), { target: { value: "abc" } });
    fireEvent.click(screen.getByText("Kiểm tra nội dung"));
    expect(await screen.findByTestId("stage2-neutral")).toHaveTextContent("Đang phân tích tiếp…");
    expect(screen.getByTestId("scan-animation")).toBeInTheDocument();
    expect(screen.queryByText(/Chưa thấy dấu hiệu/)).toBeNull();
    expect(screen.queryByText(/Tạm thời/)).toBeNull();
    expect(document.body.innerHTML).not.toMatch(/green-/);
    await act(async () => release());
    const finalBox = await screen.findByTestId("final-result");
    expect(finalBox.innerHTML).toMatch(/amber-/);
    expect(screen.getByText("Cần kiểm tra thêm trước khi chuyển")).toBeInTheDocument();
    expect(screen.queryByText(/Chưa thấy dấu hiệu/)).toBeNull();
  });

  it("routes a paste into the command box to Flow B as PASTE", async () => {
    mockStream({ final: makeResponse() });
    renderPopup();
    fireEvent.paste(screen.getByLabelText(/gõ lệnh/), {
      clipboardData: { getData: () => "tin nhắn lạ" },
    });
    await waitFor(() => expect(stream).toHaveBeenCalledTimes(1));
    expect(lastRequest().content).toEqual({ origin: "PASTE", text: "tin nhắn lạ" });
  });

  it("rejects text over 4000 characters without calling the backend", () => {
    renderPopup();
    fireEvent.change(screen.getByLabelText(/Dán nội dung/), { target: { value: "x".repeat(4001) } });
    fireEvent.click(screen.getByText("Kiểm tra nội dung"));
    expect(stream).not.toHaveBeenCalled();
    expect(screen.getByTestId("popup-notice")).toHaveTextContent(/quá dài/);
  });
});

describe("clipboard auto-scan", () => {
  function stubClipboard(readText: () => Promise<string>) {
    Object.defineProperty(navigator, "clipboard", { value: { readText }, configurable: true });
  }

  it("does not read the clipboard when opt-in is off", async () => {
    const readText = vi.fn().mockResolvedValue("x");
    stubClipboard(readText);
    renderPopup();
    await Promise.resolve();
    expect(readText).not.toHaveBeenCalled();
    expect(stream).not.toHaveBeenCalled();
  });

  it("reads once on open and once per visible event, sending origin CLIPBOARD", async () => {
    localStorage.setItem(CLIPBOARD_OPTIN_KEY, "1");
    const readText = vi.fn().mockResolvedValueOnce("nội dung 1").mockResolvedValueOnce("nội dung 2");
    stubClipboard(readText);
    mockStream({ final: makeResponse() });
    renderPopup();

    await waitFor(() => expect(stream).toHaveBeenCalledTimes(1));
    expect(lastRequest().content).toEqual({ origin: "CLIPBOARD", text: "nội dung 1" });
    expect(readText).toHaveBeenCalledTimes(1);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await waitFor(() => expect(stream).toHaveBeenCalledTimes(2));
    expect(lastRequest().content.text).toBe("nội dung 2");
    expect(readText).toHaveBeenCalledTimes(2);
  });

  it("shows a notice and focuses the paste box when the browser denies the read", async () => {
    localStorage.setItem(CLIPBOARD_OPTIN_KEY, "1");
    stubClipboard(() => Promise.reject(new DOMException("denied", "NotAllowedError")));
    renderPopup();
    expect(await screen.findByTestId("popup-notice")).toHaveTextContent(/clipboard/);
    expect(screen.getByLabelText(/Dán nội dung/)).toHaveFocus();
    expect(stream).not.toHaveBeenCalled();
  });

  it("persists the opt-in toggle", () => {
    renderPopup();
    fireEvent.click(screen.getByLabelText(/Kiểm tra clipboard/));
    expect(localStorage.getItem(CLIPBOARD_OPTIN_KEY)).toBe("1");
    fireEvent.click(screen.getByLabelText(/Kiểm tra clipboard/));
    expect(localStorage.getItem(CLIPBOARD_OPTIN_KEY)).toBeNull();
  });
});

describe("image and QR input", () => {
  const file = new File(["x"], "a.png", { type: "image/png" });

  it("runs OCR on a chosen image and sends origin OCR", async () => {
    vi.mocked(recognizeText).mockResolvedValue("STK 0123 VCB");
    mockStream({ final: makeResponse() });
    renderPopup();
    fireEvent.change(screen.getByTestId("guardian-file-input"), { target: { files: [file] } });
    await waitFor(() => expect(stream).toHaveBeenCalledTimes(1));
    expect(lastRequest().content).toEqual({ origin: "OCR", text: "STK 0123 VCB" });
  });

  it("sends a chat screenshot as CONTEXT_CHAT with the linked transaction", async () => {
    vi.mocked(recognizeText).mockResolvedValue("anh chuyển gấp giúp em");
    mockStream({ final: makeResponse() });
    const linked = { verdict_id: "v_0", bank_bin: "970436", account_number: "0123", amount_vnd: 500000 };
    renderPopup({ linkedTransaction: linked });
    fireEvent.change(screen.getByTestId("guardian-file-input"), { target: { files: [file] } });
    await waitFor(() => expect(stream).toHaveBeenCalledTimes(1));
    expect(lastRequest().content.origin).toBe("CONTEXT_CHAT");
    expect(lastRequest().linked_transaction).toEqual(linked);
  });

  it("falls back to picking an image when the camera is denied, then sends QR_IMAGE", async () => {
    vi.mocked(openQrCamera).mockResolvedValue({ status: "denied", hintVi: "Chưa mở được camera." });
    vi.mocked(decodeQrFromImage).mockResolvedValue("000201...");
    mockStream({ final: makeResponse() });
    const click = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => undefined);
    renderPopup();

    fireEvent.click(screen.getByText("Quét QR"));
    expect(await screen.findByTestId("popup-notice")).toHaveTextContent("Chưa mở được camera.");
    expect(click).toHaveBeenCalled();

    fireEvent.change(screen.getByTestId("guardian-file-input"), { target: { files: [file] } });
    await waitFor(() => expect(stream).toHaveBeenCalledTimes(1));
    expect(lastRequest().content).toEqual({ origin: "QR_IMAGE", qr_payload: "000201..." });
  });
});

describe("NameConfirm in the popup", () => {
  const ocrFinal = (): CheckResponse =>
    makeResponse({
      name_confirmation: NAME_CONF,
      prefill: {
        bank_bin: "970436",
        account_number: "0123",
        amount_vnd: null,
        memo: null,
        source_integrity_for_flow_a: "OCR_UNCONFIRMED",
      },
    });

  async function submitOcr() {
    vi.mocked(recognizeText).mockResolvedValue("0123");
    mockStream({ final: ocrFinal() });
    renderPopup();
    fireEvent.change(screen.getByTestId("guardian-file-input"), {
      target: { files: [new File(["x"], "a.png", { type: "image/png" })] },
    });
    await screen.findByText("Đúng người nhận");
  }

  it("shows the sandbox name and spaced digits, and confirms via /name/confirm", async () => {
    await submitOcr();
    expect(screen.getByTestId("name-confirm-name")).toHaveTextContent("NGUYEN VAN MINH");
    expect(screen.getByTestId("name-confirm-digits")).toHaveTextContent("0 1 2 3");

    vi.mocked(api.nameConfirm).mockResolvedValue({
      confirmation_token: "ct_1",
      source_integrity: "OCR_CONFIRMED_BY_USER",
      check: makeResponse({ verdict_id: "v_2", verdict: { ...makeResponse().verdict, evidence_bullets: ["Đã đánh giá lại"] } }),
    });
    fireEvent.click(screen.getByText("Đúng người nhận"));
    expect(await screen.findByText("Đã đánh giá lại")).toBeInTheDocument();
    expect(api.nameConfirm).toHaveBeenCalledWith({ pending_id: "pc_1", confirmed: true });
    expect(screen.queryByText("Đúng người nhận")).toBeNull();
  });

  it("lets the user correct the number and re-runs /name/inquiry with the same pending_id", async () => {
    await submitOcr();
    vi.mocked(api.nameConfirm).mockResolvedValue({ source_integrity: "OCR_UNCONFIRMED", check: null });
    vi.mocked(api.nameInquiry).mockResolvedValue({
      ...NAME_CONF,
      display_name: "TRAN THI LAN",
      account_digits_spaced: "9 9 9",
    });

    fireEvent.click(screen.getByText("Sai, sửa số"));
    expect(api.nameConfirm).toHaveBeenCalledWith({ pending_id: "pc_1", confirmed: false });
    fireEvent.change(screen.getByLabelText("Số tài khoản đúng"), { target: { value: "99-9" } });
    fireEvent.click(screen.getByText("Tra lại"));

    expect(await screen.findByText("TRAN THI LAN")).toBeInTheDocument();
    expect(api.nameInquiry).toHaveBeenCalledWith({
      pending_id: "pc_1",
      bank_bin: "970436",
      account_number: "999",
    });
    expect(screen.getByTestId("name-confirm-digits")).toHaveTextContent("9 9 9");
  });
});
