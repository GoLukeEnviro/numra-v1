"use client";

import { useState } from "react";
import { api, type RelationshipRoadmapOut, type RoadmapMilestoneOut, type WorkspaceTaskOut, type WorkspaceOverviewOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { RelationshipWorkspaceHeader } from "@/components/workspaces/relationship-workspace-header";
import { WorkspaceNavTabs } from "@/components/workspaces/workspace-nav-tabs";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

export type RoadmapEntry = { roadmap: RelationshipRoadmapOut; milestones: RoadmapMilestoneOut[] };
const ROADMAP_TYPES = [
  { value: "14_DAY", label: "app.roadmaps.14_DAY" },
  { value: "30_DAY", label: "app.roadmaps.30_DAY" },
  { value: "QUARTER", label: "app.roadmaps.QUARTER" },
] as const;
export async function loadAll<T>(page: (params: { limit: number; offset: number }) => Promise<T[]>): Promise<T[]> {
  const result: T[] = [];
  for (let offset = 0; ; offset += 200) {
    const batch = await page({ limit: 200, offset });
    result.push(...batch);
    if (batch.length < 200) return result;
  }
}

function MilestoneEditor({ initial, onSave, onCancel, busy }: { initial?: RoadmapMilestoneOut; onSave: (body: { title: string; description: string | null; target_date: string | null; sequence: number; milestone_type: "MILESTONE" | "REVIEW_POINT" }) => Promise<void>; onCancel: () => void; busy: boolean }) {
  const { t } = useLocale();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [date, setDate] = useState(initial?.target_date ?? "");
  const [sequence, setSequence] = useState(initial?.sequence ?? 0);
  const [type, setType] = useState<"MILESTONE" | "REVIEW_POINT">(initial?.milestone_type ?? "MILESTONE");
  return <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (!busy && title.trim()) void onSave({ title: title.trim(), description: description.trim() || null, target_date: date || null, sequence, milestone_type: type }); }}>
    <label className="block text-sm">{t("app.roadmaps.title")}<Input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
    <label className="block text-sm">{t("app.roadmaps.description")}<Textarea value={description} onChange={(e) => setDescription(e.target.value)} /></label>
    {!initial && <label className="block text-sm">{t("app.roadmaps.kind")}<Select value={type} onChange={(e) => setType(e.target.value as typeof type)}><option value="MILESTONE">{t("app.roadmaps.MILESTONE")}</option><option value="REVIEW_POINT">{t("app.roadmaps.REVIEW_POINT")}</option></Select></label>}
    <div className="grid gap-3 sm:grid-cols-2"><label className="block text-sm">{t("app.roadmaps.date")}<Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label><label className="block text-sm">{t("app.roadmaps.sequence")}<Input type="number" required step={1} value={sequence} onChange={(e) => setSequence(Number(e.target.value))} /></label></div>
    <div className="flex gap-2"><Button type="submit" loading={busy} disabled={!title.trim()}>{t("app.tasks.save")}</Button><Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>{t("app.tasks.cancel")}</Button></div>
  </form>;
}

