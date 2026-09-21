"use client";

import { useEffect, useRef, useState } from "react";
import { Archive, Send, Sparkles } from "lucide-react";
import { api, type ChatMessageOut, type ChatThreadOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { isPhaseDisabledError, type PhaseErrorCode } from "@/components/ui/states";
import type { MessageKey } from "@/i18n/catalog";
import { useLocale } from "@/i18n/context";
import { cn } from "@/lib/utils";

/**
 * PWA-06 / #123 -- the personal (workspace-free) Copilot conversation.
 *
 * Deliberately a separate component from `WorkspaceCopilotContent`: a personal thread
 * has no workspace, no shared/private mode switch and therefore no relationship
 * context at all (it is grounded on the requester's own profile only). Sharing the
 * component would mean shipping a mode toggle whose second mode does not exist here,
 * and rendering relationship chrome around a surface that must not know about
 * relationships. What IS shared is the message/basis rendering below and the API
 * client group (`api.me.copilot.threads.*`) -- not new design language.
 */

const MESSAGE_PAGE_SIZE = 100;

async function loadAllMessages(threadId: string) {
  const all: ChatMessageOut[] = [];
  for (let offset = 0; ; offset += MESSAGE_PAGE_SIZE) {
    const page = await api.me.copilot.threads.messages.list(threadId, {
      limit: MESSAGE_PAGE_SIZE,
      offset,
    });
    all.push(...page);
    if (page.length < MESSAGE_PAGE_SIZE) return all;
  }
}

const BASIS_KEYS: Record<string, MessageKey> = {
  NUMEROLOGY_MODEL: "app.copilot.basisNumerology",
  OBSERVED_WORKSPACE_DATA: "app.copilot.basisObserved",
  MIXED: "app.copilot.basisMixed",
  INSUFFICIENT_EVIDENCE: "app.copilot.basisInsufficient",
};

function errorMessage(cause: unknown, fallback: string) {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}

export function PersonalCopilotContent({
  onPhaseDisabled,
}: {
  onPhaseDisabled?: (code: PhaseErrorCode) => void;
}) {
  const { t } = useLocale();
  const [thread, setThread] = useState<ChatThreadOut | null>(null);
  const [messages, setMessages] = useState<ChatMessageOut[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);

  useEffect(() => {
    const version = ++requestVersion.current;
    setError(null);
    setLoading(true);
    async function load() {
      try {
        // Get-or-create is idempotent server-side: the API returns the caller's one
        // non-archived personal thread, creating it on first visit.
        const threads = await api.me.copilot.threads.list();
        if (version !== requestVersion.current) return;
        const active = threads.find((candidate) => !candidate.archived_at) ?? null;
        const resolved = active ?? (await api.me.copilot.threads.create());
        if (version !== requestVersion.current) return;
        setThread(resolved);
        const loaded = await loadAllMessages(resolved.id);
        if (version === requestVersion.current) setMessages(loaded);
      } catch (cause) {
        if (version !== requestVersion.current) return;
        if (isPhaseDisabledError(cause)) {
          onPhaseDisabled?.(cause.code);
          return;
        }
        setError(errorMessage(cause, t("app.copilot.loadError")));
      } finally {
        if (version === requestVersion.current) setLoading(false);
      }
    }
    void load();
    return () => {
      requestVersion.current += 1;
    };
  }, [onPhaseDisabled, t]);

  async function sendMessage() {
    const trimmed = content.trim();
    if (!trimmed || !thread || sending) return;
    setSending(true);
    setError(null);
    const version = requestVersion.current;
    try {
      const pair = await api.me.copilot.threads.messages.post(thread.id, { content: trimmed });
      if (version !== requestVersion.current) return;
      setMessages((current) => [...current, pair.user_message, pair.assistant_message]);
      setContent("");
    } catch (cause) {
      if (version === requestVersion.current) setError(errorMessage(cause, t("app.copilot.sendError")));
    } finally {
      if (version === requestVersion.current) setSending(false);
    }
  }

  async function archiveThread() {
    if (!thread || archiving) return;
    setArchiving(true);
    setSending(false);
    setError(null);
    try {
      await api.me.copilot.threads.archive(thread.id);
      // Invalidate anything still in flight against the thread we just left, so a
      // late reply cannot be appended to the fresh (empty) thread's transcript.
      const version = ++requestVersion.current;
      const fresh = await api.me.copilot.threads.create();
      if (version !== requestVersion.current) return;
      setThread(fresh);
      const loaded = await loadAllMessages(fresh.id);
      if (version !== requestVersion.current) return;
      setMessages(loaded);
      setContent("");
    } catch (cause) {
      if (isPhaseDisabledError(cause)) {
        onPhaseDisabled?.(cause.code);
        return;
      }
      setError(errorMessage(cause, t("app.copilot.archiveError")));
    } finally {
      setArchiving(false);
    }
  }

  return (
    <section aria-labelledby="personal-copilot-heading" className="mb-10">
      <header className="mb-4 max-w-reading">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-bronze">{t("app.copilot.personalEyebrow")}</p>
        <h2 id="personal-copilot-heading" className="mt-2 font-serif text-2xl text-ivory">{t("app.copilot.personalTitle")}</h2>
        <p className="mt-3 text-sm leading-6 text-muted">{t("app.copilot.personalIntro")}</p>
      </header>
      <p className="mb-5 rounded-lg border border-white/10 bg-surface-2 p-3 text-sm text-muted">{t("app.copilot.personalNotice")}</p>
      <Card><CardContent className="space-y-5 p-4 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-serif text-xl text-ivory">{t("app.copilot.conversation")}</h3>
          {thread ? <Button variant="ghost" size="sm" loading={archiving} onClick={archiveThread}><Archive className="h-4 w-4" />{t("app.copilot.archive")}</Button> : null}
        </div>
        <div className="min-h-48 space-y-3" aria-live="polite" aria-busy={loading || undefined}>
          {loading ? <p className="py-8 text-center text-sm text-muted">{t("app.copilot.loading")}</p> : null}
          {!loading && messages.length === 0 ? <p className="py-8 text-center text-sm text-muted">{t("app.copilot.empty")}</p> : null}
          {messages.map((message) => <article key={message.id} className={cn("max-w-[90%] rounded-xl border p-4 text-sm leading-6 sm:max-w-[80%]", message.role === "USER" ? "ml-auto border-gold/20 bg-gold/10 text-ivory" : "border-white/10 bg-surface-2 text-text")}>
            {message.role === "ASSISTANT" && message.status === "FAILED" ? <>
              {message.content ? <p>{message.content}</p> : null}
              <p role="alert" className="text-sm text-danger">{t("app.copilot.failedTurn")}</p>
            </> : <p>{message.content}</p>}
            {message.role === "ASSISTANT" && message.status === "FAILED" ? <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-bronze">{t("app.copilot.failedTurnBasis")}</p> : null}
            {message.role === "ASSISTANT" && message.status !== "FAILED" && message.basis_type ? <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-bronze">{t(BASIS_KEYS[message.basis_type] ?? "app.copilot.basisUnknown")}</p> : null}
          </article>)}
        </div>
        <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void sendMessage(); }}>
          <label htmlFor="personal-copilot-message" className="text-sm font-medium text-ivory">{t("app.copilot.messageLabel")}</label>
          <Textarea id="personal-copilot-message" maxLength={8000} value={content} disabled={loading || !thread || sending} onChange={(event) => setContent(event.target.value)} />
          {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
          <div className="flex justify-end"><Button type="submit" disabled={!content.trim() || loading || !thread} loading={sending}><Send className="h-4 w-4" />{sending ? t("app.copilot.sending") : t("app.copilot.send")}</Button></div>
        </form>
      </CardContent></Card>
    </section>
  );
}

/** Icon re-export so the page keeps a single personal-copilot entry point. */
export const PersonalCopilotIcon = Sparkles;
