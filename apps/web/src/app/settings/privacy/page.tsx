"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { DeleteAccountPanel } from "@/components/settings/delete-account-panel";

function PrivacyContent() {
  return (
    <div className="max-w-2xl">
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">Privacy &amp; data</h1>
        <p className="mt-1 text-sm text-muted">
          What Numra stores, what it never computes, and how to remove all of it.
        </p>
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">What is stored on the server</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-2 pl-5 text-sm text-text">
            <li>
              <strong className="text-ivory">Person profiles</strong> — the birth name, birth
              date, and optional birth time / birth place / current name you enter when creating
              a profile.
            </li>
            <li>
              <strong className="text-ivory">Calculations</strong> — immutable, deterministic
              snapshots of a profile&apos;s canonical numerology result at a given
              <code className="mx-1 rounded bg-black/20 px-1 py-0.5 font-mono text-xs">as_of_date</code>
              , including the full calculation trace and a hash of the inputs and result.
            </li>
            <li>
              <strong className="text-ivory">Relationship comparisons</strong> — the two
              calculation IDs you compared and the resulting per-metric comparison.
            </li>
            <li>
              <strong className="text-ivory">Reports and exports</strong> — the text of any
              long-form report you generate, and any PDF rendered from it (stored as a file
              on the server until you delete it).
            </li>
            <li>
              <strong className="text-ivory">Your account</strong> — email address and session
              credentials, used only to authenticate you.
            </li>
          </ul>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">What this app never computes or stores</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-2 pl-5 text-sm text-text">
            <li>No compatibility percentage is ever calculated for a relationship comparison.</li>
            <li>No diagnosis or medical/psychological language is generated.</li>
            <li>
              Birth time and birth place are stored as metadata only — they never influence a
              Core Number in this version.
            </li>
          </ul>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">Deleting a single profile</CardTitle>
          <CardDescription>
            Any individual profile can be deleted from that profile&apos;s own page, which also
            removes what was calculated from it.
          </CardDescription>
        </CardHeader>
      </Card>

      <DeleteAccountPanel />
    </div>
  );
}

export default function PrivacySettingsPage() {
  return (
    <AppShell>
      <PrivacyContent />
    </AppShell>
  );
}
