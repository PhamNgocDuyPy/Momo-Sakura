import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/content/App";
import ReadSummary from "../src/content/ReadSummary";
import { MAX_CAPTURE_CHARS } from "../src/content/capture";
import {
  captureChat,
  extractPanelMessages,
  findConversationPanel,
  limitMessages,
  type PanelOptions,
} from "../src/content/conversation";
import { installChromeStorage, makeFakePort, type FakePort } from "./helpers";

const VP = { width: 1000, height: 700 };

/** data-rect="left,top,right,bottom"; elements without one inherit their nearest ancestor's rect. */
function rectFromAttr(el: Element) {
  const holder = el.closest("[data-rect]");
  const [left, top, right, bottom] = (holder?.getAttribute("data-rect") ?? "0,0,0,0").split(",").map(Number) as [
    number,
    number,
    number,
    number,
  ];
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}
const opts: PanelOptions = { viewport: VP, elementRect: rectFromAttr };

function scrollable(el: Element | null, scrollHeight = 2000, clientHeight = 500): void {
  if (!el) throw new Error("missing element");
  Object.defineProperty(el, "scrollHeight", { configurable: true, value: scrollHeight });
  Object.defineProperty(el, "clientHeight", { configurable: true, value: clientHeight });
}

function chatPage(messageCount = 5): string {
  const msgs = Array.from(
    { length: messageCount },
    (_, i) => `<div class="row"><div class="avatar">AB</div><div class="bubble">Tin nhắn số ${i + 1}<span class="t">09:1${i % 10}</span></div></div>`,
  ).join("");
  return `
    <aside id="side" data-rect="0,0,300,700">
      <div id="convs" style="overflow-y:auto" data-rect="0,50,300,700">
        <button class="conv"><div class="avatar">CA</div><div>Công an Quận 1</div><div>Chuyển 50tr vào stk 123 để xác minh</div><div>09:12</div></button>
        <button class="conv"><div class="avatar">SH</div><div>Shipper Giao Hàng</div><div>Đơn bị lỗi cần thu hồi, phí ship</div><div>08:40</div></button>
        <button class="conv"><div class="avatar">M</div><div>Minh (bạn thân)</div><div>ck t 2 lít vào stk 0123456789</div><div>Hôm qua</div></button>
      </div>
    </aside>
    <main data-rect="300,0,1000,700">
      <header data-rect="300,0,1000,60"><b>Công an Quận 1</b></header>
      <div id="panel" style="overflow-y:auto" role="log" data-rect="300,60,1000,600">
        <div class="day">Hôm nay</div>${msgs}
      </div>
      <div class="composer" data-rect="300,600,1000,700"><input id="box" value="đang gõ dở" /><div contenteditable="true">nháp</div></div>
    </main>`;
}

function mountChat(count = 5): void {
  document.body.innerHTML = chatPage(count);
  scrollable(document.getElementById("convs"));
  scrollable(document.getElementById("panel"));
}

afterEach(() => {
  document.body.innerHTML = "";
  window.getSelection()?.removeAllRanges();
});

