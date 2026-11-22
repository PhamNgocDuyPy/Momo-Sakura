import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHIP_LABEL, CHIP_TAG, startAutoProtect, type AutoProtect } from "../src/content/autoProtect";
import { AUTO_PROTECT_KEY, getAutoProtectMap, isAutoProtectEnabled, normalizeHost, setAutoProtect } from "../src/shared/autoProtect";
import { installChromeStorage } from "./helpers";

const SCAM = "Chuyển gấp cho em 100k đi chị, em vừa mới đổi tài khoản nên chuyển vào tài khoản này nhé : 0378582085 tpbank";
const BENIGN = "ok mai gặp nhé chị ơi, cảm ơn chị nhiều";

let ap: AutoProtect | null = null;
let fetchSpy: ReturnType<typeof vi.fn>;

function addMessage(text: string, tag = "div"): HTMLElement {
  const row = document.createElement("div");
  row.className = "row";
  const bubble = document.createElement(tag);
  bubble.textContent = text;
  const time = document.createElement("span");
  time.textContent = "09:12";
  bubble.append(time);
  row.append(bubble);
  document.body.append(row);
  return bubble;
}
const chips = (): HTMLElement[] => Array.from(document.querySelectorAll<HTMLElement>(CHIP_TAG));
const flush = async (): Promise<void> => {
  await vi.advanceTimersByTimeAsync(400);
};

