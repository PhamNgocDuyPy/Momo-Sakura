import { useCallback, useEffect, useRef, useState, type ClipboardEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useGuardian } from "../../state/guardianStore";
import { api, ApiError } from "../../services/api";
import { streamFlowBCheck } from "../../services/ndjson";
import { recognizeText } from "../../services/ocr";
import {
  decodeQrFromImage,
  openQrCamera,
  scanVideoForQr,
  stopCamera,
} from "../../services/qrDecode";
import {
  isClipboardOptedIn,
  readClipboardOnce,
  readClipboardOnDemand,
  CLIPBOARD_DENIED_MESSAGE_VI,
  CLIPBOARD_EMPTY_MESSAGE_VI,
  setClipboardOptIn,
  type ClipboardEventKind,
} from "../../services/clipboard";
import type {
  CheckResponse,
  ContentOrigin,
  FlowBContent,
  FlowBStage2Event,
  NameConfirmation,
  AssistantResult,
  ContentMode,
  Prefill,
  ResolvedContact,
} from "../../types/api";
import ScanAnimation, { SCANNING_STATUSES } from "./ScanAnimation";
import ConsentToggle, { ClipboardToggle } from "./ConsentToggle";
import ResultCard from "./ResultCard";
import DecisionTrace from "./DecisionTrace";
import NameConfirm from "./NameConfirm";
import CalmShield from "./CalmShield";
import TransferNowButton, { type TransferNavState } from "./TransferNowButton";
import ContactPicker from "./ContactPicker";
import SpendAnswer from "./SpendAnswer";
import BillSplit from "../split/BillSplit";
import BankHandoff from "../transfer/BankHandoff";

export const MAX_CONTENT_CHARS = 4000;

const MSG = {
  tooLong: "Nội dung quá dài (tối đa 4.000 ký tự). Bạn hãy dán phần quan trọng nhất.",
  ocrEmpty: "Guardian chưa đọc được chữ trong ảnh. Bạn thử chụp rõ hơn hoặc dán nội dung vào ô bên dưới.",
  ocrFailed: "Không đọc được ảnh lúc này. Bạn hãy dán nội dung vào ô bên dưới.",
  qrNotFound: "Chưa thấy mã QR nào. Bạn thử lại hoặc chọn ảnh chứa mã QR.",
  interrupted: "Chưa có kết luận, hãy thử lại. Kết nối bị gián đoạn nên Guardian chưa phân tích xong.",
  analyzing: "Đang phân tích tiếp…",
  requestFailed: "Guardian chưa kiểm tra được lúc này. Bạn thử lại sau nhé.",
  redAlert: "Cảnh báo đỏ: Guardian thấy dấu hiệu nghiêm trọng ở mã QR hoặc tài khoản nhận. Đừng chuyển tiền.",
} as const;

export const COMMAND_EXAMPLES_VI = [
  "chuyển cho Lan 2 lít",
  "tiền điện tháng này tăng bao nhiêu",
  "chia hóa đơn lẩu cho 3 người",
] as const;

const MODE_HINT_VI: Record<ContentMode, string | null> = {
  GENERAL: null,
  SHOP: "Chế độ kiểm tra mua hàng: dán tin rao bán hoặc chụp ảnh sản phẩm.",
  PROMO: "Chế độ kiểm tra khuyến mãi: dán nội dung khuyến mãi hoặc chụp ảnh.",
  SPLIT_BILL: "Chế độ chia hóa đơn: chụp ảnh hóa đơn hoặc dán nội dung hóa đơn.",
};

function contactPrefill(c: ResolvedContact, from: Prefill | null): Prefill {
  return {
    bank_bin: c.bank_bin,
    account_number: c.account_number,
    amount_vnd: from?.amount_vnd ?? null,
    memo: from?.memo ?? null,
    account_origin: "CONTACT",
    source_integrity_for_flow_a: "USER_TYPED",
  };
}

function errorText(e: unknown): string {
  if (e instanceof ApiError && e.messageVi) return e.messageVi;
  return MSG.requestFailed;
}

interface ScanPopupProps {
  /** Opens TransferPage with the prefill (F1). The host owns navigation; absent means no button. */
  onTransferNow?: (state: TransferNavState) => void;
}

