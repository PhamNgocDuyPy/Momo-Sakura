import { describe, expect, it } from "vitest";
import { getPath, matchExpectation, resolvePrev } from "../src/lib/expectation";

const verdict = (tier: string, codes: string[] = []) => ({
  verdict: { decision_tier: tier, reason_codes: codes },
});

describe("matchExpectation", () => {
  it("passes on exact tier and included codes", () => {
    expect(
      matchExpectation(verdict("HARD_HOLD", ["RC_A", "RC_B"]), {
        decision_tier: "HARD_HOLD",
        reason_codes_include: ["RC_A"],
      }),
    ).toEqual([]);
  });

  it("reports tier mismatch with actual value", () => {
    expect(matchExpectation(verdict("ALLOW"), { decision_tier: "HARD_HOLD" })).toEqual([
      "decision_tier: expected HARD_HOLD, got ALLOW",
    ]);
  });

  it("supports min tier", () => {
    const want = { decision_tier: { min: "SOFT_FRICTION" } };
    expect(matchExpectation(verdict("HARD_HOLD"), want)).toEqual([]);
    expect(matchExpectation(verdict("SOFT_FRICTION"), want)).toEqual([]);
    expect(matchExpectation(verdict("ALLOW"), want)).toHaveLength(1);
    expect(matchExpectation(verdict("ALLOW"), { decision_tier: { min: "NOPE" } })).toHaveLength(1);
  });

  it("reads tier and codes from a top-level response too", () => {
    expect(
      matchExpectation({ decision_tier: "ALLOW", reason_codes: ["RC_X"] }, { decision_tier: "ALLOW", reason_codes_include: ["RC_X"] }),
    ).toEqual([]);
  });

  it("checks missing and excluded codes", () => {
    const res = verdict("ALLOW", ["RC_A"]);
    expect(matchExpectation(res, { reason_codes_include: ["RC_A", "RC_B"] })).toEqual([
      'reason_codes_include: missing ["RC_B"]',
    ]);
    expect(matchExpectation(res, { reason_codes_exclude: ["RC_A", "RC_C"] })).toEqual([
      'reason_codes_exclude: present ["RC_A"]',
    ]);
  });

  it("checks qr result, flags and stop codes", () => {
    const res = { qr: { result: "BAD_CRC", flags: ["F1"] }, stop_codes: ["S1"] };
    expect(matchExpectation(res, { qr_result: "BAD_CRC", qr_flags_include: ["F1"], stop_codes_include: ["S1"] })).toEqual([]);
    expect(matchExpectation(res, { qr_result: "VALID_VIETQR", qr_flags_include: ["F2"], stop_codes_include: ["S2"] })).toHaveLength(3);
  });

  it("checks trace tool allowlist", () => {
    const ok = { trace: [{ kind: "tool", name: "verify_vietqr_emvco" }, { kind: "llm", name: "x" }] };
    const bad = { trace: [{ kind: "tool", name: "transfer_money" }] };
    expect(matchExpectation(ok, { trace_tools_subset_of_allowlist: true })).toEqual([]);
    expect(matchExpectation(bad, { trace_tools_subset_of_allowlist: true })).toEqual([
      'trace_tools_subset_of_allowlist: not allowlisted ["transfer_money"]',
    ]);
  });

  describe("assert ops", () => {
    const res = { a: { n: 5, s: "hello", l: [1, 2, { k: "v" }], none: null } };
    const check = (op: string, path: string, value?: unknown) =>
      matchExpectation(res, { assert: [{ path, op, value }] });

    it("eq", () => {
      expect(check("eq", "a.n", 5)).toEqual([]);
      expect(check("eq", "a.l.2", { k: "v" })).toEqual([]);
      expect(check("eq", "a.n", 6)).toHaveLength(1);
    });
    it("lt / gt", () => {
      expect(check("lt", "a.n", 6)).toEqual([]);
      expect(check("lt", "a.n", 5)).toHaveLength(1);
      expect(check("gt", "a.n", 4)).toEqual([]);
      expect(check("lt", "a.none", 1)).toHaveLength(1);
      expect(check("lt", "a.s", 1)[0]).toContain("incomparable");
    });
    it("in / contains", () => {
      expect(check("in", "a.n", [1, 5])).toEqual([]);
      expect(check("in", "a.n", [1, 2])).toHaveLength(1);
      expect(check("contains", "a.s", "ell")).toEqual([]);
      expect(check("contains", "a.l", 2)).toEqual([]);
      expect(check("contains", "a.l", 9)).toHaveLength(1);
    });
    it("absent", () => {
      expect(check("absent", "a.missing")).toEqual([]);
      expect(check("absent", "a.none")).toEqual([]);
      expect(check("absent", "a.n")).toHaveLength(1);
    });
    it("path not found and unsupported op", () => {
      expect(check("eq", "a.missing", 1)).toEqual(["assert a.missing eq: path not found"]);
      expect(check("weird", "a.n", 1)).toEqual(["assert a.n weird: unsupported op"]);
    });
    it("matches_reference", () => {
      const ref = (value: unknown) => matchExpectation(res, { assert: [{ path: "a.n", op: "matches_reference", value }] });
      expect(ref({ fn: "equals_arg", args: { expected: 5 } })).toEqual([]);
      expect(ref({ fn: "equals_arg", args: { expected: 6 } })).toHaveLength(1);
      expect(ref("spend_reference")[0]).toContain("unknown reference function");
      expect(
        matchExpectation(res, { assert: [{ path: "a.n", op: "matches_reference", value: "spend_reference" }] }, { skipUnavailableReferences: true }),
      ).toEqual([]);
    });
  });
});

describe("getPath / resolvePrev", () => {
  it("walks objects and list indexes", () => {
    expect(getPath({ a: [{ b: 1 }] }, "a.0.b")).toEqual({ found: true, value: 1 });
    expect(getPath({ a: [] }, "a.0").found).toBe(false);
    expect(getPath({ a: 1 }, "a.b").found).toBe(false);
  });

  it("keeps type for whole-string placeholders and stringifies embedded ones", () => {
    const prev = { prefill: { amount_vnd: 200000, memo: "cơm" } };
    expect(resolvePrev({ amount_vnd: "{{prev.prefill.amount_vnd}}", note: "x {{prev.prefill.memo}}", list: ["{{prev.prefill.memo}}"] }, prev)).toEqual({
      amount_vnd: 200000,
      note: "x cơm",
      list: ["cơm"],
    });
  });

  it("throws for unresolved placeholders", () => {
    expect(() => resolvePrev("{{prev.nope}}", {})).toThrow("Unresolved placeholder: prev.nope");
  });
});
