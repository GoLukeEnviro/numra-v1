"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { PrivateBadge } from "@/components/workspace/private-badge";
import { api, type PrivateNoteOut } from "@/api/client";
import { formatDateTime } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import { Plus, Trash2 } from "lucide-react";

export interface PrivateNotesPanelProps {
  personId: string;
  managedProfile: boolean;
  initialTotal?: number;
}

/** PrivateNoteOut CRUD panel -- same create/edit/delete pattern as
 *  PersonalTasksPanel. Title is optional ("Untitled note" fallback); sorted
 *  updated_at desc. */
export function PrivateNotesPanel({ personId, managedProfile, initialTotal }: PrivateNotesPanelProps) {
  const { t } = useLocale();
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");
  const [notes, setNotes] = useState<PrivateNoteOut[]>([]);
  const [error, setError] = useState<unknown>(null);

  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [savingNew, setSavingNew] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function resetLocalUiState() {
    setCreating(false);
    setNewTitle("");
    setNewContent("");
    setEditingId(null);
    setConfirmDeleteId(null);
  }

  async function load(forPersonId: string) {
    setStatus("loading");
    setError(null);
    setNotes([]);
    try {
      const data = await api.people.privateNotes.list(forPersonId);
      if (forPersonId !== personId) return; // stale response, UI-consistency guard only
      const sorted = data
        .filter((note) => note.person_id === forPersonId)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
      setNotes(sorted);
      setStatus("success");
    } catch (err) {
      if (forPersonId !== personId) return;
      setError(err);
      setStatus("error");
    }
  }

  useEffect(() => {
    resetLocalUiState();
    setNotes([]);
    setStatus("loading");
    void load(personId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personId]);

  async function submitCreate() {
    if (!newContent.trim()) return;
    setSavingNew(true);
    try {
      await api.people.privateNotes.create(personId, {
        title: newTitle.trim() ? newTitle.trim() : null,
        content: newContent.trim(),
      });
      resetLocalUiState();
      await load(personId);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setSavingNew(false);
    }
  }

  function startEdit(note: PrivateNoteOut) {
    setEditingId(note.id);
    setEditTitle(note.title ?? "");
    setEditContent(note.content);
    setConfirmDeleteId(null);
  }

  async function submitEdit(noteId: string) {
    if (!editContent.trim()) return;
    setSavingEdit(true);
    try {
      await api.people.privateNotes.patch(noteId, {
        title: editTitle.trim() ? editTitle.trim() : null,
        content: editContent.trim(),
      });
      setEditingId(null);
      await load(personId);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setSavingEdit(false);
    }
  }

  async function confirmDelete(noteId: string) {
    setBusyId(noteId);
    try {
      await api.people.privateNotes.remove(noteId);
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
            <CardTitle className="text-base">{t("app.privateNotes.title")}</CardTitle>
            <PrivateBadge />
          </div>
          {!creating && (
            <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              {t("app.privateNotes.new")}
            </Button>
          )}
        </div>
        <CardDescription>
          {managedProfile ? t("app.privateNotes.managedBody") : t("app.privateNotes.selfBody")}
          {status !== "success" && typeof initialTotal === "number" && (
            <span className="ml-1">
              ({initialTotal} {t("app.workspace.notesSummarySuffix")})
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {creating && (
          <div className="mb-4 flex flex-col gap-2 rounded-lg border border-white/10 bg-surface-2 p-4">
            <label className="text-xs text-muted" htmlFor="new-note-title">
              {t("app.privateNotes.titleLabel")}
            </label>
            <Input
              id="new-note-title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={t("app.privateNotes.titlePlaceholder")}
            />
            <label className="text-xs text-muted" htmlFor="new-note-content">
              {t("app.privateNotes.contentLabel")}
            </label>
            <Textarea
              id="new-note-content"
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              required
            />
            <div className="mt-2 flex gap-2">
              <Button size="sm" onClick={submitCreate} loading={savingNew} disabled={!newContent.trim()}>
                {t("app.privateNotes.save")}
              </Button>
              <Button size="sm" variant="ghost" onClick={resetLocalUiState} disabled={savingNew}>
                {t("app.privateNotes.cancel")}
              </Button>
            </div>
          </div>
        )}

        {status === "loading" && <LoadingState label={t("common.loading")} />}
        {status === "error" && (
          <ErrorState error={error} title={t("app.privateNotes.loadError")} onRetry={() => load(personId)} />
        )}
        {status === "success" && notes.length === 0 && (
          <EmptyState
            title={t("app.privateNotes.empty")}
            action={
              !creating && (
                <Button size="sm" onClick={() => setCreating(true)}>
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("app.privateNotes.emptyCta")}
                </Button>
              )
            }
          />
        )}
        {status === "success" && notes.length > 0 && (
          <ul className="flex flex-col gap-2">
            {notes.map((note) => (
              <li key={note.id} className="rounded-lg border border-white/10 bg-surface-2 p-3">
                {editingId === note.id ? (
                  <div className="flex flex-col gap-2">
                    <Input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      placeholder={t("app.privateNotes.titlePlaceholder")}
                    />
                    <Textarea value={editContent} onChange={(e) => setEditContent(e.target.value)} required />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => submitEdit(note.id)}
                        loading={savingEdit}
                        disabled={!editContent.trim()}
                      >
                        {t("app.privateNotes.save")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditingId(null)} disabled={savingEdit}>
                        {t("app.privateNotes.cancel")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <button
                      type="button"
                      className="min-w-0 flex-1 text-left"
                      onClick={() => startEdit(note)}
                    >
                      <p className="text-sm font-medium text-text">
                        {note.title || t("app.privateNotes.untitled")}
                      </p>
                      <p className="mt-0.5 line-clamp-2 text-xs text-muted">{note.content}</p>
                      <p className="mt-1 text-[11px] text-muted">{formatDateTime(note.updated_at)}</p>
                    </button>
                    <div className="flex shrink-0 items-center gap-1">
                      {confirmDeleteId === note.id ? (
                        <>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => confirmDelete(note.id)}
                            loading={busyId === note.id}
                          >
                            {t("app.privateNotes.deleteConfirmButton")}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setConfirmDeleteId(null)}>
                            {t("app.privateNotes.cancel")}
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setConfirmDeleteId(note.id)}
                          aria-label={t("app.privateNotes.delete")}
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
