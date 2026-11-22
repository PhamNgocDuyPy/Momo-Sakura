import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { findVietnameseVoice, speak, TTS_RATE } from "../src/services/tts";

type Listener = () => void;

class FakeUtterance {
  lang = "";
  rate = 1;
  voice: unknown = null;
  constructor(public text: string) {}
}

function installSynth(initialVoices: { lang: string; name: string }[]) {
  const listeners: Listener[] = [];
  let voices = initialVoices;
  const synth = {
    getVoices: () => voices,
    addEventListener: (_: string, l: Listener) => listeners.push(l),
    removeEventListener: (_: string, l: Listener) => {
      const i = listeners.indexOf(l);
      if (i >= 0) listeners.splice(i, 1);
    },
    speak: vi.fn(),
    cancel: vi.fn(),
  };
  Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
  return {
    synth,
    setVoices: (v: { lang: string; name: string }[]) => {
      voices = v;
      listeners.slice().forEach((l) => l());
    },
  };
}

describe("tts", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    Reflect.deleteProperty(window, "speechSynthesis");
  });

  it("speaks with the vi-VN voice at rate 0.8", async () => {
    const { synth } = installSynth([
      { lang: "en-US", name: "en" },
      { lang: "vi-VN", name: "vi" },
    ]);
    expect(await speak("Xin chào")).toBe(true);
    const u = synth.speak.mock.calls[0][0] as FakeUtterance;
    expect(u.lang).toBe("vi-VN");
    expect(u.rate).toBe(0.8);
    expect(TTS_RATE).toBe(0.8);
    expect((u.voice as { name: string }).name).toBe("vi");
  });

  it("waits for voiceschanged", async () => {
    const { setVoices } = installSynth([]);
    const p = findVietnameseVoice();
    setVoices([{ lang: "vi_VN", name: "late" }]);
    await expect(p).resolves.toMatchObject({ name: "late" });
  });

  it("gives up after 1 second without a Vietnamese voice", async () => {
    const { synth } = installSynth([{ lang: "en-US", name: "en" }]);
    const p = findVietnameseVoice();
    let settled = false;
    void p.then(() => (settled = true));
    await vi.advanceTimersByTimeAsync(999);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(2);
    await expect(p).resolves.toBeNull();
    const spoke = speak("Xin chào");
    await vi.advanceTimersByTimeAsync(1100);
    expect(await spoke).toBe(false);
    expect(synth.speak).not.toHaveBeenCalled();
  });

  it("returns null when speechSynthesis is missing", async () => {
    await expect(findVietnameseVoice()).resolves.toBeNull();
  });
});