export default function ScanPopup({ onTransferNow }: ScanPopupProps = {}) {
  const { state, dispatch } = useGuardian();
  const { open, status, mode, linkedTransaction, autoSubmit } = state.popup;
  const [pasted, setPasted] = useState("");
  const [command, setCommand] = useState("");
  const [commandBusy, setCommandBusy] = useState(false);
  const [commandResult, setCommandResult] = useState<AssistantResult | null>(null);
  const [consent, setConsent] = useState(false);
  const [clipboardCheck, setClipboardCheck] = useState<boolean>(() => isClipboardOptedIn());
  const [notice, setNotice] = useState<string | null>(null);
  const [stage2, setStage2] = useState<FlowBStage2Event | null>(null);
  const [finalResp, setFinalResp] = useState<CheckResponse | null>(null);
  const [interrupted, setInterrupted] = useState(false);
  const [nameConf, setNameConf] = useState<NameConfirmation | null>(null);
  const [nameBusy, setNameBusy] = useState(false);
  const [camera, setCamera] = useState<MediaStream | null>(null);
  const [confirmToken, setConfirmToken] = useState<string | null>(null);
  const [calmDismissed, setCalmDismissed] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);
  const pasteRef = useRef<HTMLTextAreaElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const qrFileModeRef = useRef(false);
  const busyRef = useRef(false);

  const scanning = SCANNING_STATUSES.includes(status);
  busyRef.current = scanning;

  const resetResults = useCallback(() => {
    setNotice(null);
    setStage2(null);
    setFinalResp(null);
    setInterrupted(false);
    setNameConf(null);
    setConfirmToken(null);
    setCalmDismissed(false);
    setCommandResult(null);
  }, []);

  const submit = useCallback(
    async (content: FlowBContent): Promise<void> => {
      if ((content.text?.length ?? 0) > MAX_CONTENT_CHARS) {
        setNotice(MSG.tooLong);
        return;
      }
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      resetResults();
      // Stage 1 is local: the animation shows immediately, before any network round trip.
      dispatch({ type: "SET_STATUS", status: "stage1" });
      try {
        const result = await streamFlowBCheck(
          {
            content,
            mode,
            linked_transaction: linkedTransaction,
            explicit_consent_flag: consent,
            client_time: new Date().toISOString(),
          },
          {
            signal: controller.signal,
            onStage2: (event) => {
              if (controller.signal.aborted) return;
              setStage2(event);
              dispatch({ type: "SET_STATUS", status: "stage2" });
            },
            onFinal: (event) => {
              if (controller.signal.aborted) return;
              setFinalResp(event.response);
              setNameConf(event.response.name_confirmation);
              dispatch({ type: "VERDICT_RECEIVED", response: event.response });
            },
          },
        );
        if (controller.signal.aborted) return;
        if (result.interrupted) setInterrupted(true);
        dispatch({ type: "SET_STATUS", status: "done" });
      } catch (e) {
        if (controller.signal.aborted) return;
        setNotice(errorText(e));
        dispatch({ type: "SET_STATUS", status: "error" });
      }
    },
    [consent, dispatch, linkedTransaction, mode, resetResults],
  );
  const submitRef = useRef(submit);
  submitRef.current = submit;

  const close = (): void => dispatch({ type: "CLOSE_POPUP" });

  // Closing the popup cancels in-flight work and clears local results.
  useEffect(() => {
    if (open) return;
    abortRef.current?.abort();
    resetResults();
    setCamera(null);
  }, [open, resetResults]);

  // Content queued by the share target is submitted exactly once.
  useEffect(() => {
    if (!open || !autoSubmit) return;
    dispatch({ type: "CLEAR_QUEUED_SUBMIT" });
    void submitRef.current(autoSubmit);
  }, [open, autoSubmit, dispatch]);

  // Clipboard auto-scan: one read when the popup opens, one per tab-visible event. No polling.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const run = async (kind: ClipboardEventKind): Promise<void> => {
      if (busyRef.current) return;
      const res = await readClipboardOnce(kind);
      if (cancelled) return;
      if (res.status === "text") {
        setPasted(res.text);
        void submitRef.current({ origin: "CLIPBOARD", text: res.text });
      } else if (res.status === "denied") {
        setNotice(res.messageVi);
        pasteRef.current?.focus();
      }
    };
    void run("popup_open");
    const onVisible = (): void => {
      if (document.visibilityState === "visible") void run("tab_visible");
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [open]);

  // Live camera QR scan.
  useEffect(() => {
    if (!camera) return;
    const video = videoRef.current;
    const controller = new AbortController();
    if (video) {
      video.srcObject = camera;
      void video.play?.().catch(() => undefined);
    }
    void (async () => {
      const payload = video ? await scanVideoForQr(video, controller.signal) : null;
      if (controller.signal.aborted) return;
      stopCamera(camera);
      setCamera(null);
      if (payload) void submitRef.current({ origin: "QR_CAMERA", qr_payload: payload });
      else setNotice(MSG.qrNotFound);
    })();
    return () => {
      controller.abort();
      stopCamera(camera);
    };
  }, [camera]);

  // One tap: the clipboard read starts synchronously inside the click (user gesture).
  const pasteAndCheck = async (): Promise<void> => {
    if (busyRef.current) return;
    setNotice(null);
    const res = await readClipboardOnDemand();
    if (res.status === "text") {
      setPasted(res.text);
      await submit({ origin: "CLIPBOARD", text: res.text });
    } else if (res.status === "empty") {
      setNotice(CLIPBOARD_EMPTY_MESSAGE_VI);
    } else {
      setNotice(res.status === "denied" ? res.messageVi : CLIPBOARD_DENIED_MESSAGE_VI);
      pasteRef.current?.focus();
    }
  };

  const onClipboardToggle = (enabled: boolean): void => {
    setClipboardCheck(enabled);
    setClipboardOptIn(enabled);
  };

  const startQr = async (): Promise<void> => {
    setNotice(null);
    const res = await openQrCamera();
    if (res.status === "ok") {
      setCamera(res.stream);
      return;
    }
    setNotice(res.hintVi);
    qrFileModeRef.current = true;
    fileRef.current?.click();
  };

  const onFile = async (file: File | undefined): Promise<void> => {
    if (!file) return;
    const qrMode = qrFileModeRef.current;
    qrFileModeRef.current = false;
    setNotice(null);
    if (qrMode) {
      try {
        const payload = await decodeQrFromImage(file);
        if (payload) await submit({ origin: "QR_IMAGE", qr_payload: payload });
        else setNotice(MSG.qrNotFound);
      } catch {
        setNotice(MSG.qrNotFound);
      }
      return;
    }
    // Images shared from a "check with Guardian" flow are chat screenshots.
    const origin: ContentOrigin = linkedTransaction ? "CONTEXT_CHAT" : "OCR";
    resetResults();
    dispatch({ type: "SET_STATUS", status: "ocr" });
    let text: string;
    try {
      text = (await recognizeText(file)).trim();
    } catch {
      setNotice(MSG.ocrFailed);
      dispatch({ type: "SET_STATUS", status: "error" });
      return;
    }
    if (!text) {
      setNotice(MSG.ocrEmpty);
      dispatch({ type: "SET_STATUS", status: "error" });
      return;
    }
    await submit({ origin, text });
  };

  // A paste into the command box is untrusted content: route to Flow B, never to the Planner.
  const onCommandPaste = (e: ClipboardEvent<HTMLInputElement>): void => {
    const text = e.clipboardData.getData("text");
    if (!text.trim()) return;
    e.preventDefault();
    setPasted(text);
    void submit({ origin: "PASTE", text });
  };

  // Trusted_Command typed by the user goes to the assistant (Planner), never to Flow B.
  const runCommand = async (): Promise<void> => {
    const text = command.trim();
    if (text === "" || commandBusy) return;
    setCommandBusy(true);
    setNotice(null);
    setCommandResult(null);
    try {
      const res = await api.assistantCommand(text.slice(0, 200));
      const r = res.result;
      if (r.type === "TRANSFER_RESOLUTION" && r.status === "RESOLVED" && r.prefill && onTransferNow) {
        onTransferNow({ prefill: r.prefill });
        return;
      }
      if (r.type === "OPEN_MODE") {
        dispatch({ type: "SET_MODE", mode: r.mode });
        setCommand("");
      }
      setCommandResult(r);
    } catch (e) {
      setNotice(errorText(e));
    } finally {
      setCommandBusy(false);
    }
  };
  const pickContact = (c: ResolvedContact): void => {
    const from = commandResult?.type === "TRANSFER_RESOLUTION" ? commandResult.prefill : null;
    onTransferNow?.({ prefill: contactPrefill(c, from) });
  };
  const renderCommandResult = (r: AssistantResult) => {
    if (r.type === "SPEND_ANSWER") return <SpendAnswer answer={r} />;
    if (r.type === "TRANSFER_RESOLUTION" && r.status === "AMBIGUOUS") {
      return <ContactPicker candidates={r.candidates} message={r.message_vi} onPick={pickContact} />;
    }
    if (r.type === "OPEN_MODE") {
      return r.message_vi ? (
        <p data-testid="command-message" className="rounded-lg bg-pink-50 p-2 text-sm text-pink-900">
          {r.message_vi}
        </p>
      ) : null;
    }
    // NOT_FOUND, NEEDS_AMOUNT, REPHRASE (and RESOLVED when the host cannot open TransferPage).
    const examples = r.type === "REPHRASE" && r.examples_vi.length > 0 ? r.examples_vi : [...COMMAND_EXAMPLES_VI];
    return (
      <div data-testid="command-message" className="space-y-1 rounded-lg bg-amber-50 p-2 text-sm text-amber-900">
        <p>{r.message_vi}</p>
        <p className="text-xs font-medium">Bạn có thể thử:</p>
        <ul className="list-disc pl-5 text-xs">
          {examples.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </div>
    );
  };
  const confirmName = async (): Promise<void> => {
    if (!nameConf) return;
    setNameBusy(true);
    try {
      const res = await api.nameConfirm({ pending_id: nameConf.pending_id, confirmed: true });
      if (res.confirmation_token) setConfirmToken(res.confirmation_token);
      if (res.check) {
        setFinalResp(res.check);
        setNameConf(null);
        dispatch({ type: "VERDICT_RECEIVED", response: res.check });
      }
    } catch (e) {
      setNotice(errorText(e));
    } finally {
      setNameBusy(false);
    }
  };

  const rejectName = (): void => {
    if (!nameConf) return;
    void api.nameConfirm({ pending_id: nameConf.pending_id, confirmed: false }).catch(() => undefined);
  };

  const correctName = async (accountNumber: string): Promise<void> => {
    if (!nameConf) return;
    setNameBusy(true);
    try {
      const next = await api.nameInquiry({
        pending_id: nameConf.pending_id,
        bank_bin: finalResp?.prefill?.bank_bin ?? "",
        account_number: accountNumber,
      });
      setNameConf(next);
    } catch (e) {
      setNotice(errorText(e));
    } finally {
      setNameBusy(false);
    }
  };

  // Stage 2 never shows a tier label: only the red alert or a neutral "analyzing" note (Req 16.6, 17.2).
  const provisional = stage2 && !finalResp && (stage2.red_alert || scanning) && (
    <div data-testid="stage2-provisional" className="space-y-2">
      {stage2.red_alert && (
        <div
          role="alert"
          data-testid="red-alert"
          className="rounded-lg border border-red-400 bg-red-100 p-3 text-sm font-semibold text-red-800"
        >
          {MSG.redAlert}
        </div>
      )}
      {!stage2.red_alert && (
        <p data-testid="stage2-neutral" className="rounded-lg bg-slate-100 p-2 text-sm text-slate-700">
          {MSG.analyzing}
        </p>
      )}
    </div>
  );

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="guardian-popup-root"
          className="fixed inset-0 z-50 flex items-end justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-slate-900/50" onClick={close} aria-hidden="true" />
          <motion.section
            role="dialog"
            aria-modal="true"
            aria-label="Guardian"
            data-testid="scan-popup"
            className="relative max-h-[90vh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-white p-4 shadow-2xl"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">Guardian kiểm tra giúp bạn</h2>
              <button
                type="button"
                aria-label="Đóng"
                className="rounded-full px-2 py-1 text-slate-500 hover:bg-slate-100"
                onClick={close}
              >
                ✕
              </button>
            </div>

            {notice && (
              <p data-testid="popup-notice" role="status" className="mb-3 rounded-lg bg-amber-50 p-2 text-sm text-amber-900">
                {notice}
              </p>
            )}

            {MODE_HINT_VI[mode] && (
              <p data-testid="mode-hint" className="mb-3 rounded-lg bg-pink-50 p-2 text-sm text-pink-900">
                {MODE_HINT_VI[mode]}
              </p>
            )}
            {scanning ? (
              <div className="space-y-3">
                <ScanAnimation status={status} />
                {provisional}
              </div>
            ) : (
              <div className="space-y-3">
                {provisional}
                {interrupted && (
                  <p data-testid="stream-interrupted" className="rounded-lg bg-slate-100 p-2 text-sm text-slate-700">
                    {MSG.interrupted}
                  </p>
                )}
                {finalResp && (
                  <div className="space-y-3" data-testid="final-result">
                    <CalmShield
                      hints={finalResp.ui_hints}
                      bullets={finalResp.verdict.evidence_bullets}
                      onContinue={() => setCalmDismissed(true)}
                      dismissed={calmDismissed}
                    >
                      <ResultCard response={finalResp}>
                        {onTransferNow && !interrupted && !nameConf && (
                          <TransferNowButton
                            response={finalResp}
                            confirmationToken={confirmToken}
                            onTransfer={onTransferNow}
                          />
                        )}
                        {finalResp.prefill?.bank_bin && finalResp.prefill.account_number && (
                          <BankHandoff
                            verdictId={finalResp.verdict_id}
                            tier={finalResp.verdict.decision_tier}
                            handoffAllowed={finalResp.ui_hints.handoff_allowed}
                            bankBin={finalResp.prefill.bank_bin}
                            accountNumber={finalResp.prefill.account_number}
                            amountVnd={finalResp.prefill.amount_vnd}
                            memo={finalResp.prefill.memo}
                          />
                        )}
                      </ResultCard>
                    </CalmShield>
                    {nameConf && (
                      <NameConfirm
                        confirmation={nameConf}
                        busy={nameBusy}
                        onConfirm={() => void confirmName()}
                        onReject={rejectName}
                        onCorrect={(n) => void correctName(n)}
                      />
                    )}
                    {mode === "SPLIT_BILL" && finalResp.extensions?.receipt && (
                      <BillSplit
                        key={finalResp.request_id}
                        items={finalResp.extensions.receipt.items}
                        totalVnd={finalResp.extensions.receipt.total_vnd}
                      />
                    )}
                    <DecisionTrace response={finalResp} />
                  </div>
                )}

                {camera && (
                  <div className="space-y-2">
                    <video ref={videoRef} data-testid="qr-video" muted playsInline className="w-full rounded-lg bg-black" />
                    <button
                      type="button"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                      onClick={() => setCamera(null)}
                    >
                      Dừng quét
                    </button>
                  </div>
                )}

                <button
                  type="button"
                  data-testid="paste-and-check"
                  className="w-full rounded-xl bg-gradient-to-r from-pink-600 to-fuchsia-600 px-4 py-4 text-base font-semibold text-white shadow-md"
                  onClick={() => void pasteAndCheck()}
                >
                  Dán &amp; kiểm tra
                </button>
                <p className="text-center text-xs text-slate-500">
                  Sao chép tin nhắn rồi bấm nút trên, không cần nhấn giữ để dán.
                </p>

                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-slate-700">Dán nội dung cần kiểm tra</span>                  <textarea
                    ref={pasteRef}
                    className="h-24 w-full rounded-lg border border-slate-300 p-2 text-sm"
                    placeholder="Dán tin nhắn, đường dẫn hoặc thông tin chuyển khoản…"
                    value={pasted}
                    onChange={(e) => setPasted(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  disabled={pasted.trim().length === 0}
                  className="w-full rounded-lg border border-pink-300 px-3 py-2 text-sm font-medium text-pink-700 disabled:border-slate-200 disabled:text-slate-400"
                  onClick={() => void submit({ origin: "PASTE", text: pasted })}
                >
                  Kiểm tra nội dung
                </button>
                <form
                  data-testid="command-form"
                  className="space-y-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void runCommand();
                  }}
                >
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium text-slate-700">Hoặc gõ lệnh</span>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        maxLength={200}
                        aria-label="Lệnh cho Guardian"
                        className="min-w-0 flex-1 rounded-lg border border-slate-300 p-2 text-sm"
                        placeholder="Ví dụ: chuyển cho Lan 2 lít"
                        value={command}
                        onChange={(e) => setCommand(e.target.value)}
                        onPaste={onCommandPaste}
                      />
                      <button
                        type="submit"
                        data-testid="command-send"
                        disabled={command.trim() === "" || commandBusy}
                        className="shrink-0 rounded-lg bg-pink-600 px-3 text-sm font-medium text-white disabled:bg-slate-300"
                      >
                        {commandBusy ? "Đang gửi…" : "Gửi"}
                      </button>
                    </div>
                  </label>
                  {commandResult && renderCommandResult(commandResult)}
                </form>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="flex-1 rounded-lg border border-pink-300 px-3 py-2 text-sm font-medium text-pink-700"
                    onClick={() => {
                      qrFileModeRef.current = false;
                      fileRef.current?.click();
                    }}
                  >
                    Chọn / chụp ảnh
                  </button>
                  <button
                    type="button"
                    className="flex-1 rounded-lg border border-pink-300 px-3 py-2 text-sm font-medium text-pink-700"
                    onClick={() => void startQr()}
                  >
                    Quét QR
                  </button>
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    data-testid="guardian-file-input"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      void onFile(file);
                    }}
                  />
                </div>
                <div className="divide-y divide-slate-100 rounded-lg bg-slate-50 px-3">
                  <ConsentToggle checked={consent} onChange={setConsent} />
                  <ClipboardToggle checked={clipboardCheck} onChange={onClipboardToggle} />
                </div>
              </div>
            )}
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
