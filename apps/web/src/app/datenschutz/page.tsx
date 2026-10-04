import { LegalDocument, LegalList, LegalSection } from "@/components/legal/legal-document";
import {
  LEGAL_HOSTING,
  LEGAL_LAST_UPDATED,
  LEGAL_OPERATOR,
  operatorDisplayName,
} from "@/content/legal/operator";
import { BRAND_NAME } from "@/lib/brand";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: `Datenschutz · ${BRAND_NAME}`,
  description: `Datenschutzerklärung für ${BRAND_NAME} nach Art. 13 DSGVO.`,
};

const LINK = "text-gold underline-offset-4 hover:underline";

/**
 * Art. 13 DSGVO. Operator facts come from `content/legal/operator.ts`; every
 * statement about processing is derived from this repository and names its source
 * in a comment, so a change in the code has an obvious place to be mirrored here.
 */
export default function DatenschutzPage() {
  const operator = LEGAL_OPERATOR;
  const hosting = LEGAL_HOSTING;
  return (
    <LegalDocument title="Datenschutzerklärung" lastUpdated={LEGAL_LAST_UPDATED}>
      <LegalSection id="verantwortlicher" title="1. Verantwortlicher">
        <address className="not-italic">
          {operatorDisplayName(operator)}
          <br />
          {operator.street}
          <br />
          {operator.postalCode} {operator.city}
          <br />
          {operator.country}
          <br />
          E-Mail:{" "}
          <a href={`mailto:${operator.email}`} className={LINK}>
            {operator.email}
          </a>
        </address>
        <p>
          Eine Pflicht zur Benennung eines Datenschutzbeauftragten besteht nicht. Für alle Fragen zum
          Datenschutz und zur Ausübung deiner Rechte erreichst du uns unter der oben genannten
          E-Mail-Adresse.
        </p>
      </LegalSection>

      <LegalSection id="grundsaetze" title="2. Grundsätze">
        <LegalList>
          <li>
            {BRAND_NAME} verarbeitet nur die Daten, die du selbst eingibst, und nur, um dir die
            Funktionen des Dienstes bereitzustellen.
          </li>
          <li>Es gibt keine Werbung, keinen Verkauf von Daten und keine Reichweitenmessung oder Tracking.</li>
          <li>
            Alle Zahlen berechnet eine deterministische Engine auf unserem eigenen Server. Eine KI
            formuliert lediglich Texte zu bereits berechneten Werten (siehe Abschnitt 7).
          </li>
          <li>Du kannst deine Daten jederzeit exportieren und dein Konto vollständig löschen.</li>
        </LegalList>
      </LegalSection>

      <LegalSection id="hosting" title="3. Aufruf der Website, Hosting und Cloudflare">
        <p>
          Beim Aufruf der Website werden technisch notwendige Verbindungsdaten verarbeitet: IP-Adresse,
          Zeitpunkt, aufgerufene Adresse, übertragene Datenmenge sowie Browser- und
          Betriebssystemangaben. Sie werden benötigt, um die Seite auszuliefern, die Verbindung zu
          sichern und Missbrauch abzuwehren. Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO; unser
          berechtigtes Interesse liegt im sicheren und stabilen Betrieb.
        </p>
        <p>
          Die Anwendung läuft auf einem Server
          {hosting.provider ? <> der {hosting.provider}</> : null} mit Standort in {hosting.location}.
          {hosting.dpaConfirmed && (
            <> Mit dem Hosting-Anbieter besteht ein Vertrag über Auftragsverarbeitung nach Art. 28 DSGVO.</>
          )}
        </p>
        <p>
          Der Website ist das Netzwerk von Cloudflare, Inc. (USA) vorgeschaltet. Cloudflare leitet die
          Anfragen weiter, stellt die verschlüsselte Verbindung (TLS) bereit und schützt vor Angriffen.
          Dabei verarbeitet Cloudflare die oben genannten Verbindungsdaten. Cloudflare ist unter dem
          EU-U.S. Data Privacy Framework zertifiziert, auf dessen Grundlage (Angemessenheitsbeschluss
          der EU-Kommission, Art. 45 DSGVO) die Übermittlung in die USA erfolgt.
        </p>
        <p>
          Unsere Anwendung speichert IP-Adressen nicht in der Datenbank. Zum Schutz vor automatisierten
          Anmelde- und Registrierungsversuchen wird aus der IP-Adresse eine nicht umkehrbare,
          pseudonyme Kennung gebildet und nur für ein kurzes Zeitfenster gezählt.
        </p>
      </LegalSection>

      <LegalSection id="konto" title="4. Konto, Anmeldung und Cookies">
        <p>
          Für ein Konto verarbeiten wir deine E-Mail-Adresse und dein Passwort. Das Passwort wird nie im
          Klartext gespeichert, sondern ausschließlich als Argon2id-Hash. Rechtsgrundlage ist die
          Erfüllung des Nutzungsvertrags (Art. 6 Abs. 1 lit. b DSGVO).
        </p>
        <p>Wir setzen ausschließlich technisch notwendige Cookies ein:</p>
        <LegalList>
          <li>
            ein Sitzungs-Cookie, das dich nach der Anmeldung angemeldet hält. Es enthält eine
            zufällige Kennung; auf dem Server wird nur deren Hash gespeichert. Eine Sitzung ist
            höchstens 14 Tage gültig und endet mit der Abmeldung.
          </li>
          <li>ein Cookie zum Schutz vor Cross-Site-Request-Forgery (CSRF).</li>
        </LegalList>
        <p>
          Diese Cookies sind für den von dir ausdrücklich gewünschten Dienst unbedingt erforderlich
          (§ 25 Abs. 2 Nr. 2 TDDDG); eine Einwilligung ist dafür nicht erforderlich.
        </p>
      </LegalSection>

      <LegalSection id="inhalte" title="5. Profile, Berechnungen und Berichte">
        <p>Wenn du den Dienst nutzt, speichern wir die Daten, die du eingibst oder erzeugst:</p>
        <LegalList>
          <li>
            Personenprofile: Geburtsname, Vornamen, Geburtsdatum sowie optional weitere Namen,
            Geburtszeit und Geburtsort.
          </li>
          <li>
            Berechnungen: unveränderliche Ergebnisse zu einem Stichtag mit vollständiger Herleitung
            und Prüf-Hash.
          </li>
          <li>Vergleiche zwischen zwei Profilen, Berichte und die daraus erzeugten PDF-Dateien.</li>
        </LegalList>
        <p>
          Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO. PDF-Dateien werden auf unserem eigenen Server
          erzeugt; dafür werden keine Dritten eingesetzt.
        </p>
        <p>
          Legst du ein Profil für eine andere Person an, etwa für eine Partnerin oder einen Partner,
          verarbeiten wir auch deren Angaben. Bitte lege ein solches Profil nur an, wenn du dazu
          berechtigt bist, und informiere die betroffene Person. Profile, die du für andere anlegst,
          bleiben privat in deinem Konto. Rechtsgrundlage ist unser berechtigtes Interesse, dir diese
          Funktion bereitzustellen (Art. 6 Abs. 1 lit. f DSGVO).
        </p>
        <p>
          Soweit gemeinsame Bereiche für zwei Konten freigeschaltet sind, werden Inhalte nur mit der
          anderen Person geteilt, wenn du das ausdrücklich freigibst; die Freigabe kannst du jederzeit
          widerrufen.
        </p>
      </LegalSection>

      <LegalSection id="email" title="6. E-Mail-Versand">
        <p>
          Für E-Mails zur Bestätigung deiner Adresse und zum Zurücksetzen des Passworts sowie –
          soweit freigeschaltet – für Einladungen nutzen wir den Versanddienst Resend (USA). Dabei
          werden deine E-Mail-Adresse und der Inhalt der jeweiligen Nachricht übermittelt.
          Bestätigungslinks sind 24 Stunden gültig, Links zum Zurücksetzen des Passworts 60 Minuten.
        </p>
        <p>
          Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO. Eine Übermittlung in die USA erfolgt nur auf
          Grundlage der Art. 44 ff. DSGVO, insbesondere des EU-U.S. Data Privacy Framework oder der
          EU-Standardvertragsklauseln.
        </p>
      </LegalSection>

      <LegalSection id="ki" title="7. KI-gestützte Formulierung von Texten">
        <p>
          Berichte und Antworten des Copilots werden sprachlich von einem KI-Modell formuliert, das
          über den Dienst Ollama Cloud (Ollama, Inc., USA) bereitgestellt wird. Die Zahlen selbst
          berechnet ausschließlich unsere Engine; die KI erklärt nur, was bereits berechnet wurde.
        </p>
        <p>An den KI-Dienst übermittelt werden:</p>
        <LegalList>
          <li>
            berechnete Kennzahlen (zum Beispiel „Life Path 22/4“), Zyklen und abgeleitete
            Analyseergebnisse,
          </li>
          <li>Deutungstexte aus unserer eigenen Wissensbasis,</li>
          <li>
            im Copilot zusätzlich deine aktuelle Nachricht, frühere Nachrichten desselben Verlaufs
            und – in gemeinsamen Bereichen – Reflexionen, die ausdrücklich geteilt wurden.
          </li>
        </LegalList>
        <p>
          Namen, Geburtsdaten und E-Mail-Adressen werden nicht an den KI-Dienst übermittelt. Was du
          selbst in den Copilot schreibst, wird jedoch unverändert weitergegeben – bitte gib dort
          keine Angaben ein, die du nicht teilen möchtest.
        </p>
        <p>
          Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO, da die Textformulierung Teil der von dir
          angeforderten Funktion ist. Eine Übermittlung in die USA erfolgt nur auf Grundlage der
          Art. 44 ff. DSGVO, insbesondere des EU-U.S. Data Privacy Framework oder der
          EU-Standardvertragsklauseln.
        </p>
      </LegalSection>

      <LegalSection id="backups" title="8. Datensicherung">
        <p>
          Zum Schutz vor Datenverlust sichern wir die Datenbank täglich. Diese Sicherungen bewahren
          wir 14 Tage auf. Zusätzlich wird eine verschlüsselte Sicherung außerhalb des Servers beim
          Speicheranbieter Backblaze, Inc. (USA) abgelegt. Die Verschlüsselung erfolgt vorher auf
          unserem Server; Backblaze erhält keinen Schlüssel und kann die Inhalte nicht lesen. Diese
          Sicherungen werden nach einem festen Schema gelöscht und höchstens sechs Monate
          aufbewahrt.
        </p>
        <p>Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO (Datensicherheit und Wiederherstellbarkeit).</p>
      </LegalSection>

      <LegalSection id="browser" title="9. Speicherung im Browser">
        <p>
          In deinem Browser speichern wir lokal einige Einstellungen, zum Beispiel die gewählte
          Sprache und Anzeigeoptionen. Diese Daten verlassen dein Gerät nicht. Der Service Worker der
          Web-App speichert ausschließlich statische Programmdateien, keine Seiten und keine
          persönlichen Inhalte. Rechtsgrundlage ist § 25 Abs. 2 Nr. 2 TDDDG.
        </p>
      </LegalSection>

      <LegalSection id="speicherdauer" title="10. Speicherdauer und Löschung">
        <p>
          Wir speichern deine Daten, solange dein Konto besteht. Einzelne Profile kannst du jederzeit
          löschen; dabei wird auch alles entfernt, was daraus berechnet wurde. Löschst du dein Konto,
          werden alle zugehörigen Daten aus der Datenbank entfernt. In den Sicherungen (Abschnitt 8)
          verbleiben sie, bis diese turnusgemäß gelöscht werden, und werden in dieser Zeit nicht
          anderweitig verwendet.
        </p>
        <p>
          Export und Löschung findest du nach der Anmeldung unter{" "}
          <Link href="/settings/privacy" className={LINK}>
            Einstellungen → Datenschutz &amp; Daten
          </Link>
          .
        </p>
      </LegalSection>

      <LegalSection id="rechte" title="11. Deine Rechte">
        <p>Du hast nach der DSGVO das Recht auf:</p>
        <LegalList>
          <li>Auskunft über deine gespeicherten Daten (Art. 15),</li>
          <li>Berichtigung unrichtiger Daten (Art. 16),</li>
          <li>Löschung (Art. 17) und Einschränkung der Verarbeitung (Art. 18),</li>
          <li>Datenübertragbarkeit (Art. 20) – der Export liefert deine Daten als JSON-Datei,</li>
          <li>
            Widerspruch gegen Verarbeitungen, die auf Art. 6 Abs. 1 lit. f DSGVO beruhen, aus Gründen,
            die sich aus deiner besonderen Situation ergeben (Art. 21).
          </li>
        </LegalList>
        <p>
          Außerdem kannst du dich bei einer Datenschutz-Aufsichtsbehörde beschweren (Art. 77 DSGVO),
          insbesondere in dem Bundesland oder Mitgliedstaat deines Aufenthalts.
        </p>
        <p>
          Eine automatisierte Entscheidung im Sinne von Art. 22 DSGVO findet nicht statt. Die
          Berechnungen sind symbolische Deutungen und haben keine rechtliche oder ähnlich erhebliche
          Wirkung.
        </p>
      </LegalSection>

      <LegalSection id="pflicht" title="12. Pflicht zur Bereitstellung">
        <p>
          Die Bereitstellung deiner Daten ist weder gesetzlich noch vertraglich vorgeschrieben. Ohne
          E-Mail-Adresse und Passwort kann jedoch kein Konto angelegt werden, und ohne Geburtsname
          und Geburtsdatum kann keine Berechnung erfolgen.
        </p>
      </LegalSection>
    </LegalDocument>
  );
}