function RoadmapCard({ entry, workspaceId, dissolved, tasks, updateTask }: { entry: RoadmapEntry; workspaceId: string; dissolved: boolean; tasks: WorkspaceTaskOut[]; updateTask: (task: WorkspaceTaskOut) => void }) {
  const { t } = useLocale();
  const [roadmap, setRoadmap] = useState(entry.roadmap);
  const [milestones, setMilestones] = useState(entry.milestones);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(roadmap.title);
  const [type, setType] = useState(roadmap.roadmap_type);
  const [editor, setEditor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const readonly = dissolved || roadmap.status === "ARCHIVED";
  async function mutate(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(false);
    try { await action(); } catch { setError(true); } finally { setBusy(false); }
  }
  async function saveMilestone(body: Parameters<typeof api.workspaces.roadmaps.milestones.create>[2]) {
    await mutate(async () => {
      if (editor === "new") {
        const created = await api.workspaces.roadmaps.milestones.create(workspaceId, roadmap.id, body);
        setMilestones((old) => [...old, created]);
      } else if (editor) {
        const { milestone_type: _kind, ...patch } = body;
        void _kind;
        const updated = await api.workspaces.roadmaps.milestones.patch(workspaceId, roadmap.id, editor, patch);
        setMilestones((old) => old.map((m) => m.id === updated.id ? updated : m));
      }
      setEditor(null);
    });
  }
  return <Card className="min-w-0 border-gold/20"><CardContent className="space-y-5 p-5 md:p-7">
    <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-bronze"><span>{t(`app.roadmaps.${roadmap.roadmap_type}`)}</span><span>· {t(`app.tasks.status.${roadmap.status}`)}</span>{roadmap.prompt_version && <span>· {t("app.tasks.type.AVENYTH_SUGGESTED")}</span>}</div>
    <h2 className="break-words font-serif text-2xl text-ivory">{roadmap.title}</h2>
    {editing && !readonly ? <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void mutate(async () => { setRoadmap(await api.workspaces.roadmaps.patch(workspaceId, roadmap.id, { title: title.trim(), roadmap_type: type })); setEditing(false); }); }}>
      <label className="block text-sm">{t("app.roadmaps.title")}<Input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      <label className="block text-sm">{t("app.roadmaps.duration")}<Select value={type} onChange={(e) => setType(e.target.value as typeof type)}>{ROADMAP_TYPES.map(({ value, label }) => <option key={value} value={value}>{t(label)}</option>)}</Select></label>
      <Button loading={busy} disabled={!title.trim()} type="submit">{t("app.tasks.save")}</Button><Button type="button" variant="ghost" disabled={busy} onClick={() => setEditing(false)}>{t("app.tasks.cancel")}</Button>
    </form> : !readonly && <div className="flex flex-wrap gap-2">
      <Button variant="secondary" disabled={busy} onClick={() => setEditing(true)}>{t("app.roadmaps.edit")}</Button>
      {roadmap.status === "PROPOSED" && <Button loading={busy} onClick={() => mutate(async () => setRoadmap(await api.workspaces.roadmaps.patch(workspaceId, roadmap.id, { status: "ACCEPTED" })))}>{t("app.tasks.accept")}</Button>}
      <Button variant="ghost" disabled={busy} onClick={() => mutate(async () => setRoadmap(await api.workspaces.roadmaps.patch(workspaceId, roadmap.id, { status: "ARCHIVED" })))}>{t("app.tasks.archive")}</Button>
    </div>}
    <ol className="space-y-4">{[...milestones].sort((a, b) => a.sequence - b.sequence || a.id.localeCompare(b.id)).map((m) => <li key={m.id} className="scroll-mb-28 rounded-xl border border-white/10 bg-surface-2 p-4">
      <p className="text-xs text-bronze">{t(`app.roadmaps.${m.milestone_type}`)} · {t(`app.roadmaps.${m.status}`)}</p>
      <h3 className="mt-1 break-words font-serif text-xl">{m.title}</h3><p className="whitespace-pre-wrap break-words text-sm text-muted">{m.description}</p>{m.target_date && <p className="mt-2 text-sm text-muted">{m.target_date}</p>}
      {tasks.filter((task) => task.roadmap_milestone_id === m.id).map((task) => <p key={task.id} className="mt-2 break-words text-sm">{task.title} · {t(`app.tasks.status.${task.status}`)}</p>)}
      {!readonly && <div className="mt-3 space-y-3"><div className="flex flex-wrap gap-2"><Button size="sm" variant="secondary" disabled={busy} onClick={() => setEditor(m.id)}>{t("app.roadmaps.edit")}</Button>{m.status === "PENDING" && <Button size="sm" disabled={busy} onClick={() => mutate(async () => { const updated = await api.workspaces.roadmaps.milestones.patch(workspaceId, roadmap.id, m.id, { status: "COMPLETED" }); setMilestones((old) => old.map((x) => x.id === m.id ? updated : x)); })}>{t("app.tasks.complete")}</Button>}<Button size="sm" variant="ghost" disabled={busy} onClick={() => setConfirmDelete(m.id)}>{t("app.roadmaps.remove")}</Button></div>
        {confirmDelete === m.id && <div className="space-y-2"><p className="text-sm">{t("app.roadmaps.removeNote")}</p><Button size="sm" disabled={busy} onClick={() => mutate(async () => { await api.workspaces.roadmaps.milestones.remove(workspaceId, roadmap.id, m.id); setMilestones((old) => old.filter((x) => x.id !== m.id)); tasks.filter((x) => x.roadmap_milestone_id === m.id).forEach((x) => updateTask({ ...x, roadmap_milestone_id: null })); setConfirmDelete(null); })}>{t("app.roadmaps.confirmRemove")}</Button><Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>{t("app.tasks.cancel")}</Button></div>}
        {editor === m.id && <MilestoneEditor key={m.id} initial={m} onSave={saveMilestone} onCancel={() => setEditor(null)} busy={busy} />}
        <label className="block text-sm">{t("app.roadmaps.linkTask")}<Select value="" disabled={busy} onChange={(e) => { const id = e.target.value; if (id) void mutate(async () => updateTask(await api.workspaces.tasks.patch(workspaceId, id, { roadmap_milestone_id: m.id }))); }}><option value="">{t("app.roadmaps.chooseTask")}</option>{tasks.filter((task) => !task.roadmap_milestone_id && task.status === "ACTIVE").map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</Select></label>
        {tasks.filter((task) => task.roadmap_milestone_id === m.id).map((task) => <Button className="h-auto max-w-full whitespace-normal break-words text-left" key={task.id} size="sm" variant="ghost" disabled={busy} onClick={() => mutate(async () => updateTask(await api.workspaces.tasks.patch(workspaceId, task.id, { roadmap_milestone_id: null })))}>{t("app.roadmaps.unlink")} — {task.title}</Button>)}
      </div>}
    </li>)}</ol>
    {!milestones.length && <p className="text-sm text-muted">{t("app.roadmaps.noMilestones")}</p>}
    {!readonly && (editor === "new" ? <MilestoneEditor onSave={saveMilestone} onCancel={() => setEditor(null)} busy={busy} /> : <Button variant="secondary" disabled={busy} onClick={() => setEditor("new")}>{t("app.roadmaps.addMilestone")}</Button>)}
    {error && <p role="alert" className="text-sm text-danger">{t("app.tasks.actionError")}</p>}
  </CardContent></Card>;
}

