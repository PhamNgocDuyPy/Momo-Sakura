import type { CheckResponse } from "../../types/api";

interface Props {
  response: CheckResponse;
}

function ms(value: number | null): string {
  return value === null ? "–" : `${value} ms`;
}

export default function DecisionTrace({ response }: Props) {
  const { trace, rules_fired: rules, stage_timings_ms: timings } = response;
  return (
    <details className="rounded-xl border border-gray-200 bg-white p-3 text-sm">
      <summary className="cursor-pointer font-medium">Guardian đã quyết định thế nào</summary>
      <table className="mt-2 w-full text-left text-xs">
        <thead>
          <tr className="text-gray-500">
            <th className="py-1 pr-2">Bước</th>
            <th className="py-1 pr-2">Trạng thái</th>
            <th className="py-1 text-right">Thời gian</th>
          </tr>
        </thead>
        <tbody>
          {trace.map((s) => (
            <tr key={s.seq} className="border-t border-gray-100">
              <td className="py-1 pr-2">{s.name}</td>
              <td className="py-1 pr-2">{s.status}</td>
              <td className="py-1 text-right">{s.duration_ms} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rules.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-medium text-gray-600">Luật đã kích hoạt</p>
          <ul className="mt-1 space-y-0.5 text-xs">
            {rules.map((r, i) => (
              <li key={`${r.rule}-${i}`}>
                {r.rule}: {r.effect} ({r.reason_code})
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-2 text-xs text-gray-600">
        Giai đoạn 2: {ms(timings.stage2)} · Giai đoạn 3: {ms(timings.stage3)} · Tổng:{" "}
        {ms(timings.total ?? response.latency_ms)}
      </p>
    </details>
  );
}
