"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { EmptyState, ErrorState, LoadingState, PhaseDisabledState, isPhaseDisabledError } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { api, type ConnectionInvitationOut, type InvitationState, type UserConnectionOut } from "@/api/client";
import type { MessageKey } from "@/i18n/catalog";
import { UserPlus } from "lucide-react";

const INVITATION_STATUS_KEYS: Record<InvitationState, MessageKey> = {
  PENDING: "app.connections.statusPending",
  ACCEPTED: "app.connections.statusAccepted",
  DECLINED: "app.connections.statusDeclined",
  EXPIRED: "app.connections.statusExpired",
  REVOKED: "app.connections.statusRevoked",
};

function ConnectionRow({
  connection,
  workspaceId,
  onDissolved,
}: {
  connection: UserConnectionOut;
  workspaceId: string | undefined;
  onDissolved: (connection: UserConnectionOut) => void;
}) {
  const { t } = useLocale();
  const [confirming, setConfirming] = useState(false);
  const [dissolving, setDissolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDissolve() {
    setDissolving(true);
    setError(null);
    try {
      const dissolved = await api.connections.dissolve(connection.id);
      onDissolved(dissolved);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("app.connections.dissolveError"));
    } finally {
      setDissolving(false);
      setConfirming(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 py-3 last:border-0">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ivory">{connection.counterpart_display_name}</p>
        {error ? <p role="alert" className="mt-1 text-xs text-danger">{error}</p> : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {workspaceId && (
          <LinkButton variant="ghost" size="sm" href={`/workspaces/${workspaceId}/consent`}>
            {t("app.connections.openConsent")}
          </LinkButton>
        )}
        {confirming ? (
          <>
            <span className="text-xs text-muted">{t("app.connections.dissolveConfirm")}</span>
            <Button variant="secondary" size="sm" onClick={handleDissolve} loading={dissolving}>
              {t("app.connections.dissolveConfirmButton")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)} disabled={dissolving}>
              {t("app.connections.dissolveCancel")}
            </Button>
          </>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
            {t("app.connections.dissolveButton")}
          </Button>
        )}
      </div>
    </div>
  );
}

function HistoricalConnectionRow({ connection, workspaceId }: { connection: UserConnectionOut; workspaceId: string | undefined }) {
  const { t } = useLocale();
  return <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 py-3 opacity-75 last:border-0">
    <div className="min-w-0"><p className="truncate text-sm font-medium text-ivory">{connection.counterpart_display_name}</p><Badge variant="neutral">{t("app.connections.statusDissolved")}</Badge></div>
    {workspaceId ? <LinkButton variant="ghost" size="sm" href={`/workspaces/${workspaceId}`}>{t("app.connections.openHistory")}</LinkButton> : null}
  </div>;
}

function InvitationRow({ invitation, onRevoked }: { invitation: ConnectionInvitationOut; onRevoked: (id: string) => void }) {
  const { t } = useLocale();
  const [confirming, setConfirming] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const badgeVariant = invitation.state === "ACCEPTED" ? "success" : "neutral";

  async function handleRevoke() {
    setRevoking(true);
    try {
      await api.connections.revokeInvitation(invitation.id);
      onRevoked(invitation.id);
    } finally {
      setRevoking(false);
      setConfirming(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 py-3 last:border-0">
      <div className="flex items-center gap-2">
        <Badge variant={badgeVariant}>{t(INVITATION_STATUS_KEYS[invitation.state])}</Badge>
        <span className="text-sm text-muted">{invitation.invitee_email ?? invitation.method}</span>
      </div>
      {invitation.state === "PENDING" &&
        (confirming ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">{t("app.connections.revokeConfirm")}</span>
            <Button variant="secondary" size="sm" onClick={handleRevoke} loading={revoking}>
              {t("app.connections.revokeConfirmButton")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)} disabled={revoking}>
              {t("app.connections.revokeCancel")}
            </Button>
          </div>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
            {t("app.connections.revokeButton")}
          </Button>
        ))}
    </div>
  );
}

function ConnectionsContent() {
  const { t } = useLocale();
  const connectionsState = useAsync(() => api.connections.list(), []);
  const invitationsState = useAsync(() => api.connections.listInvitations(), []);
  // Kein connection_id->workspace_id-Link im Connection-Contract -- statt eines
  // Backend-Fix-C wird die Zuordnung client-seitig ueber die vorhandene
  // workspaces.list()/connection_id gemacht (siehe PR-Beschreibung "statt Fix C").
  const workspacesState = useAsync(() => api.workspaces.list(), []);
  const [connectionRows, setConnectionRows] = useState<UserConnectionOut[] | null>(null);
  const [removedInvitations, setRemovedInvitations] = useState<Set<string>>(new Set());

  if (connectionsState.status === "loading" || invitationsState.status === "loading") {
    return <LoadingState label={t("app.connections.loading")} />;
  }

  if (connectionsState.status === "error") {
    if (isPhaseDisabledError(connectionsState.error)) {
      return (
        <PhaseDisabledState
          code={connectionsState.error.code}
          title={t("app.connections.title")}
          description={t("app.connections.body")}
        />
      );
    }
    return <ErrorState error={connectionsState.error} onRetry={connectionsState.reload} title={t("app.connections.loadError")} />;
  }

  if (invitationsState.status === "error") {
    return <ErrorState error={invitationsState.error} onRetry={invitationsState.reload} title={t("app.connections.loadError")} />;
  }

  const allConnections = connectionRows ?? connectionsState.data;
  const connections = allConnections.filter((connection) => connection.status === "ACTIVE");
  const historicalConnections = allConnections.filter((connection) => connection.status === "DISSOLVED");
  const invitations = invitationsState.data.filter((i) => !removedInvitations.has(i.id));
  const workspaceIdByConnectionId = new Map(
    workspacesState.status === "success"
      ? workspacesState.data.map((w) => [w.connection_id, w.id] as const)
      : [],
  );

  return (
    <div className="animate-rise-in flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl text-ivory">{t("app.connections.title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("app.connections.invitedHint")}</p>
        </div>
        <LinkButton href="/connections/invite">
          <UserPlus className="h-4 w-4" aria-hidden="true" />
          {t("app.connections.inviteCta")}
        </LinkButton>
      </header>

      {workspacesState.status === "error" ? (
        isPhaseDisabledError(workspacesState.error) ? (
          <PhaseDisabledState code={workspacesState.error.code} title={t("app.connections.workspaceLoadError")} />
        ) : (
          <ErrorState error={workspacesState.error} onRetry={workspacesState.reload} title={t("app.connections.workspaceLoadError")} />
        )
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("app.connections.activeTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          {connections.length === 0 ? (
            <EmptyState
              title={t("app.connections.emptyActiveTitle")}
              description={t("app.connections.emptyActiveBody")}
              action={
                <LinkButton variant="secondary" href="/connections/invite">
                  {t("app.connections.inviteCta")}
                </LinkButton>
              }
            />
          ) : (
            connections.map((c) => (
              <ConnectionRow
                key={c.id}
                connection={c}
                workspaceId={workspaceIdByConnectionId.get(c.id)}
                onDissolved={(updated) => setConnectionRows((current) => (current ?? connectionsState.data).map((connection) => connection.id === updated.id ? updated : connection))}
              />
            ))
          )}
        </CardContent>
      </Card>

      {historicalConnections.length ? <Card><CardHeader><CardTitle className="text-base">{t("app.connections.historicalTitle")}</CardTitle></CardHeader><CardContent>{historicalConnections.map((connection) => <HistoricalConnectionRow key={connection.id} connection={connection} workspaceId={workspaceIdByConnectionId.get(connection.id)} />)}</CardContent></Card> : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("app.connections.invitationsTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          {invitations.length === 0 ? (
            <EmptyState title={t("app.connections.emptyInvitationsTitle")} />
          ) : (
            invitations.map((i) => (
              <InvitationRow
                key={i.id}
                invitation={i}
                onRevoked={(id) => setRemovedInvitations((prev) => new Set(prev).add(id))}
              />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ConnectionsPage() {
  return (
    <AppShell>
      <ConnectionsContent />
    </AppShell>
  );
}
