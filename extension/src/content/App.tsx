import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { DEFAULT_WEB_URL, getWebUrl } from "../shared/settings";
import { isAutoProtectEnabled, onAutoProtectChange, setAutoProtect } from "../shared/autoProtect";
import type { CheckRequestMessage, ExtensionOrigin, TriggerMessage } from "../shared/types";
import Bubble from "./Bubble";
import { startAutoProtect } from "./autoProtect";
import { startCheck } from "./client";
import { keepTail } from "./capture";
import { captureChat } from "./conversation";
import type { ReadInfo } from "./ReadSummary";
import Overlay from "./Overlay";
import { checkReducer, type CheckState } from "./state";

export const MSG_NOTHING_TO_CHECK =
  "Không thấy đoạn văn bản nào để kiểm tra. Hãy bôi đen tin nhắn đáng ngờ rồi thử lại.";

type Request = Omit<CheckRequestMessage, "type">;

export default function App() {
  const [state, dispatch] = useReducer(checkReducer, { phase: "idle" } as CheckState);
  const [webUrl, setWebUrl] = useState(DEFAULT_WEB_URL);
  const cancel = useRef<(() => void) | null>(null);
  const last = useRef<{ request: Request; read: ReadInfo | null } | null>(null);
  const [read, setRead] = useState<ReadInfo | null>(null);

  const close = useCallback(() => {
    cancel.current?.();
    cancel.current = null;
    dispatch({ type: "close" });
  }, []);

  const run = useCallback((request: Request | null, readInfo: ReadInfo | null) => {
    cancel.current?.();
    cancel.current = null;
    if (!request) {
      setRead(null);
      dispatch({ type: "start", charCount: 0 });
      dispatch({ type: "error", message: MSG_NOTHING_TO_CHECK });
      return;
    }
    last.current = { request, read: readInfo };
    setRead(readInfo);
    dispatch({ type: "start", charCount: request.text.length });
    void getWebUrl().then(setWebUrl);
    cancel.current = startCheck(request, {
      onMessage: (m) => {
        if (m.type === "stage2") dispatch({ type: "stage2", event: m.event });
        else if (m.type === "final") dispatch({ type: "final", response: m.response });
        else dispatch({ type: "error", message: m.message_vi });
      },
    });
  }, []);

  /** Runs only on a user action (bubble tap, context menu, shortcut): reads selection or viewport then. */
  const trigger = useCallback(
    (selectionText?: string) => {
      const sel = selectionText?.trim();
      if (sel) {
        const origin: ExtensionOrigin = "EXTENSION_SELECTION";
        const text = keepTail(sel);
        run({ text, origin }, { source: "selection", messages: [text] });
        return;
      }
      const c = captureChat();
      run(c && { text: c.text, origin: c.origin }, c && { source: c.source, messages: c.messages });
    },
    [run],
  );

  useEffect(() => {
    const onMessage = (message: unknown): void => {
      const m = message as Partial<TriggerMessage> | null;
      if (m?.type === "guardian-trigger") trigger(m.selectionText);
    };
    chrome.runtime.onMessage.addListener(onMessage);
    return () => chrome.runtime.onMessage.removeListener(onMessage);
  }, [trigger]);

  useEffect(() => () => cancel.current?.(), []);
  // "Tự động bảo vệ": off by default, stored per hostname.
  const host = window.location.hostname;
  const [autoProtect, setAutoProtectState] = useState(false);
  useEffect(() => {
    let alive = true;
    void isAutoProtectEnabled(host).then((on) => alive && setAutoProtectState(on));
    const off = onAutoProtectChange((map) => setAutoProtectState(map[host] === true));
    return () => {
      alive = false;
      off();
    };
  }, [host]);
  const toggleAutoProtect = useCallback(() => {
    const next = !autoProtect;
    setAutoProtectState(next);
    void setAutoProtect(host, next).catch(() => setAutoProtectState(!next));
  }, [autoProtect, host]);
  useEffect(() => {
    if (!autoProtect) return;
    const ap = startAutoProtect({
      onCheck: (text) => {
        const t = keepTail(text);
        run({ text: t, origin: "EXTENSION_SELECTION" }, { source: "selection", messages: [t] });
      },
    });
    return ap.stop;
  }, [autoProtect, run]);

  const retry = last.current ? () => run(last.current!.request, last.current!.read) : undefined;

  return (
    <>
      {state.phase === "idle" && <Bubble onTap={() => trigger()} autoProtect={autoProtect} onToggleAutoProtect={toggleAutoProtect} />}
      <Overlay state={state} webUrl={webUrl} onClose={close} onRetry={retry} read={read} />
    </>
  );
}