export function WorkspaceRoadmapsContent({ workspaceId, overview, entries, tasks: initialTasks }: { workspaceId: string; overview: WorkspaceOverviewOut; entries: RoadmapEntry[]; tasks: WorkspaceTaskOut[] }) {
  const { t } = useLocale(); const { user } = useAuth();
  const [items, setItems] = useState(entries); const [tasks, setTasks] = useState(initialTasks);
  const [creating, setCreating] = useState(false); const [title, setTitle] = useState("");
  const [type, setType] = useState<RelationshipRoadmapOut["roadmap_type"]>("14_DAY");
  const [busy, setBusy] = useState(false); const [error, setError] = useState(false);
  const dissolved = overview.workspace.status === "DISSOLVED";
  return <div className="animate-rise-in"><RelationshipWorkspaceHeader workspaceId={workspaceId} workspace={overview.workspace} counterpartName={overview.dual_profile.find((m) => m.user_id !== user?.id)?.display_name ?? ""} /><WorkspaceNavTabs workspaceId={workspaceId} />
    <header className="mb-8 max-w-reading"><p className="text-xs uppercase tracking-[0.2em] text-bronze">{t("app.roadmaps.eyebrow")}</p><h1 className="mt-2 font-serif text-4xl text-ivory">{t("app.roadmaps.heading")}</h1><p className="mt-3 text-sm leading-6 text-muted">{t("app.roadmaps.intro")}</p></header>
    {dissolved ? <p className="mb-6 rounded-xl border border-white/10 p-5">{t("app.tasks.dissolvedBody")}</p> : creating ? <Card className="mb-6"><CardContent className="p-5"><form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); if (busy || !title.trim()) return; setBusy(true); setError(false); try { const roadmap = await api.workspaces.roadmaps.create(workspaceId, { title: title.trim(), roadmap_type: type }); setItems((old) => [{ roadmap, milestones: [] }, ...old]); setTitle(""); setCreating(false); } catch { setError(true); } finally { setBusy(false); } }}>
      <label className="block text-sm">{t("app.roadmaps.title")}<Input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} /></label><label className="block text-sm">{t("app.roadmaps.duration")}<Select value={type} onChange={(e) => setType(e.target.value as typeof type)}>{ROADMAP_TYPES.map(({ value, label }) => <option key={value} value={value}>{t(label)}</option>)}</Select></label>
      <Button type="submit" loading={busy} disabled={!title.trim()}>{t("app.tasks.save")}</Button><Button type="button" variant="ghost" disabled={busy} onClick={() => setCreating(false)}>{t("app.tasks.cancel")}</Button>{error && <p role="alert">{t("app.tasks.createError")}</p>}
    </form></CardContent></Card> : <Button className="mb-6" onClick={() => setCreating(true)}>{t("app.roadmaps.create")}</Button>}
    <div className="space-y-6">{items.map((entry) => <RoadmapCard key={entry.roadmap.id} entry={entry} workspaceId={workspaceId} dissolved={dissolved} tasks={tasks} updateTask={(updated) => setTasks((old) => old.map((x) => x.id === updated.id ? updated : x))} />)}{!items.length && <Card><CardContent className="p-8 text-center text-muted">{t("app.roadmaps.empty")}</CardContent></Card>}</div>
  </div>;
}
