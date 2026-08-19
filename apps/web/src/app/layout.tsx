import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "Numra",
  description: "An auditable numerology platform — deterministic core, transparent traces.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
