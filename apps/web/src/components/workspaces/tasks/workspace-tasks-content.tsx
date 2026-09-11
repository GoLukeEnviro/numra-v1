"use client";

import { useEffect, useMemo, useState } from "react";
import { Archive, Check, Clock3, Lock, Plus, Send, Sparkles, Users } from "lucide-react";
import { api, type TaskType, type WorkspaceOverviewOut, type WorkspaceTaskOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { RelationshipWorkspaceHeader } from "@/components/workspaces/relationship-workspace-header";
import { WorkspaceNavTabs } from "@/components/workspaces/workspace-nav-tabs";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

type Props = { workspaceId: string; overview: WorkspaceOverviewOut; tasks: WorkspaceTaskOut[] };

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(`${value}T00:00:00`));
}

function TaskCard({ task, actorId, dissolved, onChanged }: { task: WorkspaceTaskOut; actorId?: string; dissolved: boolean; onChanged: (task: WorkspaceTaskOut) => void }) {
  const { t, locale } = useLocale();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const incoming = task.status === "PROPOSED" && (task.task_type === "AVENYTH_SUGGESTED" || task.recipient_user_id === actorId);
  const pendingByMe = task.status === "PROPOSED" && task.proposer_user_id === actorId;
  const mutate = async (action: () => Promise<WorkspaceTaskOut>) => {
    setBusy(true); setError(null);
    try { onChanged(await action()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : t("app.tasks.actionError")); }
    finally { setBusy(false); }
  };
  const icon = task.task_type === "FOR_PARTNER_PROPOSED" ? <Send className="h-4 w-4" /> : task.task_type === "AVENYTH_SUGGESTED" ? <Sparkles className="h-4 w-4" /> : <Users className="h-4 w-4" />;
  return <Card className={incoming ? "scroll-mb-28 border-gold/30" : "scroll-mb-28"}>
    <CardHeader>
      <div className="flex items-start justify-between gap-4">
        <div><div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-bronze">{icon}{t(`app.tasks.type.${task.task_type}`)}</div><CardTitle>{task.title}</CardTitle>{task.description ? <CardDescription>{task.description}</CardDescription> : null}</div>
        <span className="rounded-full border border-white/10 bg-surface-2 px-2.5 py-1 text-xs text-muted">{pendingByMe ? t("app.tasks.pending") : t(`app.tasks.status.${task.status}`)}</span>
      </div>
    </CardHeader>
    <CardContent className="space-y-3">
      {task.due_date ? <p className="flex items-center gap-2 text-sm text-muted"><Clock3 className="h-4 w-4" />{t("app.tasks.due")} {formatDate(task.due_date, locale)}</p> : null}
      {!dissolved && incoming ? <div className="flex flex-wrap gap-2"><Button className="scroll-mb-28" size="sm" loading={busy} onClick={() => mutate(() => api.workspaces.tasks.accept(task.workspace_id, task.id))}>{t("app.tasks.accept")}</Button><Button className="scroll-mb-28" size="sm" variant="secondary" disabled={busy} onClick={() => mutate(() => api.workspaces.tasks.decline(task.workspace_id, task.id))}>{t("app.tasks.decline")}</Button></div> : null}
      {!dissolved && task.status === "ACTIVE" ? <div className="flex flex-wrap gap-2"><Button size="sm" loading={busy} onClick={() => mutate(() => api.workspaces.tasks.patch(task.workspace_id, task.id, { status: "COMPLETED" }))}><Check className="h-4 w-4" />{t("app.tasks.complete")}</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => mutate(() => api.workspaces.tasks.patch(task.workspace_id, task.id, { status: "ARCHIVED" }))}><Archive className="h-4 w-4" />{t("app.tasks.archive")}</Button></div> : null}
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    </CardContent>
  </Card>;
}