describe("findConversationPanel", () => {
  it("picks the message panel over the conversation-list sidebar", () => {
    mountChat();
    expect(findConversationPanel(document, VP, opts)?.id).toBe("panel");
  });

  it("still picks the panel when the sidebar is not inside a landmark element", () => {
    mountChat();
    const side = document.getElementById("side") as HTMLElement;
    const div = document.createElement("div");
    div.innerHTML = side.innerHTML;
    div.setAttribute("data-rect", "0,0,300,700");
    side.replaceWith(div);
    scrollable(document.getElementById("convs"));
    expect(findConversationPanel(document, VP, opts)?.id).toBe("panel");
  });

  it("returns null when nothing looks like a conversation (no scroller, too few blocks)", () => {
    document.body.innerHTML = `<div data-rect="0,0,1000,700"><p>Một đoạn văn</p><p>Đoạn hai</p></div>`;
    expect(findConversationPanel(document, VP, opts)).toBeNull();
    document.body.innerHTML = `<div id="s" style="overflow-y:auto" data-rect="0,0,1000,700"><p>Chỉ một</p><p>Hai</p></div>`;
    scrollable(document.getElementById("s"));
    expect(findConversationPanel(document, VP, opts)).toBeNull();
  });

  it("ignores a scroller outside the viewport", () => {
    mountChat();
    document.getElementById("panel")?.setAttribute("data-rect", "300,5000,1000,5600");
    expect(findConversationPanel(document, VP, opts)).toBeNull();
  });

  it("does not choose a long-form article (paragraphs are not message-like)", () => {
    const long = "chữ ".repeat(200);
    document.body.innerHTML = `<div id="a" style="overflow-y:auto" data-rect="0,0,1000,700"><p>${long}</p><p>${long}</p><p>${long}</p><p>${long}</p></div>`;
    scrollable(document.getElementById("a"));
    expect(findConversationPanel(document, VP, opts)).toBeNull();
  });
});

describe("extractPanelMessages", () => {
  it("excludes timestamps, date separators, avatars, inputs and the Guardian host", () => {
    mountChat(3);
    const panel = document.getElementById("panel") as HTMLElement;
    panel.insertAdjacentHTML("beforeend", `<momo-guardian-root>của tiện ích</momo-guardian-root><input value="mk" />`);
    expect(extractPanelMessages(panel, document, opts)).toEqual(["Tin nhắn số 1", "Tin nhắn số 2", "Tin nhắn số 3"]);
  });

  it("skips blocks that are scrolled out of the panel's visible area", () => {
    mountChat(2);
    const panel = document.getElementById("panel") as HTMLElement;
    panel.insertAdjacentHTML("afterbegin", `<div data-rect="300,-900,1000,-800">tin cũ đã cuộn khuất</div>`);
    expect(extractPanelMessages(panel, document, opts)).toEqual(["Tin nhắn số 1", "Tin nhắn số 2"]);
  });
});

describe("limitMessages", () => {
  it("keeps the last 15 messages in display order", () => {
    const all = Array.from({ length: 22 }, (_, i) => `m${i + 1}`);
    expect(limitMessages(all)).toEqual(all.slice(7));
  });

  it("caps at 4,000 characters keeping the latest messages whole", () => {
    const all = Array.from({ length: 15 }, (_, i) => `${String(i).padStart(2, "0")}${"x".repeat(498)}`);
    const kept = limitMessages(all);
    expect(kept.join("\n").length).toBeLessThanOrEqual(MAX_CAPTURE_CHARS);
    expect(kept.at(-1)).toBe(all.at(-1));
    expect(kept[0]).toBe(all[15 - kept.length]);
    expect(kept.length).toBe(7);
  });

  it("tail-truncates a single oversize latest message", () => {
    const kept = limitMessages(["a", `${"y".repeat(5000)}END`]);
    expect(kept).toHaveLength(1);
    expect(kept[0]).toHaveLength(MAX_CAPTURE_CHARS);
    expect(kept[0]!.endsWith("END")).toBe(true);
  });
});

