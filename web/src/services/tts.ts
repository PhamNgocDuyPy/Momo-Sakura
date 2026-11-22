/** Text-to-speech via the Web Speech API. Vietnamese voice only; no voice means no read-aloud button. */

export const TTS_LANG = "vi-VN";
export const TTS_RATE = 0.8;
export const VOICES_WAIT_MS = 1000;

function synth(): SpeechSynthesis | null {
  if (typeof window === "undefined") return null;
  return window.speechSynthesis ?? null;
}

function pickVietnamese(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const norm = (l: string): string => l.toLowerCase().replace("_", "-");
  return (
    voices.find((v) => norm(v.lang) === "vi-vn") ?? voices.find((v) => norm(v.lang).startsWith("vi")) ?? null
  );
}

/**
 * Resolve a vi-VN voice. `getVoices()` loads asynchronously on many browsers, so wait for
 * `voiceschanged` for at most `timeoutMs`, then conclude there is no voice.
 */
export function findVietnameseVoice(timeoutMs: number = VOICES_WAIT_MS): Promise<SpeechSynthesisVoice | null> {
  const s = synth();
  if (!s || typeof s.getVoices !== "function") return Promise.resolve(null);
  const now = pickVietnamese(s.getVoices());
  if (now) return Promise.resolve(now);
  return new Promise((resolve) => {
    let done = false;
    const finish = (): void => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      s.removeEventListener?.("voiceschanged", onChange);
      resolve(pickVietnamese(s.getVoices()));
    };
    const onChange = (): void => {
      if (pickVietnamese(s.getVoices())) finish();
    };
    const timer = setTimeout(finish, timeoutMs);
    s.addEventListener?.("voiceschanged", onChange);
  });
}

/** Speak `text` with the Vietnamese voice at the slow rate. Returns false when unavailable. */
export async function speak(text: string, voice?: SpeechSynthesisVoice | null): Promise<boolean> {
  const s = synth();
  if (!s || typeof SpeechSynthesisUtterance === "undefined" || text.trim() === "") return false;
  const v = voice ?? (await findVietnameseVoice());
  if (!v) return false;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = TTS_LANG;
  utterance.voice = v;
  utterance.rate = TTS_RATE;
  s.cancel();
  s.speak(utterance);
  return true;
}

export function stopSpeaking(): void {
  synth()?.cancel();
}
