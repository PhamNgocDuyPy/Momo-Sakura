import { describe, expect, it } from "vitest";
import { FLAG_THRESHOLD, foldVi, screenMessage } from "../src/content/localScreen";

const SCAM = [
  "Chuyển gấp cho em 100k đi chị, em vừa mới đổi tài khoản nên chuyển vào tài khoản này nhé : 0378582085 tpbank",
  "Đây là Công an quận 1, tài khoản VNeID của bạn liên quan đường dây rửa tiền, chuyển 50tr vào stk 1903777888999 TCB để xác minh, không được nói với ai",
  "Shipper đây, đơn bị lỗi cần thu hồi, chuyển khoản trước 35k phí ship lại",
  "ck t 2 lít vào stk 0123456789 VCB nha, tiền cơm",
  "Chúc mừng bạn trúng thưởng 50 triệu, đóng phí nhận thưởng tại https://momo-qua-tang.top ngay",
  "Anh ơi nick em bị hack, mượn tạm 2tr chuyển vào stk mới 9704123456 MB nhé khẩn cấp",
];

const CALM = [
  "ok mai gặp nhé",
  "cảm ơn chị",
  "Trưa nay ăn cơm tấm nha, vui lắm.",
  "Đơn của mình bao giờ tới vậy shop?",
  "Mai mấy giờ họp vậy em?",
  "Ok, mình ra liền.",
];

describe("foldVi", () => {
  it("removes diacritics and maps đ to d", () => {
    expect(foldVi("Chuyển KHOẢN Đổi tài khoản")).toBe("chuyen khoan doi tai khoan");
  });
});

describe("screenMessage", () => {
  it.each(SCAM)("flags scam-like message: %s", (text) => {
    const r = screenMessage(text);
    expect(r.flagged).toBe(true);
    expect(r.score).toBeGreaterThanOrEqual(FLAG_THRESHOLD);
  });

  it.each(CALM)("does not flag ordinary chat: %s", (text) => {
    expect(screenMessage(text).flagged).toBe(false);
  });

  it("reports the feature groups for the demo message", () => {
    const r = screenMessage(SCAM[0]!);
    expect(r.features).toEqual(expect.arrayContaining(["transfer", "account_change", "account_near_bank", "urgency"]));
  });

  it("matches without diacritics too", () => {
    expect(screenMessage("chuyen gap cho em, em doi tai khoan roi, stk moi 0378582085 tpbank").flagged).toBe(true);
  });

  it("does not treat 'gặp' as urgency", () => {
    expect(screenMessage("mai gặp nhé").features).not.toContain("urgency");
    expect(screenMessage("làm gấp giúp em").features).toContain("urgency");
  });

  it("a bare phone-like number alone is not enough", () => {
    expect(screenMessage("số điện thoại em là 0912345678 nhé").flagged).toBe(false);
  });
});