import type { Metadata, Viewport } from "next";
import { AuthProvider } from "@/lib/auth-context";
import { LocaleProvider } from "@/i18n/context";
import { RegisterServiceWorker } from "@/components/pwa/register-service-worker";
import "./globals.css";

export const metadata: Metadata = {
  title: "Numra",
  description: "An auditable numerology platform — deterministic core, transparent traces.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Numra",
  },
};

export const viewport: Viewport = {
  themeColor: "#0B0B0F",
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
        <RegisterServiceWorker />
      </body>
    </html>
  );
}
