import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth-context";
import { LocaleProvider } from "@/i18n/context";
import "./globals.css";

export const metadata: Metadata = {
  title: "Numra",
  description: "An auditable numerology platform — deterministic core, transparent traces.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // German is Numra's default UI language (V1.5 Epic G); LocaleProvider updates
  // this to "en" client-side if the visitor previously chose English.
  return (
    <html lang="de" data-theme="dark">
      <body>
        <LocaleProvider>
          <AuthProvider>{children}</AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
