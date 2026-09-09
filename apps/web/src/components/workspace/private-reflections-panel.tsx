"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { PrivateBadge } from "@/components/workspace/private-badge";
import { api, type PrivateReflectionOut } from "@/api/client";
import { formatIsoDate, todayIsoDate } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import { Plus, Trash2 } from "lucide-react";

export interface PrivateReflectionsPanelProps {
  personId: string;
  managedProfile: boolean;
  initialTotal?: number;
}

/** PrivateReflectionOut CRUD panel -- dated journal entries, no title, entry_date
 *  required. Sorted entry_date desc. Deliberately no share button: api.private
 *  Reflections.share exists in the client but is out of scope for this panel. */
export function PrivateReflectionsPanel({
  personId,
  managedProfile,
  initialTotal,
}: PrivateReflectionsPanelProps) {
  const { t } = useLocale();
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");
  const [reflections, setReflections] = useState<PrivateReflectionOut[]>([]);
  const [error, setError] = useState<unknown>(null);

  const [creating, setCreating] = useState(false);
  const [newDate, setNewDate] = useState(todayIsoDate());
  const [newContent, setNewContent] = useState("");
  const [savingNew, setSavingNew] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDate, setEditDate] = useState("");
  const [editContent, setEditContent] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Always holds the *current* active person, unlike a plain closure over the
  // `personId` prop captured when `load()` was defined -- needed so a stale
  // response from an earlier person is recognized as stale even after several
  // re-renders (UI-consistency guard only, see the check inside `load()` below).
  const activePersonIdRef = useRef(personId);
  activePersonIdRef.current = personId;

  function resetLocalUiState() {
    setCreating(false);
    setNewDate(todayIsoDate());
    setNewContent("");
    setEditingId(null);
    setConfirmDeleteId(null);
  }

  async function load(forPersonId: string) {
    setStatus("loading");
    setError(null);
    setReflections([]);
    try {
      const data = await api.people.privateReflections.list(forPersonId);
      if (forPersonId !== activePersonIdRef.current) return; // stale response, UI-consistency guard only
      const sorted = data
        .filter((entry) => entry.person_id === forPersonId)
        .sort((a, b) => b.entry_date.localeCompare(a.entry_date));
      setReflections(sorted);
      setStatus("success");
    } catch (err) {
      if (forPersonId !== activePersonIdRef.current) return;
      setError(err);
      setStatus("error");
    }
  }

  useEffect(() => {
    resetLocalUiState();
    setReflections([]);
    setStatus("loading");
    void load(personId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personId]);

  async function submitCreate() {
    if (!newContent.trim() || !newDate) return;
    setSavingNew(true);
    try {
      await api.people.privateReflections.create(personId, { content: newContent.trim(), entry_date: newDate });
      resetLocalUiState();
      await load(personId);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setSavingNew(false);
    }
  }

  function startEdit(entry: PrivateReflectionOut) {
    setEditingId(entry.id);
    setEditDate(entry.entry_date);
    setEditContent(entry.content);
    setConfirmDeleteId(null);
  }

  async function submitEdit(reflectionId: string) {
    if (!editContent.trim() || !editDate) return;
    setSavingEdit(true);
    try {
      await api.people.privateReflections.patch(reflectionId, { content: editContent.trim(), entry_date: editDate });
      setEditingId(null);
      await load(personId);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setSavingEdit(false);
    }
  }

  async function confirmDelete(reflectionId: string) {
    setBusyId(reflectionId);
    try {
      await api.people.privateReflections.remove(reflectionId);
      setConfirmDeleteId(null);
      await load(personId);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">{t("app.privateReflections.title")}</CardTitle>
            <PrivateBadge />
          </div>
          {!creating && (
            <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              {t("app.privateReflections.new")}
            </Button>
          )}
        </div>
        <CardDescription>
          {managedProfile ? t("app.privateReflections.managedBody") : t("app.privateReflections.selfBody")}
          {status !== "success" && typeof initialTotal === "number" && (
            <span className="ml-1">
              ({initialTotal} {t("app.workspace.reflectionsSummarySuffix")})
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {creating && (
          <div className="mb-4 flex flex-col gap-2 rounded-lg border border-white/10 bg-surface-2 p-4">
            <label className="text-xs text-muted" htmlFor="new-reflection-date">
              {t("app.privateReflections.dateLabel")}
            </label>
            <Input
              id="new-reflection-date"
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              required
            />
            <label className="text-xs text-muted" htmlFor="new-reflection-content">
              {t("app.privateReflections.contentLabel")}
            </label>
            <Textarea
              id="new-reflection-content"
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              required
            />
            <div className="mt-2 flex gap-2">
              <Button
                size="sm"
                onClick={submitCreate}
                loading={savingNew}
                disabled={!newContent.trim() || !newDate}
              >
                {t("app.privateReflections.save")}
              </Button>
              <Button size="sm" variant="ghost" onClick={resetLocalUiState} disabled={savingNew}>
                {t("app.privateReflections.cancel")}
              </Button>
            </div>
          </div>
        )}

        {status === "loading" && <LoadingState label={t("common.loading")} />}
        {status === "error" && (
          <ErrorState
            error={error}
            title={t("app.privateReflections.loadError")}
            onRetry={() => load(personId)}
          />
        )}
        {status === "success" && reflections.length === 0 && (
          <EmptyState
            title={t("app.privateReflections.empty")}
            action={
              !creating && (
                <Button size="sm" onClick={() => setCreating(true)}>
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("app.privateReflections.emptyCta")}
                </Button>
              )
            }
          />
        )}
        {status === "success" && reflections.length > 0 && (
          <ul className="flex flex-col gap-3">
            {reflections.map((entry) => (
              <li key={entry.id} className="rounded-lg border border-white/10 bg-surface-2 p-4">
                {editingId === entry.id ? (
                  <div className="flex flex-col gap-2">
                    <Input type="date" value={editDate} onChange={(e) => setEditDate(e.target.value)} required />
                    <Textarea value={editContent} onChange={(e) => setEditContent(e.target.value)} required />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => submitEdit(entry.id)}
                        loading={savingEdit}
                        disabled={!editContent.trim() || !editDate}
                      >
                        {t("app.privateReflections.save")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditingId(null)} disabled={savingEdit}>
                        {t("app.privateReflections.cancel")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <button type="button" className="min-w-0 flex-1 text-left" onClick={() => startEdit(entry)}>
                      <p className="text-xs font-medium uppercase tracking-wider text-bronze">
                        {formatIsoDate(entry.entry_date)}
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-text">{entry.content}</p>
                    </button>
                    <div className="flex shrink-0 items-center gap-1">
                      {confirmDeleteId === entry.id ? (
                        <>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => confirmDelete(entry.id)}
                            loading={busyId === entry.id}
                          >
                            {t("app.privateReflections.deleteConfirmButton")}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setConfirmDeleteId(null)}>
                            {t("app.privateReflections.cancel")}
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setConfirmDeleteId(entry.id)}
                          aria-label={t("app.privateReflections.delete")}
                        >
                          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
