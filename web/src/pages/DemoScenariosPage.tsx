import { useCallback, useEffect, useState } from "react";
import { matchExpectation, resolvePrev } from "../lib/expectation";
import { evalApi } from "../services/api";
import { useGuardianOptional } from "../state/guardianStore";
import type { CheckResponse, EvalScenario } from "../types/api";

interface CaseOutcome {
  endpoint: string;
  expectedText: string;
  actualTier: string | null;
  actualCodes: string[];
  mismatches: string[];
}

interface ScenarioOutcome {
  status: "running" | "passed" | "failed";
  cases: CaseOutcome[];
}

type Obj = Record<string, unknown>;

function isObj(value: unknown): value is Obj {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function describeExpectation(expect: Obj): string {
  const parts: string[] = [];
  const tier = expect["decision_tier"];
  if (typeof tier === "string") parts.push(tier);
  else if (isObj(tier) && typeof tier["min"] === "string") parts.push(`≥ ${tier["min"]}`);
  const include = expect["reason_codes_include"];
  if (Array.isArray(include) && include.length > 0) parts.push(include.map(String).join(", "));
  const stops = expect["stop_codes_include"];
  if (Array.isArray(stops) && stops.length > 0) parts.push(stops.map(String).join(", "));
  const qr = expect["qr_result"];
  if (typeof qr === "string") parts.push(qr);
  return parts.join(" · ") || "Kiểm tra theo điều kiện chi tiết";
}

function actualOf(body: unknown): { tier: string | null; codes: string[] } {
  if (!isObj(body)) return { tier: null, codes: [] };
  const verdict = isObj(body["verdict"]) ? body["verdict"] : body;
  const tier = typeof verdict["decision_tier"] === "string" ? verdict["decision_tier"] : null;
  const codes = Array.isArray(verdict["reason_codes"]) ? verdict["reason_codes"].map(String) : [];
  return { tier, codes };
}

/** Debug-only fixtures lose their `debug` block when the backend runs without GUARDIAN_DEBUG. */
function missingDebug(s: EvalScenario): boolean {
  return s.requires_debug && !s.cases.some((c) => "debug" in c.request);
}

function isCheckResponse(body: unknown): body is CheckResponse {
  return isObj(body) && isObj(body["verdict"]) && typeof body["verdict"]["decision_tier"] === "string";
}

export default function DemoScenariosPage() {
  const guardian = useGuardianOptional();
  const dispatch = guardian?.dispatch;
  const [scenarios, setScenarios] = useState<EvalScenario[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [outcomes, setOutcomes] = useState<Record<string, ScenarioOutcome>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    evalApi
      .scenarios()
      .then((list) => {
        if (!cancelled) setScenarios(list);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const runScenario = useCallback(
    async (scenario: EvalScenario): Promise<boolean> => {
      setOutcomes((prev) => ({ ...prev, [scenario.id]: { status: "running", cases: [] } }));
      const results: CaseOutcome[] = [];
      let prevBody: unknown = null;
      for (const c of scenario.cases) {
        let body: unknown;
        let mismatches: string[];
        try {
          const request = prevBody === null ? c.request : (resolvePrev(c.request, prevBody) as Obj);
          body = await evalApi.runCase(c.endpoint, request);
          if (isCheckResponse(body)) {
            body = { ...body, from_demo: true };
            dispatch?.({ type: "VERDICT_RECEIVED", response: body as CheckResponse });
          }
          mismatches = matchExpectation(body, c.expect, { skipUnavailableReferences: true });
        } catch (error) {
          body = null;
          mismatches = [`request failed: ${error instanceof Error ? error.message : String(error)}`];
        }
        const actual = actualOf(body);
        results.push({
          endpoint: c.endpoint,
          expectedText: describeExpectation(c.expect),
          actualTier: actual.tier,
          actualCodes: actual.codes,
          mismatches,
        });
        prevBody = body ?? {};
      }
      const passed = results.every((r) => r.mismatches.length === 0);
      setOutcomes((prev) => ({
        ...prev,
        [scenario.id]: { status: passed ? "passed" : "failed", cases: results },
      }));
      return passed;
    },
    [dispatch],
  );

  const runOne = async (scenario: EvalScenario): Promise<void> => {
    setBusy(true);
    try {
      await runScenario(scenario);
    } finally {
      setBusy(false);
    }
  };

  const runnable = (scenarios ?? []).filter((s) => !missingDebug(s));
  const runAll = async (): Promise<void> => {
    setBusy(true);
    setOutcomes({});
    try {
      for (const s of runnable) await runScenario(s);
    } finally {
      setBusy(false);
    }
  };

  const finished = runnable.filter((s) => {
    const status = outcomes[s.id]?.status;
    return status === "passed" || status === "failed";
  });
  const passedCount = finished.filter((s) => outcomes[s.id]?.status === "passed").length;

  return (
    <main className="mx-auto max-w-md space-y-3 p-4">
      <h1 className="text-xl font-semibold">Kịch bản demo</h1>
      <p className="text-sm text-gray-600">
        Kết quả chạy từ trang này không được tính vào thống kê Shield. Dữ liệu là sandbox.
      </p>
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="rounded bg-pink-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          disabled={busy || runnable.length === 0}
          onClick={() => void runAll()}
        >
          Chạy tất cả
        </button>
        <p role="status" className="text-sm font-medium">
          Đạt {passedCount}/{runnable.length}
        </p>
      </div>
      {loadError && (
        <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">
          Không tải được danh sách kịch bản.
        </p>
      )}
      {!scenarios && !loadError && <p className="text-sm text-gray-500">Đang tải...</p>}
      <ul className="space-y-2">
        {(scenarios ?? []).map((s) => {
          const outcome = outcomes[s.id];
          const disabled = busy || missingDebug(s);
          return (
            <li key={s.id} data-testid={`scenario-${s.id}`} className="rounded border bg-white p-3 text-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium">
                    {s.id} · {s.title_vi}
                  </p>
                  <p className="text-gray-600">{s.description_vi}</p>
                  <p className="text-xs text-gray-500">
                    Mong đợi: {s.cases.map((c) => describeExpectation(c.expect)).join(" | ")}
                  </p>
                  {missingDebug(s) && (
                    <p className="text-xs text-amber-700">Cần bật GUARDIAN_DEBUG ở backend để chạy kịch bản này.</p>
                  )}
                </div>
                <button
                  type="button"
                  aria-label={`Chạy ${s.id}`}
                  className="shrink-0 rounded border px-2 py-1 disabled:opacity-50"
                  disabled={disabled}
                  onClick={() => void runOne(s)}
                >
                  Chạy
                </button>
              </div>
              {outcome?.status === "running" && <p className="mt-1 text-gray-500">Đang chạy...</p>}
              {outcome?.status === "passed" && <p className="mt-1 font-medium text-green-700">Đạt</p>}
              {outcome?.status === "failed" && (
                <div className="mt-1 space-y-1 text-red-700">
                  <p className="font-medium">Không đạt</p>
                  {outcome.cases
                    .filter((c) => c.mismatches.length > 0)
                    .map((c, i) => (
                      <div key={i} className="rounded bg-red-50 p-2">
                        <p>Mong đợi: {c.expectedText}</p>
                        <p>
                          Thực tế: {c.actualTier ?? "không có tier"}
                          {c.actualCodes.length > 0 ? ` · ${c.actualCodes.join(", ")}` : ""}
                        </p>
                        <ul className="list-disc pl-4 text-xs">
                          {c.mismatches.map((m) => (
                            <li key={m}>{m}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                </div>
              )}
              {outcome?.status === "passed" && outcome.cases.length > 0 && (
                <p className="text-xs text-gray-500">
                  Thực tế: {outcome.cases.map((c) => c.actualTier ?? "-").join(" | ")}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </main>
  );
}
