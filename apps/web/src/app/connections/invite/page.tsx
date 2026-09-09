"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { api, ApiError, type ConnectionInvitationCreatedOut, type InvitationMethod } from "@/api/client";
import { useLocale } from "@/i18n/context";
import { Check, Copy } from "lucide-react";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const METHODS: {
  value: InvitationMethod;
  labelKey: "app.connectionsInvite.methodLinkLabel" | "app.connectionsInvite.methodCodeLabel" | "app.connectionsInvite.methodEmailLabel";
  hintKey: "app.connectionsInvite.methodLinkHint" | "app.connectionsInvite.methodCodeHint" | "app.connectionsInvite.methodEmailHint";
}[] = [
  { value: "LINK", labelKey: "app.connectionsInvite.methodLinkLabel", hintKey: "app.connectionsInvite.methodLinkHint" },
  { value: "CODE", labelKey: "app.connectionsInvite.methodCodeLabel", hintKey: "app.connectionsInvite.methodCodeHint" },
  { value: "EMAIL", labelKey: "app.connectionsInvite.methodEmailLabel", hintKey: "app.connectionsInvite.methodEmailHint" },
];

function MethodChoice({
  method,
  selected,
  onSelect,
}: {
  method: (typeof METHODS)[number];
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useLocale();
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        "flex w-full flex-col gap-1 rounded-lg border p-4 text-left transition-colors",
        selected
          ? "border-gold bg-gold/10"
          : "border-white/10 bg-surface-2 hover:border-gold/40",
      )}
    >
      <span className="text-sm font-medium text-ivory">{t(method.labelKey)}</span>
      <span className="text-xs text-muted">{t(method.hintKey)}</span>
    </button>
  );
}

function CopyField({ label, value }: { label: string; value: string }) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (permissions, insecure context) -- value stays selectable in the input.
    }
  }

  return (
    <div>
      <Label>{label}</Label>
      <div className="flex gap-2">
        <Input readOnly value={value} onFocus={(e) => e.currentTarget.select()} />
        <Button type="button" variant="secondary" onClick={handleCopy}>
          {copied ? (
            <>
              <Check className="h-4 w-4" aria-hidden="true" />
              {t("app.connectionsInvite.copiedFeedback")}
            </>
          ) : (
            <>
              <Copy className="h-4 w-4" aria-hidden="true" />
              {t("app.connectionsInvite.copyButton")}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

function MethodStep({
  onCreated,
}: {
  onCreated: (result: ConnectionInvitationCreatedOut) => void;
}) {
  const { t } = useLocale();
  const [method, setMethod] = useState<InvitationMethod>("LINK");
  const [email, setEmail] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailInvalid = method === "EMAIL" && emailTouched && !EMAIL_PATTERN.test(email.trim());

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (method === "EMAIL") {
      setEmailTouched(true);
      if (!EMAIL_PATTERN.test(email.trim())) return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.connections.invite(
        method === "EMAIL" ? { method, invitee_email: email.trim() } : { method },
      );
      onCreated(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("app.connectionsInvite.submitError"));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 text-sm font-medium text-ivory">
          {t("app.connectionsInvite.methodStepTitle")}
        </legend>
        {METHODS.map((m) => (
          <MethodChoice key={m.value} method={m} selected={method === m.value} onSelect={() => setMethod(m.value)} />
        ))}
      </fieldset>

      {method === "EMAIL" && (
        <div className="mt-4">
          <Label htmlFor="invitee-email">{t("app.connectionsInvite.emailLabel")}</Label>
          <Input
            id="invitee-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={() => setEmailTouched(true)}
            required
          />
          {emailInvalid && (
            <p className="mt-1 text-xs text-danger">{t("app.connectionsInvite.emailInvalid")}</p>
          )}
        </div>
      )}

      {error && (
        <div role="alert" className="mt-4 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text">
          {error}
        </div>
      )}

      <Button type="submit" className="mt-6 w-full" loading={submitting}>
        {t("app.connectionsInvite.continueButton")}
      </Button>
    </form>
  );
}

function ResultStep({ result, onDone }: { result: ConnectionInvitationCreatedOut; onDone: () => void }) {
  const { t } = useLocale();
  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-serif text-lg text-ivory">{t("app.connectionsInvite.createdTitle")}</h2>
      <div role="alert" className="rounded-lg border border-gold/30 bg-gold/10 p-3 text-sm text-ivory">
        {t("app.connectionsInvite.createdWarning")}
      </div>

      <CopyField label={t("app.connectionsInvite.linkLabel")} value={result.redeem_url} />
      {result.method === "CODE" && (
        <CopyField label={t("app.connectionsInvite.codeLabel")} value={result.token} />
      )}

      <Button className="w-full" onClick={onDone}>
        {t("app.connectionsInvite.doneButton")}
      </Button>
    </div>
  );
}

function InviteContent() {
  const { t } = useLocale();
  const router = useRouter();
  const [result, setResult] = useState<ConnectionInvitationCreatedOut | null>(null);

  return (
    <div className="mx-auto max-w-lg">
      <Card>
        <CardHeader>
          <CardTitle>{t("app.connectionsInvite.title")}</CardTitle>
          <CardDescription>
            <Link href="/connections" className="text-gold underline-offset-4 hover:underline">
              {t("app.connections.title")}
            </Link>
          </CardDescription>
        </CardHeader>
        <CardContent>
          {result ? (
            <ResultStep result={result} onDone={() => router.push("/connections")} />
          ) : (
            <MethodStep onCreated={setResult} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ConnectionsInvitePage() {
  return (
    <AppShell>
      <InviteContent />
    </AppShell>
  );
}
