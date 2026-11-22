import type { DecisionTier } from "../shared/types";

export const TIER_STYLE: Record<DecisionTier, { box: string; title: string; chip: string; label: string }> = {
  ALLOW: {
    box: "border-green-300 bg-green-50",
    title: "text-green-800",
    chip: "bg-green-600",
    label: "Chưa thấy dấu hiệu bất thường",
  },
  SOFT_FRICTION: {
    box: "border-amber-300 bg-amber-50",
    title: "text-amber-800",
    chip: "bg-amber-500",
    label: "Có dấu hiệu đáng ngờ, cần kiểm tra thêm",
  },
  HARD_HOLD: {
    box: "border-red-400 bg-red-50",
    title: "text-red-800",
    chip: "bg-red-600",
    label: "Rất có dấu hiệu lừa đảo, đừng chuyển tiền",
  },
};

export const CALM_BANNER_VI = "MoMo không bao giờ gọi điện yêu cầu bạn chuyển tiền";
export const CALM_MAX_BULLETS = 3;

/** `tel:` link with only digits and a leading plus. */
export function telHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, "")}`;
}

export function coolingText(seconds: number): string | null {
  if (!Number.isFinite(seconds) || seconds <= 0) return null;
  const when = seconds >= 60 ? `${Math.round(seconds / 60)} phút` : `${seconds} giây`;
  return `Hãy chờ ít nhất ${when} và hỏi lại người thân trước khi quyết định.`;
}