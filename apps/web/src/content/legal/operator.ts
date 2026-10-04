/**
 * Single source of truth for the facts on /impressum and /datenschutz.
 *
 * Nothing in here may be invented. The provider identity (name, address, contact)
 * and the hosting provider are facts only the operator can supply; until they are
 * filled in, `missingOperatorFields()` lists them and the guard test in
 * `__tests__/operator.test.ts` fails, so an incomplete legal page can never be
 * merged and deployed. Everything else below is derived from this repository
 * (see the comments on each entry) and must be kept in sync with it.
 */

export interface LegalOperator {
  /** Full name, or company name (with `legalForm` if applicable). */
  name: string;
  legalForm?: string;
  street: string;
  postalCode: string;
  city: string;
  country: string;
  email: string;
  phone?: string;
  /** USt-IdNr.; `null` = none (the line is not rendered). */
  vatId: string | null;
  /** § 18 Abs. 2 MStV — only rendered when set. */
  contentResponsible?: string;
}

export const LEGAL_OPERATOR: LegalOperator = {
  name: "",
  street: "",
  postalCode: "",
  city: "",
  country: "Deutschland",
  email: "",
  vatId: null,
};

export interface HostingFacts {
  /** Name of the server provider (VPS/root server). */
  provider: string;
  location: string;
  /** Set to true only once a data-processing agreement (Art. 28 DSGVO) is confirmed. */
  dpaConfirmed: boolean;
}

export const LEGAL_HOSTING: HostingFacts = {
  provider: "",
  location: "Deutschland bzw. Europäische Union",
  dpaConfirmed: false,
};

/** Last substantive change of the privacy notice. */
export const LEGAL_LAST_UPDATED = "26. September 2026";

type Field = { key: string; label: string; value: string };

/** Fields that must be non-empty before the legal pages may go live. */
export function missingOperatorFields(
  operator: LegalOperator = LEGAL_OPERATOR,
  hosting: HostingFacts = LEGAL_HOSTING,
): string[] {
  const required: Field[] = [
    { key: "name", label: "Name bzw. Firma", value: operator.name },
    { key: "street", label: "Straße und Hausnummer", value: operator.street },
    { key: "postalCode", label: "Postleitzahl", value: operator.postalCode },
    { key: "city", label: "Ort", value: operator.city },
    { key: "country", label: "Land", value: operator.country },
    { key: "email", label: "Kontakt-E-Mail", value: operator.email },
    { key: "hosting.provider", label: "Hosting-Anbieter", value: hosting.provider },
  ];
  return required.filter((field) => field.value.trim() === "").map((field) => field.key);
}

export function operatorDisplayName(operator: LegalOperator = LEGAL_OPERATOR): string {
  return operator.legalForm ? `${operator.name} ${operator.legalForm}` : operator.name;
}
