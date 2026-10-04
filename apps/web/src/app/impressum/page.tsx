import { LegalDocument, LegalSection } from "@/components/legal/legal-document";
import { LEGAL_OPERATOR, operatorDisplayName } from "@/content/legal/operator";
import { dePublic } from "@/i18n/messages/de/public";
import { BRAND_NAME } from "@/lib/brand";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: `Impressum · ${BRAND_NAME}`,
  description: `Anbieterkennzeichnung für ${BRAND_NAME} nach § 5 DDG.`,
};

/** § 5 DDG. Every fact comes from `content/legal/operator.ts` — nothing is typed in here. */
export default function ImpressumPage() {
  const operator = LEGAL_OPERATOR;
  return (
    <LegalDocument title="Impressum">
      <LegalSection id="anbieter" title="Angaben gemäß § 5 DDG">
        <address className="not-italic">
          {operatorDisplayName(operator)}
          <br />
          {operator.street}
          <br />
          {operator.postalCode} {operator.city}
          <br />
          {operator.country}
        </address>
      </LegalSection>

      <LegalSection id="kontakt" title="Kontakt">
        <p>
          E-Mail:{" "}
          <a href={`mailto:${operator.email}`} className="text-gold underline-offset-4 hover:underline">
            {operator.email}
          </a>
          {operator.phone && (
            <>
              <br />
              Telefon: {operator.phone}
            </>
          )}
        </p>
      </LegalSection>

      {operator.vatId && (
        <LegalSection id="ust" title="Umsatzsteuer-Identifikationsnummer">
          <p>Umsatzsteuer-Identifikationsnummer gemäß § 27a Umsatzsteuergesetz: {operator.vatId}</p>
        </LegalSection>
      )}

      {operator.contentResponsible && (
        <LegalSection id="redaktion" title="Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV">
          <p>{operator.contentResponsible}, Anschrift wie oben.</p>
        </LegalSection>
      )}

      <LegalSection id="streitbeilegung" title="Verbraucherstreitbeilegung">
        <p>
          Wir sind nicht bereit und nicht verpflichtet, an Streitbeilegungsverfahren vor einer
          Verbraucherschlichtungsstelle teilzunehmen.
        </p>
      </LegalSection>

      <LegalSection id="hinweis" title="Hinweis zum Angebot">
        <p>{dePublic["public.landing.disclaimerBody"]}</p>
        <p>
          Wie wir personenbezogene Daten verarbeiten, beschreibt unsere{" "}
          <Link href="/datenschutz" className="text-gold underline-offset-4 hover:underline">
            Datenschutzerklärung
          </Link>
          .
        </p>
      </LegalSection>
    </LegalDocument>
  );
}
