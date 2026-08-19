"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { useAuth } from "@/lib/auth-context";
import { ShieldCheck } from "lucide-react";

function SettingsContent() {
  const { user } = useAuth();

  return (
    <div>
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">Settings</h1>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Account</CardTitle>
            <CardDescription>{user?.email ?? "—"}</CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <div className="mb-1 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-gold" aria-hidden="true" />
              <CardTitle className="text-base">Privacy &amp; data</CardTitle>
            </div>
            <CardDescription>What Numra stores about you, and how to remove it.</CardDescription>
          </CardHeader>
          <CardContent>
            <LinkButton href="/settings/privacy" variant="secondary" size="sm">
              View privacy settings
            </LinkButton>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <AppShell>
      <SettingsContent />
    </AppShell>
  );
}
