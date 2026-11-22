import type { BackgroundMessage, CheckRequestMessage } from "../shared/types";
import { CHECK_PORT_NAME } from "../shared/types";

export const MSG_WORKER_UNAVAILABLE =
  "Không liên lạc được với tiện ích. Hãy tải lại trang hoặc tải lại tiện ích rồi thử lại.";

export interface CheckHandlers {
  onMessage: (message: BackgroundMessage) => void;
}

/**
 * Opens a `guardian-check` port to the service worker (which calls the backend) and sends one request.
 * Returns a cancel function that disconnects the port.
 */
export function startCheck(request: Omit<CheckRequestMessage, "type">, handlers: CheckHandlers): () => void {
  let closed = false;
  try {
    const port = chrome.runtime.connect({ name: CHECK_PORT_NAME });
    port.onMessage.addListener((m: BackgroundMessage) => {
      if (closed) return;
      handlers.onMessage(m);
      if (m.type === "final" || m.type === "error") {
        closed = true;
        port.disconnect();
      }
    });
    port.onDisconnect.addListener(() => {
      if (!closed) {
        closed = true;
        handlers.onMessage({ type: "error", message_vi: MSG_WORKER_UNAVAILABLE });
      }
    });
    const message: CheckRequestMessage = { type: "check", ...request };
    port.postMessage(message);
    return () => {
      if (closed) return;
      closed = true;
      port.disconnect();
    };
  } catch {
    // Extension was reloaded or removed: the old content script has no runtime any more.
    queueMicrotask(() => handlers.onMessage({ type: "error", message_vi: MSG_WORKER_UNAVAILABLE }));
    return () => {
      closed = true;
    };
  }
}