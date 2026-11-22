import { createRoot, type Root } from "react-dom/client";
import App from "./App";
import { HOST_TAG } from "./capture";

/** Creates `<momo-guardian-root>` with a Shadow DOM, inlines the compiled CSS, renders the app. */
export function mountGuardian(css: string, doc: Document = document): { host: HTMLElement; root: Root } | null {
  if (doc.querySelector(HOST_TAG)) return null; // already injected (auto + manual injection)
  const host = doc.createElement(HOST_TAG);
  host.style.cssText =
    "all: initial; position: fixed; top: 0; left: 0; width: 0; height: 0; z-index: 2147483647;";
  const shadow = host.attachShadow({ mode: "open" });
  const style = doc.createElement("style");
  style.textContent = css;
  const mountPoint = doc.createElement("div");
  shadow.append(style, mountPoint);
  doc.documentElement.append(host);
  const root = createRoot(mountPoint);
  root.render(<App />);
  return { host, root };
}