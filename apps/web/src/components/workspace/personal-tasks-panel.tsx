"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { PrivateBadge } from "@/components/workspace/private-badge";
import { api, type PersonalTaskOut, type PersonalTaskStatus } from "@/api/client";
import { formatIsoDate } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import { Plus, Trash2, Archive, Undo2 } from "lucide-react";

type Filter = PersonalTaskStatus | "ALL";

export interface PersonalTasksPanelProps {
  personId: string;
  managedProfile: boolean;
  /** Overview count shown before this panel's own list call resolves. */
  initialActiveCount?: number;
}

/**
 * PersonalTaskOut CRUD panel. Establishes the create/edit/delete pattern the
 * private-notes and private-reflections panels mirror. `completed_at` is server-
 * derived (route sets it on a transition into COMPLETED) -- never sent from here.
 */
export function PersonalTasksPanel({
  personId,
  managedProfile,
  initialActiveCount,
}: PersonalTasksPanelProps) {
  const { t } = useLocale();
  const [filter, setFilter] = useState<Filter>("ACTIVE");
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");
  const [tasks, setTasks] = useState<PersonalTaskOut[]>([]);
  const [error, setError] = useState<unknown>(null);

  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newDueDate, setNewDueDate] = useState("");
  const [savingNew, setSavingNew] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editDueDate, setEditDueDate] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Always holds the *current* active person/filter, unlike a plain closure
  // over the props captured when `load()` was defined -- needed so a stale
  // response is recognized as stale even after several re-renders
  // (UI-consistency guard only, see the check inside `load()` below).
  const activeRef = useRef({ personId, filter });
  activeRef.current = { personId, filter };

  function resetLocalUiState() {
    setCreating(false);
    setNewTitle("");
    setNewDescription("");
    setNewDueDate("");
    setEditingId(null);
    setConfirmDeleteId(null);
  }

  async function load(forPersonId: string, forFilter: Filter) {
    setStatus("loading");
    setError(null);
    setTasks([]);
    try {
      const params = forFilter === "ALL" ? {} : { status: forFilter };
      const data = await api.personalTasks.list(forPersonId, params);
      // Defensive UI-consistency guard against a stale response resolving after a
      // newer request started (personId or filter changed in the meantime) --
      // NOT a security boundary. The real ownership check is the backend route.
      if (forPersonId !== activeRef.current.personId || forFilter !== activeRef.current.filter) return;
      setTasks(data.filter((task) => task.person_id === forPersonId));
      setStatus("success");
    } catch (err) {
      if (forPersonId !== activeRef.current.personId || forFilter !== activeRef.current.filter) return;
      setError(err);
      setStatus("error");
    }
  }

  // State isolation (privacy-critical): clear immediately on a personId change,
  // close any open create/edit/delete-confirm UI, then reload for the new person.
  useEffect(() => {
    resetLocalUiState();
    setTasks([]);
    setStatus("loading");
    void load(personId, filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personId, filter]);

  async function submitCreate() {
    if (!newTitle.trim()) return;
    setSavingNew(true);
    try {
      await api.personalTasks.create(personId, {
        title: newTitle.trim(),
        description: newDescription.trim() ? newDescription.trim() : null,
        due_date: newDueDate ? newDueDate : null,
      });
      resetLocalUiState();
      await load(personId, filter);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setSavingNew(false);
    }
  }

  function startEdit(task: PersonalTaskOut) {
    setEditingId(task.id);
    setEditTitle(task.title);
    setEditDescription(task.description ?? "");
    setEditDueDate(task.due_date ?? "");
    setConfirmDeleteId(null);
  }

  async function submitEdit(taskId: string) {
    if (!editTitle.trim()) return;
    setSavingEdit(true);
    try {
      await api.personalTasks.patch(taskId, {
        title: editTitle.trim(),
        description: editDescription.trim() ? editDescription.trim() : null,
        due_date: editDueDate ? editDueDate : null,
      });
      setEditingId(null);
      await load(personId, filter);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setSavingEdit(false);
    }
  }

  async function toggleStatus(task: PersonalTaskOut) {
    setBusyId(task.id);
    try {
      const nextStatus: PersonalTaskStatus = task.status === "ACTIVE" ? "COMPLETED" : "ACTIVE";
      await api.personalTasks.patch(task.id, { status: nextStatus });
      await load(personId, filter);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setBusyId(null);
    }
  }

  async function archiveTask(task: PersonalTaskOut) {
    setBusyId(task.id);
    try {
      await api.personalTasks.patch(task.id, { status: "ARCHIVED" });
      await load(personId, filter);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setBusyId(null);
    }
  }

  async function confirmDelete(taskId: string) {
    setBusyId(taskId);
    try {
      await api.personalTasks.remove(taskId);
      setConfirmDeleteId(null);
      await load(personId, filter);
    } catch (err) {
      setError(err);
      setStatus("error");
    } finally {
      setBusyId(null);
    }
  }

  const filters: Filter[] = ["ACTIVE", "COMPLETED", "ARCHIVED", "ALL"];
  const filterLabel: Record<Filter, string> = {
    ACTIVE: t("app.personalTasks.statusActive"),
    COMPLETED: t("app.personalTasks.statusCompleted"),
    ARCHIVED: t("app.personalTasks.statusArchived"),
    ALL: t("app.personalTasks.filterAll"),
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">{t("app.personalTasks.title")}</CardTitle>
            <PrivateBadge />
          </div>
          {!creating && (
            <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              {t("app.personalTasks.new")}
            </Button>
          )}
        </div>
        <CardDescription>
          {managedProfile ? t("app.personalTasks.managedBody") : t("app.personalTasks.selfBody")}
          {status !== "success" && typeof initialActiveCount === "number" && (
            <span className="ml-1">
              ({initialActiveCount} {t("app.workspace.tasksSummarySuffix")})
            </span>
          )}
        </CardDescription>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {filters.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                filter === f
                  ? "border-gold/50 bg-gold/10 text-gold"
                  : "border-white/10 text-muted hover:text-ivory"
              }`}
            >
              {filterLabel[f]}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {creating && (
          <div className="mb-4 flex flex-col gap-2 rounded-lg border border-white/10 bg-surface-2 p-4">
            <label className="text-xs text-muted" htmlFor="new-task-title">
              {t("app.personalTasks.titleLabel")}
            </label>
            <Input
              id="new-task-title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={t("app.personalTasks.titlePlaceholder")}
              required
            />
            <label className="text-xs text-muted" htmlFor="new-task-description">
              {t("app.personalTasks.descriptionLabel")}
            </label>
            <Textarea
              id="new-task-description"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
            />
            <label className="text-xs text-muted" htmlFor="new-task-due">
              {t("app.personalTasks.dueDateLabel")}
            </label>
            <Input
              id="new-task-due"
              type="date"
              value={newDueDate}
              onChange={(e) => setNewDueDate(e.target.value)}
            />
            <div className="mt-2 flex gap-2">
              <Button size="sm" onClick={submitCreate} loading={savingNew} disabled={!newTitle.trim()}>
                {t("app.personalTasks.save")}
              </Button>
              <Button size="sm" variant="ghost" onClick={resetLocalUiState} disabled={savingNew}>
                {t("app.personalTasks.cancel")}
              </Button>
            </div>
          </div>
        )}

        {status === "loading" && <LoadingState label={t("common.loading")} />}
        {status === "error" && (
          <ErrorState error={error} title={t("app.personalTasks.loadError")} onRetry={() => load(personId, filter)} />
        )}
        {status === "success" && tasks.length === 0 && (
          <EmptyState
            title={t("app.personalTasks.empty")}
            action={
              !creating && (
                <Button size="sm" onClick={() => setCreating(true)}>
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("app.personalTasks.emptyCta")}
                </Button>
              )
            }
          />
        )}
        {status === "success" && tasks.length > 0 && (
          <ul className="flex flex-col gap-2">
            {tasks.map((task) => (
              <li key={task.id} className="rounded-lg border border-white/10 bg-surface-2 p-3">
                {editingId === task.id ? (
                  <div className="flex flex-col gap-2">
                    <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} required />
                    <Textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} />
                    <Input type="date" value={editDueDate} onChange={(e) => setEditDueDate(e.target.value)} />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => submitEdit(task.id)}
                        loading={savingEdit}
                        disabled={!editTitle.trim()}
                      >
                        {t("app.personalTasks.save")}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditingId(null)} disabled={savingEdit}>
                        {t("app.personalTasks.cancel")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <label className="flex flex-1 items-start gap-3">
                      <input
                        type="checkbox"
                        checked={task.status === "COMPLETED"}
                        disabled={task.status === "ARCHIVED" || busyId === task.id}
                        onChange={() => toggleStatus(task)}
                        aria-label={`${t("app.personalTasks.markDone")}: ${task.title}`}
                        className="mt-1 h-4 w-4 rounded border-white/20 bg-surface text-gold accent-gold"
                      />
                      <div className="min-w-0 flex-1 cursor-pointer" onClick={() => startEdit(task)}>
                        <p
                          className={`text-sm text-text ${task.status === "COMPLETED" ? "line-through opacity-60" : ""}`}
                        >
                          {task.title}
                        </p>
                        {task.description && <p className="mt-0.5 text-xs text-muted">{task.description}</p>}
                        {task.due_date && (
                          <p className="mt-0.5 text-xs text-muted">
                            {t("app.personalTasks.dueDateLabel")}: {formatIsoDate(task.due_date)}
                          </p>
                        )}
                      </div>
                    </label>
                    <div className="flex shrink-0 items-center gap-1">
                      {task.status === "COMPLETED" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => archiveTask(task)}
                          disabled={busyId === task.id}
                          aria-label={t("app.personalTasks.archiveAction")}
                        >
                          <Archive className="h-3.5 w-3.5" aria-hidden="true" />
                        </Button>
                      )}
                      {task.status === "ARCHIVED" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => toggleStatus(task)}
                          disabled={busyId === task.id}
                          aria-label={t("app.personalTasks.markActive")}
                        >
                          <Undo2 className="h-3.5 w-3.5" aria-hidden="true" />
                        </Button>
                      )}
                      {confirmDeleteId === task.id ? (
                        <>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => confirmDelete(task.id)}
                            loading={busyId === task.id}
                          >
                            {t("app.personalTasks.deleteConfirmButton")}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setConfirmDeleteId(null)}>
                            {t("app.personalTasks.cancel")}
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setConfirmDeleteId(task.id)}
                          aria-label={t("app.personalTasks.delete")}
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
