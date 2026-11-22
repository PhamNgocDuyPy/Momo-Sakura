// Amount parser and formatter. Mirrors backend `guardian/tools/amount.py`.

const NUM = String.raw`\d+(?:[.,]\d+)?`;
const GROUPED = String.raw`\d{1,3}(?:\.\d{3})+`;

const RE_LIT = /^(\d+)\s*(?:lít|lit)$/;
const RE_XI = /^(\d+)\s*(?:xị|xi)$/;
const RE_CU = /^(\d+)\s*(?:củ|cu)$/;
const RE_K = new RegExp(String.raw`^(${NUM})\s*(?:k|nghìn|ngàn|nghin|ngan)$`);
const RE_TR_DIGITS = /^(\d+)\s*(?:tr|triệu|trieu)\s*(\d{1,3})$/;
const RE_TR = new RegExp(String.raw`^(${NUM})\s*(?:tr|triệu|trieu|m)$`);
const RE_GROUPED = new RegExp(String.raw`^(${GROUPED})\s*(?:đ|vnd|vnđ|d)?$`);
const RE_PLAIN = /^(\d+)\s*(?:đ|vnd|vnđ|d)?$/;

// In-sentence scan: only units, thousand separators or currency suffixes count.
// Bare digit runs (e.g. account numbers) never match.
const UNIT = "(?:tr|triệu|trieu)";
const WORD = String.raw`[\p{L}\p{N}_]`;
const SCAN_SOURCE =
  String.raw`(?<![\p{L}\p{N}_.,])(?:` +
  String.raw`\d+\s*${UNIT}\s*\d{1,3}` +
  String.raw`|${NUM}\s*(?:tr|triệu|trieu|m|k|nghìn|ngàn|nghin|ngan)` +
  String.raw`|\d+\s*(?:lít|lit|xị|xi|củ|cu)` +
  String.raw`|${GROUPED}(?:\s*(?:đ|vnd|vnđ))?` +
  String.raw`|\d+\s*(?:đ|vnd|vnđ)` +
  String.raw`)(?!${WORD})(?![.,]\d)`;

function normalize(text: string): string {
  return text.trim().toLowerCase().normalize("NFC");
}

/** n * mult where n is a decimal string ("1.5" or "1,5"); null if the result is not an integer. */
function scaleDecimal(raw: string, mult: bigint): bigint | null {
  const [intPart, fracPart = ""] = raw.replace(",", ".").split(".");
  const numerator = BigInt(intPart + fracPart);
  const scale = 10n ** BigInt(fracPart.length);
  const product = numerator * mult;
  return product % scale === 0n ? product / scale : null;
}

function toSafeNumber(value: bigint | null): number | null {
  if (value === null || value < 0n || value > BigInt(Number.MAX_SAFE_INTEGER)) return null;
  return Number(value);
}

function parseNormalized(s: string): number | null {
  let m = RE_LIT.exec(s) ?? RE_XI.exec(s);
  if (m) return toSafeNumber(BigInt(m[1]) * 100_000n);
  m = RE_CU.exec(s);
  if (m) return toSafeNumber(BigInt(m[1]) * 1_000_000n);
  m = RE_K.exec(s);
  if (m) return toSafeNumber(scaleDecimal(m[1], 1000n));
  m = RE_TR_DIGITS.exec(s);
  if (m) {
    const b = m[2];
    return toSafeNumber(BigInt(m[1]) * 1_000_000n + BigInt(b) * 10n ** BigInt(6 - b.length));
  }
  m = RE_TR.exec(s);
  if (m) return toSafeNumber(scaleDecimal(m[1], 1_000_000n));
  m = RE_GROUPED.exec(s);
  if (m) return toSafeNumber(BigInt(m[1].replaceAll(".", "")));
  m = RE_PLAIN.exec(s);
  if (m) return toSafeNumber(BigInt(m[1]));
  return null;
}

/** Parse a Vietnamese amount string into integer VND, or null. Never throws. */
export function parseAmount(text: string): number | null {
  if (typeof text !== "string") return null;
  try {
    return parseNormalized(normalize(text));
  } catch {
    return null;
  }
}

/** Integer VND amounts found in a sentence, in order of appearance. */
export function findAmounts(text: string): number[] {
  if (typeof text !== "string") return [];
  const found: number[] = [];
  for (const m of normalize(text).matchAll(new RegExp(SCAN_SOURCE, "gu"))) {
    const value = parseNormalized(m[0].trim());
    if (value !== null) found.push(value);
  }
  return found;
}

/** Format a non-negative safe integer as `1.234.567 đ`. */
export function formatVnd(n: number): string {
  if (!Number.isSafeInteger(n) || n < 0) {
    throw new RangeError("formatVnd expects a non-negative integer");
  }
  return `${n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".")} đ`;
}
