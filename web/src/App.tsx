import { useCallback, useEffect, useRef } from "react";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { GuardianProvider, useGuardian } from "./state/guardianStore";
import GuardianBubble from "./components/guardian/GuardianBubble";
import ScanPopup from "./components/guardian/ScanPopup";
import type { TransferNavState } from "./components/guardian/TransferNowButton";
import { recognizeText } from "./services/ocr";
import { composeSharedText, isShareLaunch, readShareInbox } from "./services/share";

/** Handles `/?share=1` (Web Share Target): open the popup and send the shared content to Flow B. */
function useShareLaunch(): void {
  const { dispatch } = useGuardian();
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current || !isShareLaunch(window.location.search)) return;
    handled.current = true;
    window.history.replaceState(null, "", window.location.pathname);
    void (async () => {
      dispatch({ type: "OPEN_POPUP" });
      const item = await readShareInbox();
      if (!item) return;
      let text = composeSharedText(item);
      if (item.image) {
        dispatch({ type: "SET_STATUS", status: "ocr" });
        try {
          const ocr = (await recognizeText(item.image)).trim();
          text = [text, ocr].filter((s) => s !== "").join("\n");
        } catch {
          // OCR is best effort; shared text, if any, still goes through, otherwise the user pastes.
        }
        dispatch({ type: "SET_STATUS", status: "idle" });
      }
      if (text !== "") dispatch({ type: "QUEUE_SUBMIT", content: { origin: "SHARE_TARGET", text } });
    })();
  }, [dispatch]);
}

function GuardianHost() {
  const { dispatch } = useGuardian();
  useShareLaunch();
  const onTransferNow = useCallback(
    (state: TransferNavState): void => {
      dispatch({ type: "CLOSE_POPUP" });
      void router.navigate("/transfer", { state });
    },
    [dispatch],
  );
  return (
    <>
      <GuardianBubble />
      <ScanPopup onTransferNow={onTransferNow} />
    </>
  );
}

export default function App() {
  return (
    <GuardianProvider>
      <RouterProvider router={router} />
      <GuardianHost />
    </GuardianProvider>
  );
}
