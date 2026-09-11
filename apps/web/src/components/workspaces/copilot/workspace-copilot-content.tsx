"use client";

import { useEffect, useRef, useState } from "react";
import { Archive, Lock, Send, Users } from "lucide-react";
import { api, type ChatMessageOut, type ChatThreadOut, type WorkspaceOverviewOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { RelationshipWorkspaceHeader } from "@/components/workspaces/relationship-workspace-header";
import { WorkspaceNavTabs } from "@/components/workspaces/workspace-nav-tabs";
import type { MessageKey } from "@/i18n/catalog";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { isPhaseDisabledError, type PhaseErrorCode } from "@/components/ui/states";

type RelationshipScope = "RELATIONSHIP_SHARED" | "RELATIONSHIP_PRIVATE";
type Props = {
  workspaceId: string;
  overview: WorkspaceOverviewOut;
  onPhaseDisabled?: (code: PhaseErrorCode) => void;
};

const MESSAGE_PAGE_SIZE = 100;

async function loadAllMessages(workspaceId: string, threadId: string) {
  const all: ChatMessageOut[] = [];
  for (let offset = 0; ; offset += MESSAGE_PAGE_SIZE) {
    const page = await api.workspaces.copilot.threads.messages.list(workspaceId, threadId, {
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

export function WorkspaceCopilotContent({ workspaceId, overview, onPhaseDisabled }: Props) {
  const { t } = useLocale();
  const { user } = useAuth();
  const [scope, setScope] = useState<RelationshipScope>("RELATIONSHIP_SHARED");
  const [thread, setThread] = useState<ChatThreadOut | null>(null);
  const [messages, setMessages] = useState<ChatMessageOut[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const dissolved = overview.workspace.status === "DISSOLVED";
  const counterpart = overview.dual_profile.find((member) => member.user_id !== user?.id);

  useEffect(() => {
    const version = ++requestVersion.current;
    setThread(null);
    setMessages([]);
    setError(null);
    setLoading(true);
    async function load() {
      try {
        const threads = await api.workspaces.copilot.threads.list(workspaceId);
        if (version !== requestVersion.current) return;
        let active = threads.find((candidate) => candidate.scope === scope && !candidate.archived_at) ?? null;
        if (!active && !dissolved) active = await api.workspaces.copilot.threads.create(workspaceId, { scope });
        if (version !== requestVersion.current) return;
        setThread(active);
        if (active) {
          const loaded = await loadAllMessages(workspaceId, active.id);
          if (version === requestVersion.current) setMessages(loaded);
        }
      } catch (cause) {
        if (version === requestVersion.current && isPhaseDisabledError(cause)) {
          onPhaseDisabled?.(cause.code);
          return;
        }
        if (version === requestVersion.current) setError(errorMessage(cause, t("app.copilot.loadError")));
      } finally {
        if (version === requestVersion.current) setLoading(false);
      }
    }
    void load();
    return () => { requestVersion.current += 1; };
  }, [dissolved, onPhaseDisabled, scope, t, workspaceId]);

  function selectScope(next: RelationshipScope) {
    if (next === scope) return;
    requestVersion.current += 1;
    setMessages([]);
    setThread(null);
    setContent("");
    setError(null);
    setSending(false);
    setArchiving(false);
    setScope(next);
  }

  async function sendMessage() {
    const trimmed = content.trim();
    if (!trimmed || !thread || sending || dissolved) return;
    setSending(true);
    setError(null);
    const version = requestVersion.current;
    try {
      const pair = await api.workspaces.copilot.threads.messages.post(workspaceId, thread.id, { content: trimmed });
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
    if (!thread || archiving || dissolved) return;
    const version = requestVersion.current;
    const originScope = scope;
    const originThreadId = thread.id;
    setArchiving(true);
    setError(null);
    try {
      await api.workspaces.copilot.threads.archive(workspaceId, originThreadId);
      if (version !== requestVersion.current) return;
      const fresh = await api.workspaces.copilot.threads.create(workspaceId, { scope: originScope });
      if (version !== requestVersion.current) return;
      setThread(fresh);
      const loaded = await loadAllMessages(workspaceId, fresh.id);
      if (version !== requestVersion.current) return;
      setMessages(loaded);
      setContent("");
    } catch (cause) {
      if (version === requestVersion.current) setError(errorMessage(cause, t("app.copilot.archiveError")));
    } finally {
      if (version === requestVersion.current) setArchiving(false);
    }
  }

  return <div className="animate-rise-in">
    <RelationshipWorkspaceHeader workspaceId={workspaceId} workspace={overview.workspace} counterpartName={counterpart?.display_name ?? ""} />
    <WorkspaceNavTabs workspaceId={workspaceId} />
    <header className="mb-6 max-w-reading">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-bronze">{t("app.copilot.eyebrow")}</p>
      <h1 className="mt-2 font-serif text-3xl text-ivory md:text-4xl">{t("app.copilot.workspaceTitle")}</h1>
      <p className="mt-3 text-sm leading-6 text-muted">{t("app.copilot.workspaceIntro")}</p>
    </header>
    <div className="mb-4 grid grid-cols-2 gap-2 rounded-xl border border-white/10 bg-surface p-2" role="group" aria-label={t("app.copilot.modeLabel")}>
      {(["RELATIONSHIP_SHARED", "RELATIONSHIP_PRIVATE"] as const).map((candidate) => <Button key={candidate} variant={scope === candidate ? "primary" : "ghost"} aria-pressed={scope === candidate} onClick={() => selectScope(candidate)}>
        {candidate === "RELATIONSHIP_SHARED" ? <Users className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
        {candidate === "RELATIONSHIP_SHARED" ? t("app.copilot.modeShared") : t("app.copilot.modePrivate")}
      </Button>)}
    </div>
    <p className="mb-5 rounded-lg border border-white/10 bg-surface-2 p-3 text-sm text-muted">
      {scope === "RELATIONSHIP_SHARED" ? t("app.copilot.sharedNotice") : t("app.copilot.privateNotice")}
    </p>
    <Card><CardContent className="space-y-5 p-4 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-serif text-xl text-ivory">{t("app.copilot.conversation")}</h2>
        {!dissolved && thread ? <Button variant="ghost" size="sm" loading={archiving} onClick={archiveThread}><Archive className="h-4 w-4" />{t("app.copilot.archive")}</Button> : null}
      </div>
      <div className="min-h-48 space-y-3" aria-live="polite" aria-busy={loading || undefined}>
        {loading ? <p className="py-8 text-center text-sm text-muted">{t("app.copilot.loading")}</p> : null}
        {!loading && messages.length === 0 ? <p className="py-8 text-center text-sm text-muted">{t("app.copilot.empty")}</p> : null}
        {messages.map((message) => <article key={message.id} className={cn("max-w-[90%] rounded-xl border p-4 text-sm leading-6 sm:max-w-[80%]", message.role === "USER" ? "ml-auto border-gold/20 bg-gold/10 text-ivory" : "border-white/10 bg-surface-2 text-text")}>
          <p>{message.content}</p>
          {message.role === "ASSISTANT" && message.basis_type ? <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-bronze">{t(BASIS_KEYS[message.basis_type] ?? "app.copilot.basisUnknown")}</p> : null}
        </article>)}
      </div>
      {dissolved ? <p className="text-sm text-muted">{t("app.copilot.dissolved")}</p> : <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void sendMessage(); }}>
        <label htmlFor="copilot-message" className="text-sm font-medium text-ivory">{t("app.copilot.messageLabel")}</label>
        <Textarea id="copilot-message" maxLength={8000} value={content} disabled={loading || !thread || sending} onChange={(event) => setContent(event.target.value)} />
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        <div className="flex justify-end"><Button type="submit" disabled={!content.trim() || loading || !thread} loading={sending}><Send className="h-4 w-4" />{sending ? t("app.copilot.sending") : t("app.copilot.send")}</Button></div>
      </form>}
      {dissolved && error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    </CardContent></Card>
  </div>;
}
