import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatVnd } from "../../lib/amount";
import type { SpendAnswerResult } from "../../types/api";

function formatValue(n: number, unit: SpendAnswerResult["unit"]): string {
  if (unit === "VND") return formatVnd(n);
  if (unit === "PERCENT") return `${n}%`;
  return String(n);
}

/** `2026-06-30...` to `30/06`; day buckets only. Week buckets are shown as returned. */
function shortBucket(bucket: string, unit: SpendAnswerResult["bucket_unit"]): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(bucket);
  if (!m) return bucket;
  return unit === "WEEK" ? `Tuần ${m[3]}/${m[2]}` : `${m[3]}/${m[2]}`;
}

/** F6 answer: the template sentence from the backend plus a small chart by day or week. */
export default function SpendAnswer({ answer }: { answer: SpendAnswerResult }) {
  const data = answer.series.map((p) => ({ label: shortBucket(p.bucket, answer.bucket_unit), value: p.value }));
  const delta = answer.delta_percent;
  return (
    <section
      aria-label="Câu trả lời về chi tiêu"
      data-testid="spend-answer"
      className="space-y-3 rounded-xl border border-pink-200 bg-pink-50 p-3"
    >
      <p data-testid="spend-answer-text" className="text-sm font-medium text-slate-900">
        {answer.answer_vi}
      </p>
      <div className="flex items-baseline justify-between gap-2">
        <span data-testid="spend-value" className="text-2xl font-bold text-pink-700">
          {formatValue(answer.value, answer.unit)}
        </span>
        {delta !== null && (
          <span
            data-testid="spend-delta"
            className={`text-sm font-semibold ${delta > 0 ? "text-amber-800" : "text-green-800"}`}
          >
            {delta > 0 ? "Tăng" : delta < 0 ? "Giảm" : "Không đổi"}
            {delta !== 0 ? ` ${Math.abs(delta)}%` : ""} so với kỳ trước
          </span>
        )}
      </div>
      {data.length > 0 ? (
        <div className="h-32 w-full" data-testid="spend-chart" aria-label={answer.bucket_unit === "WEEK" ? "Biểu đồ theo tuần" : "Biểu đồ theo ngày"}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
              <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis hide />
              <Tooltip formatter={(v) => (typeof v === "number" ? formatValue(v, answer.unit) : String(v ?? ""))} />
              <Bar dataKey="value" fill="#a50064" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-xs text-slate-500">Chưa có giao dịch trong khoảng thời gian này.</p>
      )}
      <p className="text-xs text-slate-500">Dữ liệu ví mô phỏng (sandbox).</p>
    </section>
  );
}
