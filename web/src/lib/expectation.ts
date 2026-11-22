/**
 * Expectation matcher for scenario fixtures. Mirrors `backend/eval/matcher.py`:
 * `matchExpectation(response, expect)` returns mismatch strings; empty means pass.
 */

export type Json = unknown;
type Obj = Record<string, unknown>;

export const TIER_ORDER: Record<string, number> = { ALLOW: 0, SOFT_FRICTION: 1, HARD_HOLD: 2 };

/** Mirrors `ALLOWED_TOOLS` in `guardian/control_plane/tool_runner.py`. */
export const ALLOWED_TOOLS: ReadonlySet<string> = new Set([
  "check_urls",
  "detect_hijack",
  "lookup_official_promos",
  "lookup_payer_history",
  "lookup_recipient_risk_and_simo",
  "lookup_reference_price",
  "napas_name_inquiry_readonly",
  "plan",
  "prompt_guard_cpu_score",
  "quarantined_extract",
  "redact_pii_local",
  "risk_memory_lookup",
  "risk_memory_write",
  "scan_entities",
  "verify_vietqr_emvco",
]);

export type ReferenceFn = (actual: unknown, args: Obj, response: Obj) => boolean;

/** Only `equals_arg` is portable; `spend_reference` needs the backend wallet fixture. */
export const REFERENCE_FUNCS: Record<string, ReferenceFn> = {
  equals_arg: (actual, args) => deepEqual(actual, args["expected"]),
};

export interface MatchOptions {
  /** Reference functions that cannot run in the browser are skipped instead of failing. */
  skipUnavailableReferences?: boolean;
}

function isObj(value: unknown): value is Obj {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((v, i) => deepEqual(v, b[i]));
  }
  if (isObj(a) && isObj(b)) {
    const ka = Object.keys(a);
    return ka.length === Object.keys(b).length && ka.every((k) => k in b && deepEqual(a[k], b[k]));
  }
  return false;
}

function show(value: unknown): string {
  return JSON.stringify(value) ?? String(value);
}

/** Dotted path over objects and integer list indexes (same rules as `get_path`). */
export function getPath(data: unknown, path: string): { found: boolean; value: unknown } {
  let current: unknown = data;
  for (const part of path.split(".")) {
    if (isObj(current)) {
      if (!(part in current)) return { found: false, value: undefined };
      current = current[part];
    } else if (Array.isArray(current)) {
      if (!/^\s*[+-]?\d+\s*$/.test(part)) return { found: false, value: undefined };
      const idx = Number.parseInt(part, 10);
      const real = idx < 0 ? current.length + idx : idx;
      if (real < 0 || real >= current.length) return { found: false, value: undefined };
      current = current[real];
    } else {
      return { found: false, value: undefined };
    }
  }
  return { found: true, value: current };
}

function tierOf(response: Obj): string | null {
  const verdict = response["verdict"];
  if (isObj(verdict) && "decision_tier" in verdict) return String(verdict["decision_tier"]);
  const value = response["decision_tier"];
  return value !== undefined && value !== null ? String(value) : null;
}

function reasonCodesOf(response: Obj): string[] {
  const verdict = response["verdict"];
  const codes = isObj(verdict) ? verdict["reason_codes"] : response["reason_codes"];
  return Array.isArray(codes) ? codes.map(String) : [];
}

function qrOf(response: Obj): Obj {
  const qr = response["qr"];
  return isObj(qr) ? qr : {};
}

type Comparable = number | string;
function comparable(a: unknown, b: unknown): a is Comparable {
  return (
    (typeof a === "number" && typeof b === "number") || (typeof a === "string" && typeof b === "string")
  );
}

function contains(actual: unknown, expected: unknown): boolean | null {
  if (typeof actual === "string") return typeof expected === "string" ? actual.includes(expected) : null;
  if (Array.isArray(actual)) return actual.some((v) => deepEqual(v, expected));
  if (isObj(actual)) return typeof expected === "string" ? expected in actual : null;
  return null;
}

function checkAssert(response: Obj, spec: Obj, options: MatchOptions): string | null {
  const path = String(spec["path"] ?? "");
  const op = spec["op"];
  const expected = spec["value"];
  const { found, value: actual } = getPath(response, path);
  const label = `assert ${path} ${String(op)}`;
  if (op === "absent") {
    return !found || actual === null ? null : `${label}: found ${show(actual)}`;
  }
  if (!found) return `${label}: path not found`;
  let ok: boolean;
  switch (op) {
    case "eq":
      ok = deepEqual(actual, expected);
      break;
    case "lt":
    case "gt":
      if (actual === null) {
        ok = false;
      } else if (!comparable(actual, expected) || typeof actual !== typeof expected) {
        return `${label}: incomparable value ${show(actual)} vs ${show(expected)}`;
      } else {
        ok = op === "lt" ? actual < (expected as Comparable) : actual > (expected as Comparable);
      }
      break;
    case "in":
      if (Array.isArray(expected)) ok = expected.some((v) => deepEqual(v, actual));
      else if (typeof expected === "string" && typeof actual === "string") ok = expected.includes(actual);
      else if (isObj(expected) && typeof actual === "string") ok = actual in expected;
      else return `${label}: incomparable value ${show(actual)} vs ${show(expected)}`;
      break;
    case "contains": {
      const result = contains(actual, expected);
      if (result === null) return `${label}: incomparable value ${show(actual)} vs ${show(expected)}`;
      ok = result;
      break;
    }
    case "matches_reference": {
      const name = typeof expected === "string" ? expected : String((expected as Obj | undefined)?.["fn"] ?? "");
      const args = isObj(expected) && isObj(expected["args"]) ? expected["args"] : {};
      const fn = REFERENCE_FUNCS[name];
      if (!fn) {
        if (options.skipUnavailableReferences) return null;
        return `${label}: unknown reference function ${show(name)}`;
      }
      ok = fn(actual, args, response);
      break;
    }
    default:
      return `${label}: unsupported op`;
  }
  return ok ? null : `${label}: expected ${show(expected)}, got ${show(actual)}`;
}