function CreateTask({ workspaceId, onCreated }: { workspaceId: string; onCreated: (task: WorkspaceTaskOut) => void }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<TaskType>("JOINT_SHARED");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function create() {
    setBusy(true); setError(null);
    try {
      const created = await api.workspaces.tasks.create(workspaceId, { task_type: type, title: title.trim(), description: description.trim() || null, due_date: dueDate || null });
      setTitle(""); setDescription(""); setDueDate(""); setOpen(false); onCreated(created);
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("app.tasks.createError")); }
    finally { setBusy(false); }
  }
  if (!open) return <Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" />{t("app.tasks.create")}</Button>;
  return <Card className="border-gold/20"><CardHeader><CardTitle>{t("app.tasks.createTitle")}</CardTitle><CardDescription>{t("app.tasks.createBody")}</CardDescription></CardHeader><CardContent className="space-y-4">
    <div><Label htmlFor="task-type">{t("app.tasks.typeLabel")}</Label><Select id="task-type" value={type} onChange={(e) => setType(e.target.value as TaskType)}><option value="JOINT_SHARED">{t("app.tasks.type.JOINT_SHARED")}</option><option value="FOR_PARTNER_PROPOSED">{t("app.tasks.type.FOR_PARTNER_PROPOSED")}</option></Select></div>
    <div><Label htmlFor="task-title">{t("app.tasks.titleLabel")}</Label><Input id="task-title" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} /></div>
    <div><Label htmlFor="task-description">{t("app.tasks.descriptionLabel")}</Label><Textarea id="task-description" value={description} onChange={(e) => setDescription(e.target.value)} /></div>
    <div><Label htmlFor="task-due">{t("app.tasks.dueLabel")}</Label><Input id="task-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} /></div>
    {type === "FOR_PARTNER_PROPOSED" ? <p className="rounded-lg border border-white/10 bg-surface-2 p-3 text-sm text-muted">{t("app.tasks.proposalNote")}</p> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <div className="flex gap-2"><Button loading={busy} disabled={!title.trim()} onClick={create}>{t("app.tasks.save")}</Button><Button variant="ghost" disabled={busy} onClick={() => setOpen(false)}>{t("app.tasks.cancel")}</Button></div>
  </CardContent></Card>;
}

export function WorkspaceTasksContent({ workspaceId, overview, tasks }: Props) {
  const { t } = useLocale();
  const { user } = useAuth();
  const counterpart = overview.dual_profile.find((member) => member.user_id !== user?.id);
  const dissolved = overview.workspace.status === "DISSOLVED";
  const [displayTasks, setDisplayTasks] = useState(tasks);
  useEffect(() => setDisplayTasks(tasks), [tasks]);
  const sections = useMemo(() => ({
    current: displayTasks.filter((task) => task.status === "PROPOSED" || task.status === "ACTIVE" || task.status === "ACCEPTED"),
    completed: displayTasks.filter((task) => task.status === "COMPLETED"),
    archived: displayTasks.filter((task) => task.status === "ARCHIVED" || task.status === "DECLINED"),
  }), [displayTasks]);
  const updateTask = (updated: WorkspaceTaskOut) => setDisplayTasks((old) => old.map((task) => task.id === updated.id ? updated : task));
  const addTask = (created: WorkspaceTaskOut) => setDisplayTasks((old) => [created, ...old]);
  return <div className="animate-rise-in">
    <RelationshipWorkspaceHeader workspaceId={workspaceId} workspace={overview.workspace} counterpartName={counterpart?.display_name ?? ""} />
    <WorkspaceNavTabs workspaceId={workspaceId} />
    <header className="mb-8 flex flex-col items-start justify-between gap-5 md:flex-row md:items-end"><div className="max-w-reading"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-bronze">{t("app.tasks.eyebrow")}</p><h1 className="mt-2 font-serif text-3xl text-ivory md:text-4xl">{t("app.tasks.heading")}</h1><p className="mt-3 text-sm leading-6 text-muted">{t("app.tasks.intro")}</p></div>{!dissolved ? <CreateTask workspaceId={workspaceId} onCreated={addTask} /> : null}</header>
    {dissolved ? <Card className="mb-8"><CardContent className="flex gap-3 p-6"><Lock className="h-5 w-5 text-muted" /><div><h2 className="font-serif text-lg text-ivory">{t("app.tasks.dissolvedTitle")}</h2><p className="mt-1 text-sm text-muted">{t("app.tasks.dissolvedBody")}</p></div></CardContent></Card> : null}
    <section className="space-y-4"><h2 className="font-serif text-2xl text-ivory">{t("app.tasks.currentTitle")}</h2>{sections.current.length ? <div className="grid gap-4 md:grid-cols-2">{sections.current.map((task) => <TaskCard key={task.id} task={task} actorId={user?.id} dissolved={dissolved} onChanged={updateTask} />)}</div> : <Card><CardContent className="p-8 text-center text-sm text-muted">{t("app.tasks.empty")}</CardContent></Card>}</section>
    {sections.completed.length ? <section className="mt-10 space-y-4"><h2 className="font-serif text-2xl text-ivory">{t("app.tasks.completedTitle")}</h2><div className="grid gap-4 md:grid-cols-2">{sections.completed.map((task) => <TaskCard key={task.id} task={task} actorId={user?.id} dissolved={dissolved} onChanged={updateTask} />)}</div></section> : null}
    {sections.archived.length ? <section className="mt-10 space-y-4"><h2 className="font-serif text-2xl text-ivory">{t("app.tasks.archivedTitle")}</h2><div className="grid gap-4 md:grid-cols-2">{sections.archived.map((task) => <TaskCard key={task.id} task={task} actorId={user?.id} dissolved={dissolved} onChanged={updateTask} />)}</div></section> : null}
  </div>;
}
