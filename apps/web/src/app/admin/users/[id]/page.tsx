"use client";

import { ApiError, api, type AdminUserOut } from "@/api/client";
import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { RoleBadge, StatusBadge } from "@/components/admin/user-badges";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/ui/states";
import type { MessageKey } from "@/i18n/catalog";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { useAsync } from "@/lib/use-async";
import { formatDateTime } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type ReactNode } from "react";

type ActionId = "disable" | "enable" | "revoke";

const ACTIONS: Record<
  ActionId,
  { titleKey: MessageKey; bodyKey: MessageKey; successKey: MessageKey; confirmKey: MessageKey }
> = {
  disable: {
    titleKey: "admin.userDetail.disableConfirmTitle",
    bodyKey: "admin.userDetail.disableConfirmBody",
    successKey: "admin.userDetail.disableSuccess",
    confirmKey: "admin.userDetail.disable",
  },
  enable: {
    titleKey: "admin.userDetail.enableConfirmTitle",
    bodyKey: "admin.userDetail.enableConfirmBody",
    successKey: "admin.userDetail.enableSuccess",
    confirmKey: "admin.userDetail.enable",
  },
  revoke: {
    titleKey: "admin.userDetail.revokeConfirmTitle",
    bodyKey: "admin.userDetail.revokeConfirmBody",
    successKey: "admin.userDetail.revokeSuccess",
    confirmKey: "admin.userDetail.revoke",
  },
};

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-white/10 px-4 py-3 first:border-t-0">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="break-all text-sm text-ivory">{children}</dd>
    </div>
  );
}

function UserDetail({ user, onChanged }: { user: AdminUserOut; onChanged: () => void }) {
  const { t } = useLocale();
  const { user: currentUser } = useAuth();
  const [pending, setPending] = useState<ActionId | null>(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // The backend refuses an admin disabling their own account with a 403; showing the
  // button as plainly unavailable saves the round trip and explains why.
  const isSelf = currentUser?.id === user.id;

  async function runAction(action: ActionId) {
    setBusy(true);
    setFeedback(null);
    setActionError(null);
    try {
      if (action === "disable") await api.admin.users.disable(user.id);
      if (action === "enable") await api.admin.users.enable(user.id);
      if (action === "revoke") await api.admin.users.revokeSessions(user.id);
      setFeedback(t(ACTIONS[action].successKey));
      onChanged();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : t("admin.common.errorTitle"));
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  return (
    <div className="animate-rise-in">
      <Link
        href="/admin/users"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-gold"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {t("admin.userDetail.back")}
      </Link>

      <header className="mb-6">
        <p className="text-sm text-muted">{t("admin.userDetail.title")}</p>
        <h1 className="break-all font-serif text-2xl text-ivory sm:text-3xl">{user.email}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <RoleBadge role={user.role} />
          <StatusBadge isActive={user.is_active} />
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="account-data" className="rounded-xl border border-white/10 bg-surface">
          <h2 id="account-data" className="border-b border-white/10 p-4 font-serif text-lg text-ivory">
            {t("admin.userDetail.metadataTitle")}
          </h2>
          <dl>
            <Row label={t("admin.userDetail.colId")}>
              <span className="font-mono text-xs">{user.id}</span>
            </Row>
            <Row label={t("admin.users.colEmail")}>{user.email}</Row>
            <Row label={t("admin.users.colRole")}>
              <span className="font-mono text-xs">{user.role}</span>
            </Row>
            <Row label={t("admin.users.colStatus")}>
              {user.is_active ? t("admin.users.statusActive") : t("admin.users.statusDisabled")}
            </Row>
            <Row label={t("admin.users.colRegistered")}>{formatDateTime(user.created_at)}</Row>
            <Row label={t("admin.users.colLastLogin")}>
              {user.last_login_at ? formatDateTime(user.last_login_at) : t("admin.common.never")}
            </Row>
            <Row label={t("admin.users.colSessions")}>{user.active_session_count}</Row>
          </dl>
        </section>

        <section aria-labelledby="account-usage" className="rounded-xl border border-white/10 bg-surface">
          <h2 id="account-usage" className="border-b border-white/10 p-4 font-serif text-lg text-ivory">
            {t("admin.userDetail.usageTitle")}
          </h2>
          <dl>
            <Row label={t("admin.users.colPeople")}>{user.people_count}</Row>
            <Row label={t("admin.users.colCalculations")}>{user.calculation_count}</Row>
            <Row label={t("admin.users.colReports")}>{user.report_count}</Row>
            <Row label={t("admin.users.colRelationships")}>{user.relationship_count}</Row>
          </dl>
        </section>
      </div>

      <section aria-labelledby="account-actions" className="mt-4 rounded-xl border border-white/10 bg-surface p-4">
        <h2 id="account-actions" className="font-serif text-lg text-ivory">
          {t("admin.userDetail.actionsTitle")}
        </h2>

        {feedback && (
          <p role="status" className="mt-3 rounded-lg border border-success/40 px-3 py-2 text-sm text-success">
            {feedback}
          </p>
        )}
        {actionError && (
          <p role="alert" className="mt-3 rounded-lg border border-danger/30 bg-danger-surface px-3 py-2 text-sm text-text">
            {actionError}
          </p>
        )}

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          {user.is_active ? (
            <Button variant="danger" disabled={isSelf} onClick={() => setPending("disable")}>
              {t("admin.userDetail.disable")}
            </Button>
          ) : (
            <Button variant="primary" onClick={() => setPending("enable")}>
              {t("admin.userDetail.enable")}
            </Button>
          )}
          <Button variant="secondary" onClick={() => setPending("revoke")}>
            {t("admin.userDetail.revoke")}
          </Button>
        </div>
        {isSelf && user.is_active && (
          <p className="mt-3 text-xs text-muted">{t("admin.userDetail.selfLockHint")}</p>
        )}
      </section>

      <ConfirmDialog
        open={pending !== null}
        title={pending ? t(ACTIONS[pending].titleKey) : ""}
        description={pending ? t(ACTIONS[pending].bodyKey) : ""}
        confirmLabel={pending ? t(ACTIONS[pending].confirmKey) : undefined}
        danger={pending === "disable" || pending === "revoke"}
        busy={busy}
        onConfirm={() => pending && void runAction(pending)}
        onCancel={() => setPending(null)}
      />
    </div>
  );
}

export default function AdminUserDetailPage() {
  const params = useParams<{ id: string }>();
  const userId = params?.id ?? "";
  const { t } = useLocale();
  const userState = useAsync(() => api.admin.users.get(userId), [userId]);

  if (userState.status === "loading") {
    return <LoadingState label={t("admin.userDetail.loading")} />;
  }
  if (userState.status === "error") {
    return (
      <ErrorState
        error={userState.error}
        onRetry={userState.reload}
        title={t("admin.common.errorTitle")}
      />
    );
  }

  return <UserDetail user={userState.data} onChanged={userState.reload} />;
}
