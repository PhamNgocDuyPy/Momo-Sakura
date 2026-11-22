/** SHA-256 hex digest of text. */
export async function sha256Hex(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export interface ClipboardDedupe {
  /** True when `text` differs from the last accepted value; records it if so. */
  accept(text: string): Promise<boolean>;
  reset(): void;
}

/** Compares SHA-256 of each value with the previously accepted one (Req 3.4). */
export function createClipboardDedupe(): ClipboardDedupe {
  let last: string | null = null;
  return {
    async accept(text: string): Promise<boolean> {
      const hash = await sha256Hex(text);
      if (hash === last) return false;
      last = hash;
      return true;
    },
    reset(): void {
      last = null;
    },
  };
}