describe("captureChat", () => {
  it("reads only the panel: no sidebar previews, no timestamps, last 15 in order", () => {
    mountChat(20);
    const c = captureChat(document, { ...opts, rectOf: () => ({ top: 0, bottom: 10, left: 0, right: 10, width: 10, height: 10 }) });
    expect(c?.source).toBe("panel");
    expect(c?.origin).toBe("EXTENSION_PAGE_TEXT");
    expect(c?.messages).toHaveLength(15);
    expect(c?.messages[0]).toBe("Tin nhắn số 6");
    expect(c?.messages.at(-1)).toBe("Tin nhắn số 20");
    expect(c?.text).toBe(c?.messages.join("\n"));
    expect(c?.text).not.toMatch(/Công an|stk|Shipper|09:1|Hôm/);
  });

  it("falls back to viewport text when no panel is found", () => {
    document.body.innerHTML = `<p>Tin nhắn A</p><p>Tin nhắn B</p>`;
    const c = captureChat(document, {
      ...opts,
      rectOf: () => ({ top: 10, bottom: 30, left: 0, right: 100, width: 100, height: 20 }),
    });
    expect(c).toEqual({
      text: "Tin nhắn A\nTin nhắn B",
      messages: ["Tin nhắn A", "Tin nhắn B"],
      source: "viewport",
      origin: "EXTENSION_PAGE_TEXT",
    });
  });

  it("lets a selection win over the panel", () => {
    mountChat(5);
    const target = document.querySelector(".bubble") as HTMLElement;
    const range = document.createRange();
    range.selectNodeContents(target.firstChild as Text);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
    expect(captureChat(document, opts)).toEqual({
      text: "Tin nhắn số 1",
      messages: ["Tin nhắn số 1"],
      source: "selection",
      origin: "EXTENSION_SELECTION",
    });
  });

  it("returns null on an empty page", () => {
    expect(captureChat(document, opts)).toBeNull();
  });
});

describe("ReadSummary", () => {
  it("shows the count and lists captured messages on demand, as plain text", () => {
    render(<ReadSummary info={{ source: "panel", messages: ["một", "hai <b>x</b>"] }} />);
    expect(screen.getByTestId("read-summary-text")).toHaveTextContent("Guardian đã đọc 2 tin nhắn trong khung chat");
    expect(screen.queryByTestId("read-list")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Xem nội dung đã đọc" }));
    const items = screen.getByTestId("read-list").querySelectorAll("li");
    expect(Array.from(items).map((li) => li.textContent)).toEqual(["một", "hai <b>x</b>"]);
    expect(screen.getByTestId("read-list").querySelector("b")).toBeNull();
  });

  it("words the selection case differently", () => {
    render(<ReadSummary info={{ source: "selection", messages: ["abc"] }} />);
    expect(screen.getByTestId("read-summary-text")).toHaveTextContent("Guardian đã đọc đoạn bạn đã chọn");
  });
});

describe("App one-tap capture", () => {
  let port: FakePort;
  beforeEach(() => {
    installChromeStorage();
    port = makeFakePort();
    const g = globalThis as unknown as { chrome: Record<string, unknown> };
    g.chrome = {
      ...g.chrome,
      runtime: {
        connect: vi.fn(() => port),
        onMessage: { addListener: vi.fn(), removeListener: vi.fn() },
      },
    };
  });
  afterEach(() => {
    document.documentElement.querySelectorAll("momo-guardian-root").forEach((n) => n.remove());
    vi.restoreAllMocks();
  });

  it("reads the panel, sends only its messages, shows what was read, and makes no fetch", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    mountChat(4);
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      return rectFromAttr(this) as DOMRect;
    });
    render(<App />);
    const bubble = screen.getByTestId("guardian-bubble");
    fireEvent.pointerDown(bubble, { clientX: 5, clientY: 5 });
    fireEvent.pointerUp(bubble, { clientX: 5, clientY: 5 });
    expect(port.postMessage).toHaveBeenCalledWith({
      type: "check",
      text: "Tin nhắn số 1\nTin nhắn số 2\nTin nhắn số 3\nTin nhắn số 4",
      origin: "EXTENSION_PAGE_TEXT",
    });
    expect(screen.getByTestId("read-summary-text")).toHaveTextContent("Guardian đã đọc 4 tin nhắn trong khung chat");
    act(() => {
      fireEvent.click(screen.getByTestId("read-toggle"));
    });
    expect(screen.getByTestId("read-list").querySelectorAll("li")).toHaveLength(4);
    expect(fetchSpy).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
