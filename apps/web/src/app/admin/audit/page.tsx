"use client";

import { api, type AuditEventOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { formatDateTime } from "@/lib/utils";
import { useState, type FormEvent } from "react";

const PAGE_SIZE = 25;

// Mirrors the backend's `AuditAction` enum. These are internal codes and are shown
// verbatim — an audit trail that renames its own actions is not an audit trail.
const ACTIONS = ["USER_DISABLED", "USER_ENABLED", "USER_SESSIONS_REVOKED", "ADMIN_PROMOTED"] as const;

function shortId(id: string | null): string {
  if (!id) return "—";
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

function metadataText(metadata: AuditEventOut["safe_metadata"]): string | null {
  const entries = Object.entries(metadata ?? {});
  if (entries.length === 0) return null;
  return entries.map(([key, value]) => `${key}=${JSON.stringify(value)}`).join(" · ");
}

/**
 * Everything rendered here comes from the single `/v1/admin/audit` response. The page
 * deliberately never resolves an actor or target id into an account, because that
 * would enrich an operational log with personal data it was designed not to carry.
 */
export default function AdminAuditPage() {
  const { t } = useLocale();
  const [actionDraft, setActionDraft] = useState("");
  const [targetDraft, setTargetDraft] = useState("");
  const [action, setAction] = useState("");
  const [targetUserId, setTargetUserId] = useState("");
  const [page, setPage] = useState(1);

  const auditState = useAsync(
    () =>
      api.admin.audit.list({
        action: action || undefined,
        targetUserId: targetUserId || undefined,
        page,
        pageSize: PAGE_SIZE,
      }),
    [action, targetUserId, page],
  );

  function handleApply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setAction(actionDraft);
    setTargetUserId(targetDraft.trim());
  }

  function handleReset() {
    setActionDraft("");
    setTargetDraft("");
    setAction("");
    setTargetUserId("");
    setPage(1);
  }

  const data = auditState.status === "success" ? auditState.data : null;
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="animate-rise-in">
      <header className="mb-6">
        <h1 className="font-serif text-3xl text-ivory">{t("admin.audit.title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("admin.audit.subtitle")}</p>
      </header>

      <form
        onSubmit={handleApply}
        className="mb-6 grid gap-3 rounded-xl border border-white/10 bg-surface p-4 sm:grid-cols-2"
      >
        <div>
          <Label htmlFor="audit-action">{t("admin.audit.actionLabel")}</Label>
          <Select
            id="audit-action"
            value={actionDraft}
            onChange={(e) => setActionDraft(e.target.value)}
          >
            <option value="">{t("admin.audit.allActions")}</option>
            {ACTIONS.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="audit-target">{t("admin.audit.targetLabel")}</Label>
          <Input
            id="audit-target"
            value={targetDraft}
            placeholder={t("admin.audit.targetPlaceholder")}
            onChange={(e) => setTargetDraft(e.target.value)}
          />
        </div>
        <div className="flex gap-2 sm:col-span-2">
          <Button type="submit" variant="secondary" size="sm">
            {t("admin.audit.apply")}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={handleReset}>
            {t("admin.audit.reset")}
          </Button>
        </div>
      </form>

      {auditState.status === "loading" && <LoadingState label={t("admin.audit.loading")} />}
      {auditState.status === "error" && (
        <ErrorState
          error={auditState.error}
          onRetry={auditState.reload}
          title={t("admin.common.errorTitle")}
        />
      )}

      {data && data.items.length === 0 && (
        <EmptyState title={t("admin.audit.empty")} description={t("admin.audit.emptyHint")} />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="flex flex-col gap-3 md:hidden">
            {data.items.map((event) => (
              <article key={event.id} className="rounded-xl border border-white/10 bg-surface p-4">
                <p className="font-mono text-xs text-gold">{event.action}</p>
                <p className="mt-1 text-xs text-muted">{formatDateTime(event.created_at)}</p>
                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  <dt className="text-muted">{t("admin.audit.colActor")}</dt>
                  <dd className="text-right font-mono text-text" title={event.actor_user_id ?? undefined}>
                    {shortId(event.actor_user_id)}
                  </dd>
                  <dt className="text-muted">{t("admin.audit.colTarget")}</dt>
                  <dd className="text-right font-mono text-text" title={event.target_user_id ?? undefined}>
                    {shortId(event.target_user_id)}
                  </dd>
                </dl>
                <p className="mt-2 break-all text-xs text-muted">
                  {metadataText(event.safe_metadata) ?? t("admin.audit.noMetadata")}
                </p>
              </article>
            ))}
          </div>

          <div className="hidden overflow-x-auto rounded-xl border border-white/10 bg-surface md:block">
            <table className="w-full min-w-[48rem] border-collapse text-left">
              <caption className="sr-only">{t("admin.audit.tableCaption")}</caption>
              <thead>
                <tr className="text-xs uppercase tracking-wide text-muted">
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.audit.colTime")}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.audit.colAction")}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.audit.colActor")}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.audit.colTarget")}</th>
                  <th scope="col" className="px-3 py-3 font-medium">{t("admin.audit.colMetadata")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((event) => (
                  <tr key={event.id} className="border-t border-white/10">
                    <td className="whitespace-nowrap px-3 py-3 text-sm text-muted">
                      {formatDateTime(event.created_at)}
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-gold">{event.action}</td>
                    <td
                      className="px-3 py-3 font-mono text-xs text-text"
                      title={event.actor_user_id ?? undefined}
                    >
                      {shortId(event.actor_user_id)}
                    </td>
                    <td
                      className="px-3 py-3 font-mono text-xs text-text"
                      title={event.target_user_id ?? undefined}
                    >
                      {shortId(event.target_user_id)}
                    </td>
                    <td className="px-3 py-3 text-xs text-muted">
                      {metadataText(event.safe_metadata) ?? t("admin.audit.noMetadata")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <nav
            aria-label={t("admin.pagination.page")}
            className="mt-4 flex flex-wrap items-center justify-between gap-3"
          >
            <p className="text-sm text-muted">
              {data.total} {t("admin.pagination.total")}
            </p>
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                disabled={data.page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                {t("admin.pagination.prev")}
              </Button>
              <span className="text-sm text-text">
                {t("admin.pagination.page")} {data.page} / {pageCount}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={data.page >= pageCount}
                onClick={() => setPage((current) => current + 1)}
              >
                {t("admin.pagination.next")}
              </Button>
            </div>
          </nav>
        </>
      )}
    </div>
  );
}
