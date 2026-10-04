import { describe, expect, it } from "vitest";
import { LEGAL_HOSTING, LEGAL_OPERATOR, missingOperatorFields } from "@/content/legal/operator";

/**
 * Release guard for /impressum and /datenschutz: the provider identity and the
 * hosting provider are operator facts that must never be invented or left as a
 * placeholder. This test is expected to fail until `content/legal/operator.ts`
 * carries the real values; a PR that ships the legal pages stays a draft until it
 * passes.
 */
describe("legal operator facts", () => {
  it("are complete — no required Impressum/Datenschutz field is empty", () => {
    expect(missingOperatorFields()).toEqual([]);
  });

  it("carry a plausible contact e-mail once set", () => {
    if (LEGAL_OPERATOR.email) expect(LEGAL_OPERATOR.email).toMatch(/^[^\s@]+@[^\s@]+\.[^\s@]+$/);
  });

  it("never claim a hosting DPA without a named provider", () => {
    if (LEGAL_HOSTING.dpaConfirmed) expect(LEGAL_HOSTING.provider.trim()).not.toBe("");
  });
});

describe("missingOperatorFields", () => {
  it("lists exactly the empty required fields", () => {
    expect(
      missingOperatorFields(
        { name: "X", street: "", postalCode: "1", city: "Y", country: "DE", email: "", vatId: null },
        { provider: "", location: "EU", dpaConfirmed: false },
      ),
    ).toEqual(["street", "email", "hosting.provider"]);
  });
});