export function matchExpectation(response: unknown, expectation: unknown, options: MatchOptions = {}): string[] {
  const res: Obj = isObj(response) ? response : {};
  const expect: Obj = isObj(expectation) ? expectation : {};
  const mismatches: string[] = [];

  if ("decision_tier" in expect) {
    const want = expect["decision_tier"];
    const got = tierOf(res);
    if (isObj(want)) {
      const floor = String(want["min"] ?? "");
      if (!(floor in TIER_ORDER)) {
        mismatches.push(`decision_tier: invalid min ${show(floor)}`);
      } else if (got === null || !(got in TIER_ORDER) || (TIER_ORDER[got] ?? -1) < (TIER_ORDER[floor] ?? 0)) {
        mismatches.push(`decision_tier: expected >= ${floor}, got ${String(got)}`);
      }
    } else if (got !== want) {
      mismatches.push(`decision_tier: expected ${String(want)}, got ${String(got)}`);
    }
  }

  const codes = new Set(reasonCodesOf(res));
  const include = Array.isArray(expect["reason_codes_include"]) ? expect["reason_codes_include"] : [];
  const missing = include.filter((c) => !codes.has(String(c)));
  if (missing.length > 0) mismatches.push(`reason_codes_include: missing ${show(missing)}`);
  const exclude = Array.isArray(expect["reason_codes_exclude"]) ? expect["reason_codes_exclude"] : [];
  const unexpected = exclude.filter((c) => codes.has(String(c)));
  if (unexpected.length > 0) mismatches.push(`reason_codes_exclude: present ${show(unexpected)}`);

  if ("qr_result" in expect) {
    const gotQr = qrOf(res)["result"];
    if (!deepEqual(gotQr, expect["qr_result"])) {
      mismatches.push(`qr_result: expected ${String(expect["qr_result"])}, got ${String(gotQr)}`);
    }
  }
  if ("qr_flags_include" in expect) {
    const flagsRaw = qrOf(res)["flags"];
    const flags = new Set(Array.isArray(flagsRaw) ? flagsRaw : []);
    const wanted = Array.isArray(expect["qr_flags_include"]) ? expect["qr_flags_include"] : [];
    const absent = wanted.filter((f) => !flags.has(f));
    if (absent.length > 0) mismatches.push(`qr_flags_include: missing ${show(absent)}`);
  }
  if ("stop_codes_include" in expect) {
    const stopsRaw = res["stop_codes"];
    const stops = new Set(Array.isArray(stopsRaw) ? stopsRaw : []);
    const wanted = Array.isArray(expect["stop_codes_include"]) ? expect["stop_codes_include"] : [];
    const absent = wanted.filter((s) => !stops.has(s));
    if (absent.length > 0) mismatches.push(`stop_codes_include: missing ${show(absent)}`);
  }

  if (expect["trace_tools_subset_of_allowlist"]) {
    const trace = Array.isArray(res["trace"]) ? res["trace"] : [];
    const bad = trace
      .filter((s): s is Obj => isObj(s) && s["kind"] === "tool" && !ALLOWED_TOOLS.has(String(s["name"])))
      .map((s) => String(s["name"]));
    if (bad.length > 0) mismatches.push(`trace_tools_subset_of_allowlist: not allowlisted ${show(bad)}`);
  }

  const asserts = Array.isArray(expect["assert"]) ? expect["assert"] : [];
  for (const spec of asserts) {
    const problem = checkAssert(res, isObj(spec) ? spec : {}, options);
    if (problem) mismatches.push(problem);
  }
  return mismatches;
}

/** Placeholder helpers shared with the page: `{{prev.<path>}}` against the previous response. */
const PLACEHOLDER = /\{\{\s*prev\s*[:.]\s*([^{}]+?)\s*\}\}/g;
const FULL_PLACEHOLDER = /^\{\{\s*prev\s*[:.]\s*([^{}]+?)\s*\}\}$/;

export class PlaceholderError extends Error {}

export function resolvePrev(value: unknown, prev: unknown): unknown {
  if (typeof value === "string") {
    const full = FULL_PLACEHOLDER.exec(value);
    if (full?.[1] !== undefined) {
      const hit = getPath(prev, full[1]);
      if (!hit.found) throw new PlaceholderError(`Unresolved placeholder: prev.${full[1]}`);
      return hit.value;
    }
    return value.replace(PLACEHOLDER, (_m, path: string) => {
      const hit = getPath(prev, path);
      if (!hit.found) throw new PlaceholderError(`Unresolved placeholder: prev.${path}`);
      return String(hit.value);
    });
  }
  if (Array.isArray(value)) return value.map((v) => resolvePrev(v, prev));
  if (isObj(value)) return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, resolvePrev(v, prev)]));
  return value;
}
