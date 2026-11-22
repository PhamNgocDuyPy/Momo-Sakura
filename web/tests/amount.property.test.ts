import { describe, expect, it } from "vitest";
import fc from "fast-check";
import vectors from "../../fixtures/amount_vectors.json";
import { formatVnd, parseAmount } from "../src/lib/amount";

// Feature: momo-guardian-web, Property 25: Round trip định dạng số tiền
// **Validates: Requirements 16.9, 19.6, 19.7**
describe("Property 25: amount format round trip", () => {
  it("formatVnd matches the pattern and parseAmount(formatVnd(n)) === n", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: Number.MAX_SAFE_INTEGER }), (n) => {
        const s = formatVnd(n);
        expect(s).toMatch(/^\d{1,3}(\.\d{3})* đ$/);
        expect(parseAmount(s)).toBe(n);
      }),
      { numRuns: 100 },
    );
  });

  it("formatVnd matches every shared vector in fixtures/amount_vectors.json", () => {
    for (const v of vectors.format) {
      expect(formatVnd(v.n)).toBe(v.text);
      expect(parseAmount(v.text)).toBe(v.n);
    }
  });
});
