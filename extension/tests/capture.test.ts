import { afterEach, describe, expect, it } from "vitest";
import { MAX_CAPTURE_CHARS, capture, captureViewportText, getSelectionText, keepTail } from "../src/content/capture";

const visible = () => ({ top: 10, bottom: 30, left: 0, right: 100, width: 100, height: 20 });

afterEach(() => {
  document.body.innerHTML = "";
  window.getSelection()?.removeAllRanges();
});

describe("captureViewportText", () => {
  it("returns visible text in DOM order and skips input, script, style and hidden elements", () => {
    document.body.innerHTML = `
      <style>.x{color:red}</style>
      <script>var secret = 1;</script>
      <div>Xin chào</div>
      <textarea>nháp riêng tư</textarea>
      <input value="mật khẩu" />
      <div hidden>ẩn bằng attribute</div>
      <div style="display:none"><span>ẩn bằng css</span></div>
      <div aria-hidden="true">ẩn aria</div>
      <div style="visibility:hidden">vô hình</div>
      <p>Tin nhắn thứ hai</p>
      <momo-guardian-root><span>của tiện ích</span></momo-guardian-root>`;
    const text = captureViewportText(document, { rectOf: visible, viewport: { width: 800, height: 600 } });
    expect(text).toBe("Xin chào\nTin nhắn thứ hai");
  });

  it("skips text nodes outside the viewport", () => {
    document.body.innerHTML = `<p id="a">ở trên màn hình</p><p id="b">ngoài màn hình</p>`;
    const rectOf = (node: Text) =>
      node.parentElement?.id === "b"
        ? { top: 2000, bottom: 2020, left: 0, right: 50, width: 50, height: 20 }
        : visible();
    expect(captureViewportText(document, { rectOf, viewport: { width: 800, height: 600 } })).toBe("ở trên màn hình");
  });

  it("keeps the last 4000 characters", () => {
    const parts = Array.from({ length: 100 }, (_, i) => `<p>${String(i).padStart(3, "0")} ${"x".repeat(96)}</p>`);
    document.body.innerHTML = parts.join("");
    const text = captureViewportText(document, { rectOf: visible, viewport: { width: 800, height: 600 } });
    expect(text.length).toBe(MAX_CAPTURE_CHARS);
    expect(text.endsWith("x".repeat(96))).toBe(true);
    expect(text).toContain("099 ");
    expect(text).not.toContain("000 ");
  });

  it("returns an empty string for an empty page", () => {
    expect(captureViewportText(document, { rectOf: visible })).toBe("");
  });
});

describe("keepTail", () => {
  it("keeps the end of long text", () => {
    expect(keepTail("abcdef", 3)).toBe("def");
    expect(keepTail("abc", 3)).toBe("abc");
  });
});

describe("capture", () => {
  it("uses the selection with EXTENSION_SELECTION when text is selected", () => {
    document.body.innerHTML = `<p id="m">Chuyển 50tr vào stk 123</p><p>Nội dung khác</p>`;
    const range = document.createRange();
    range.selectNodeContents(document.getElementById("m") as HTMLElement);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
    expect(getSelectionText()).toBe("Chuyển 50tr vào stk 123");
    expect(capture(document, { rectOf: visible })).toEqual({
      text: "Chuyển 50tr vào stk 123",
      origin: "EXTENSION_SELECTION",
    });
  });

  it("falls back to viewport text with EXTENSION_PAGE_TEXT when nothing is selected", () => {
    document.body.innerHTML = `<p>Tin nhắn A</p><p>Tin nhắn B</p>`;
    expect(capture(document, { rectOf: visible, viewport: { width: 800, height: 600 } })).toEqual({
      text: "Tin nhắn A\nTin nhắn B",
      origin: "EXTENSION_PAGE_TEXT",
    });
  });

  it("returns null when there is nothing to check", () => {
    expect(capture(document, { rectOf: visible })).toBeNull();
  });
});