beforeEach(() => {
  vi.useFakeTimers();
  fetchSpy = vi.fn(() => Promise.reject(new Error("network is not allowed while scanning")));
  vi.stubGlobal("fetch", fetchSpy);
  document.body.innerHTML = "";
});
afterEach(() => {
  ap?.stop();
  ap = null;
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("startAutoProtect", () => {
  it("attaches exactly one chip to a flagged new message and none to a benign one", async () => {
    const onCheck = vi.fn();
    ap = startAutoProtect({ onCheck });
    addMessage(SCAM);
    addMessage(BENIGN);
    await flush();
    expect(chips()).toHaveLength(1);
    expect(ap.chipCount()).toBe(1);
    const btn = chips()[0]!.shadowRoot!.querySelector("button")!;
    expect(btn).toHaveTextContent(CHIP_LABEL);
    expect(chips()[0]!.shadowRoot!.querySelector("style")!.textContent).not.toMatch(/green|#22c55e|an toàn/i);
    expect(btn.textContent).not.toMatch(/an toàn/i);
  });

  it("does not attach duplicate chips when the same element mutates again", async () => {
    ap = startAutoProtect({ onCheck: vi.fn() });
    const bubble = addMessage(SCAM);
    await flush();
    bubble.append(document.createElement("i")); // unrelated child mutation
    bubble.parentElement!.append(document.createElement("b"));
    await flush();
    expect(chips()).toHaveLength(1);
  });

  it("scans the messages already visible once when switched on", () => {
    addMessage(SCAM);
    addMessage(BENIGN);
    ap = startAutoProtect({ onCheck: vi.fn(), isVisible: () => true });
    expect(chips()).toHaveLength(1);
  });

  it("skips messages that are not visible in the initial scan", () => {
    addMessage(SCAM);
    ap = startAutoProtect({ onCheck: vi.fn(), isVisible: () => false });
    expect(chips()).toHaveLength(0);
  });

  it("ignores inputs, scripts, editable areas, our own hosts and huge containers", async () => {
    ap = startAutoProtect({ onCheck: vi.fn() });
    const ta = document.createElement("textarea");
    ta.value = SCAM;
    ta.textContent = SCAM;
    const script = document.createElement("script");
    script.type = "text/plain";
    script.textContent = SCAM;
    const editable = document.createElement("div");
    editable.setAttribute("contenteditable", "true");
    editable.textContent = SCAM;
    const own = document.createElement("momo-guardian-root");
    own.textContent = SCAM;
    const huge = document.createElement("div");
    huge.textContent = `${SCAM} ${"lorem ipsum ".repeat(250)}`;
    document.body.append(ta, script, editable, own, huge);
    await flush();
    expect(chips()).toHaveLength(0);
  });

  it("caps the number of chips", async () => {
    ap = startAutoProtect({ onCheck: vi.fn(), maxChips: 3 });
    for (let i = 0; i < 8; i++) addMessage(`${SCAM} số ${i}`);
    await flush();
    expect(chips()).toHaveLength(3);
  });

  it("defaults to a cap of 20 chips", async () => {
    ap = startAutoProtect({ onCheck: vi.fn() });
    for (let i = 0; i < 30; i++) addMessage(`${SCAM} số ${i}`);
    await flush();
    expect(chips()).toHaveLength(20);
  });

  it("debounces: nothing is scanned before the debounce delay", async () => {
    ap = startAutoProtect({ onCheck: vi.fn(), debounceMs: 300 });
    addMessage(SCAM);
    await vi.advanceTimersByTimeAsync(100);
    expect(chips()).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(300);
    expect(chips()).toHaveLength(1);
  });

  it("calls onCheck with exactly that message's text when the chip is clicked", async () => {
    const onCheck = vi.fn();
    ap = startAutoProtect({ onCheck });
    addMessage("Hôm nay chị khỏe không, nhớ ăn cơm đúng giờ nhé");
    addMessage(SCAM);
    await flush();
    expect(onCheck).not.toHaveBeenCalled();
    chips()[0]!.shadowRoot!.querySelector("button")!.click();
    expect(onCheck).toHaveBeenCalledTimes(1);
    expect(onCheck).toHaveBeenCalledWith(SCAM);
  });

  it("makes no network call while scanning", async () => {
    ap = startAutoProtect({ onCheck: vi.fn(), isVisible: () => true });
    addMessage(SCAM);
    addMessage(BENIGN);
    await flush();
    expect(chips()).toHaveLength(1);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("stop() removes the chips and stops watching", async () => {
    ap = startAutoProtect({ onCheck: vi.fn() });
    addMessage(SCAM);
    await flush();
    expect(chips()).toHaveLength(1);
    ap.stop();
    expect(chips()).toHaveLength(0);
    addMessage(`${SCAM} khác`);
    await flush();
    expect(chips()).toHaveLength(0);
  });
});

describe("per-domain storage", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("is off by default and stores the switch per hostname", async () => {
    const store = installChromeStorage();
    expect(await isAutoProtectEnabled("chat.zalo.me")).toBe(false);
    await setAutoProtect("Chat.Zalo.me", true);
    expect(store[AUTO_PROTECT_KEY]).toEqual({ "chat.zalo.me": true });
    expect(await isAutoProtectEnabled("chat.zalo.me")).toBe(true);
    expect(await isAutoProtectEnabled("facebook.com")).toBe(false);
    await setAutoProtect("chat.zalo.me", false);
    expect(await getAutoProtectMap()).toEqual({});
  });

  it("normalizes hosts and rejects junk", () => {
    expect(normalizeHost("https://Chat.Zalo.me/abc")).toBe("chat.zalo.me");
    expect(normalizeHost("localhost:5173")).toBe("localhost");
    expect(normalizeHost("not a host!")).toBeNull();
    expect(normalizeHost("")).toBeNull();
  });
});
describe("startAutoProtect sidebar", () => {
  it("does not flag previews inside an aside / conversation list, but flags the open chat", () => {
    document.body.innerHTML = `<aside><button><div id="prev"></div></button></aside><main><div id="open"></div></main>`;
    document.getElementById("prev")!.textContent = SCAM;
    document.getElementById("open")!.textContent = SCAM;
    ap = startAutoProtect({ onCheck: () => undefined, isVisible: () => true });
    expect(chips()).toHaveLength(1);
    expect(document.querySelector("aside")?.querySelector(CHIP_TAG)).toBeNull();
  });
});