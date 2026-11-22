import { Children, type ReactNode } from "react";
import { formatVnd } from "../../lib/amount";
import type { CheckResponse, DecisionTier, Extensions } from "../../types/api";
import SandboxBadge from "./SandboxBadge";
import { CALM_MAX_BULLETS, useCalm } from "./CalmShield";

const TIER_STYLE: Record<DecisionTier, { box: string; title: string; label: string }> = {
  ALLOW: {
    box: "border-green-300 bg-green-50",
    title: "text-green-800",
    label: "Chưa thấy dấu hiệu bất thường",
  },
  SOFT_FRICTION: {
    box: "border-amber-300 bg-amber-50",
    title: "text-amber-800",
    label: "Cần kiểm tra thêm trước khi chuyển",
  },
  HARD_HOLD: {
    box: "border-red-300 bg-red-50",
    title: "text-red-800",
    label: "Guardian đã tạm giữ giao dịch này",
  },
};

interface Props {
  response: CheckResponse;
  /** Action buttons rendered below the bullets (e.g. transfer, ask Guardian). */
  children?: ReactNode;
}

function safeVnd(n: number | null | undefined): string | null {
  return typeof n === "number" && Number.isSafeInteger(n) && n >= 0 ? formatVnd(n) : null;
}

/** `2026-06-30` or an ISO timestamp to `30/06/2026`; anything else is shown unchanged. */
function viDate(s: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : s;
}

type Listing = NonNullable<Extensions["listing"]>;
type Promo = NonNullable<Extensions["promo"]>;

function cheaperPercent(l: Listing): number | null {
  if (l.discount_percent != null) return Math.round(l.discount_percent);
  if (l.listed_price_vnd != null && l.reference_price_vnd != null && l.reference_price_vnd > 0) {
    return Math.round((1 - l.listed_price_vnd / l.reference_price_vnd) * 100);
  }
  return null;
}

function ListingPanel({ listing, showTips }: { listing: Listing; showTips: boolean }) {
  const listed = safeVnd(listing.listed_price_vnd);
  const reference = safeVnd(listing.reference_price_vnd);
  const pct = cheaperPercent(listing);
  return (
    <div data-testid="listing-panel" className="mt-3 rounded-lg border border-slate-200 bg-white/80 p-3 text-sm">
      <h3 className="font-semibold text-slate-900">Giá món hàng</h3>
      <dl className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1">
        <dt className="text-slate-500">Giá rao</dt>
        <dd data-testid="listing-listed" className="text-right font-medium">
          {listed ?? "Chưa rõ"}
        </dd>
        <dt className="text-slate-500">Giá tham chiếu</dt>
        <dd data-testid="listing-reference" className="text-right font-medium">
          {reference ?? "Chưa có giá tham chiếu"}
        </dd>
        {pct !== null && pct > 0 && (
          <>
            <dt className="text-slate-500">Rẻ hơn tham chiếu</dt>
            <dd data-testid="listing-cheaper" className="text-right font-semibold text-amber-800">
              {pct}%
            </dd>
          </>
        )}
      </dl>
      {showTips && (
        <div data-testid="safe-payment-tips" className="mt-2 rounded-md bg-sky-50 p-2 text-sky-900">
          <p className="font-medium">Cách thanh toán an toàn hơn</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            <li>Ưu tiên thanh toán khi nhận hàng (COD) và kiểm tra hàng trước khi trả tiền.</li>
            <li>Dùng kênh có bảo vệ người mua của sàn thay vì chuyển khoản trực tiếp.</li>
            <li>Tránh đặt cọc hoặc chuyển trước cho người bán chưa xác minh.</li>
          </ul>
        </div>
      )}
    </div>
  );
}

function PromoPanel({ promo }: { promo: Promo }) {
  const official = promo.official_promo;
  return (
    <div data-testid="promo-panel" className="mt-3 rounded-lg border border-slate-200 bg-white/80 p-3 text-sm">
      <h3 className="font-semibold text-slate-900">Khuyến mãi của {promo.brand}</h3>
      <p
        data-testid="promo-match"
        className={`mt-1 font-medium ${promo.matched ? "text-green-800" : "text-amber-800"}`}
      >
        {promo.matched
          ? "Nội dung khớp với khuyến mãi chính thức Guardian đang có."
          : "Chưa thấy khuyến mãi chính thức nào khớp với nội dung này."}
      </p>
      {official ? (
        <p data-testid="promo-official" className="mt-1 text-slate-700">
          Khuyến mãi chính thức: {official.title_vi} (đến {viDate(official.valid_to)})
        </p>
      ) : (
        <p className="mt-1 text-slate-500">Guardian chưa có thông tin khuyến mãi chính thức để đối chiếu.</p>
      )}
    </div>
  );
}

/** Renders only strings that come from GuardianVerdict (template-backed) and typed response fields. */
export default function ResultCard({ response, children }: Props) {
  const calm = useCalm();
  const { verdict, extensions } = response;
  const style = TIER_STYLE[verdict.decision_tier];
  const bullets = calm ? verdict.evidence_bullets.slice(0, CALM_MAX_BULLETS) : verdict.evidence_bullets;
  const listing = extensions?.listing ?? null;
  const promo = calm ? null : (extensions?.promo ?? null);
  return (
    <section
      aria-label="Kết quả kiểm tra"
      data-tier={verdict.decision_tier}
      className={`rounded-xl border p-4 ${style.box} ${calm ? "text-[1.125rem] leading-relaxed" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className={`font-semibold ${calm ? "text-[1.25rem]" : "text-base"} ${style.title}`}>{style.label}</h2>
        {response.sandbox_sources.length > 0 && <SandboxBadge />}
      </div>
      {bullets.length > 0 && (
        <ul
          className={`mt-2 list-disc space-y-1 pl-5 ${calm ? "text-[1.125rem] font-medium text-slate-900" : "text-sm text-gray-800"}`}
        >
          {bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      )}
      {listing && <ListingPanel listing={listing} showTips={response.ui_hints.safe_payment_tips} />}
      {promo && <PromoPanel promo={promo} />}
      {Children.toArray(children).length > 0 && <div className="mt-3 flex flex-col gap-2">{children}</div>}
    </section>
  );
}
