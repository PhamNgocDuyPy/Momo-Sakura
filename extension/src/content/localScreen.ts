// Local, offline screening for "Tự động bảo vệ". Pure functions, no network, no storage.
// The result is only a hint to show "Guardian: nên kiểm tra"; it is never a verdict.

export const FLAG_THRESHOLD = 4;

export interface ScreenResult {
  score: number;
  flagged: boolean;
  /** Names of the feature groups that matched (for tests and debugging). */
  features: string[];
}

/** Lower-case, strip Vietnamese diacritics, map đ to d, collapse whitespace. */
export function foldVi(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/\s+/g, " ")
    .trim();
}

const BANKS =
  "vcb|vietcombank|tcb|techcombank|tpbank|tpb|mbbank|mb|bidv|vietinbank|ctg|agribank|acb|sacombank|stb|vpbank|ocb|shb|hdbank|msb|eximbank|scb|seabank|vib|lpbank|momo|nam a bank|ngan hang";
const BANK_RE = new RegExp(`\\b(?:${BANKS})\\b`);
const DIGIT_RUN_RE = /\d(?:[\d .-]{4,24}\d)|\d{6,19}/g;

interface Feature {
  name: string;
  weight: number;
  test: RegExp;
}

// Patterns run on the folded text (no diacritics), so "chuyển khoản" matches "chuyen khoan".
const FEATURES: Feature[] = [
  { name: "transfer", weight: 2, test: /\b(?:chuyen khoan|chuyen tien|chuyen gap|chuyen ngay|ck|stk|so tai khoan|so tk|stk nhan)\b/ },
  {
    name: "account_change",
    weight: 3,
    test: /\b(?:doi (?:tai khoan|stk|so tai khoan)|tai khoan moi|stk moi|so (?:tai khoan|tk) moi|chuyen vao (?:tai khoan|stk) (?:nay|moi)|nick (?:bi|da bi) hack|bi hack|muon tam)\b/,
  },
  {
    name: "authority",
    weight: 3,
    test: /\b(?:cong an|vien kiem sat|vneid|toa an|can bo dieu tra|co quan dieu tra|rua tien|lenh bat|lenh truy na)\b/,
  },
  { name: "url", weight: 1.5, test: /(?:https?:\/\/|www\.|\b[a-z0-9-]+\.(?:top|xyz|vip|icu|site|click|cc|me|ly|link|apk)\b|\bbit\.ly\b|\.apk\b)/ },
  { name: "fee", weight: 1.5, test: /\b(?:phi|dat coc|tien coc|coc|mo khoa|phi mo khoa|nap phi|dong phi)\b/ },
  { name: "shipper", weight: 2, test: /\b(?:shipper|thu hoi don|don bi loi|don hang bi loi|thu hoi)\b/ },
  { name: "prize", weight: 2, test: /\b(?:trung thuong|nhan thuong|trao thuong|phan thuong|qua tang|boc tham|rut tham)\b/ },
];

// "gấp" folds to "gap", the same as "gặp" (to meet). Judge it on the accented text when there is any.
const URGENT_ACCENTED = /(?:\bgấp\b|\bngay\b|khẩn cấp|\bkhan cap\b|\bngay lập tức\b)/;
const URGENT_FOLDED = /\b(?:khan cap|ngay lap tuc|gap|ngay)\b/;
const HAS_VI_DIACRITIC = /[\u00c0-\u1ef9]/i;

function hasDigitRunNearBank(folded: string): { run: boolean; nearBank: boolean } {
  let run = false;
  for (const m of folded.matchAll(DIGIT_RUN_RE)) {
    const digits = m[0].replace(/\D/g, "");
    if (digits.length < 6 || digits.length > 19) continue;
    run = true;
    const start = m.index ?? 0;
    const around = folded.slice(Math.max(0, start - 40), start + m[0].length + 40);
    if (BANK_RE.test(around)) return { run, nearBank: true };
  }
  return { run, nearBank: false };
}

function isUrgent(raw: string, folded: string): boolean {
  const lower = raw.toLowerCase().normalize("NFC");
  if (URGENT_ACCENTED.test(lower)) return true;
  // Without diacritics ("chuyen gap") the folded form is all we have.
  return !HAS_VI_DIACRITIC.test(lower) && URGENT_FOLDED.test(folded);
}

/** Scores one message. Each feature group counts once. */
export function screenMessage(text: string): ScreenResult {
  const folded = foldVi(text);
  const features: string[] = [];
  let score = 0;
  for (const f of FEATURES) {
    if (f.test.test(folded)) {
      features.push(f.name);
      score += f.weight;
    }
  }
  const digits = hasDigitRunNearBank(folded);
  if (digits.nearBank) {
    features.push("account_near_bank");
    score += 3;
  } else if (digits.run) {
    features.push("digit_run");
    score += 1;
  }
  if (isUrgent(text, folded)) {
    features.push("urgency");
    score += 1;
  }
  return { score, flagged: score >= FLAG_THRESHOLD, features };
}
