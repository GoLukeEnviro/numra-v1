"use client";
import { useState } from "react";
import Link from "next/link";
import { api, type PrivateReflectionOut, type SharedReflectionOut, type WorkspaceOverviewOut } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { RelationshipWorkspaceHeader } from "@/components/workspaces/relationship-workspace-header";
import { WorkspaceNavTabs } from "@/components/workspaces/workspace-nav-tabs";
import { loadAll } from "./workspace-roadmaps-content";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

export function WorkspaceReflectionsContent({ workspaceId, overview, reflections }: { workspaceId: string; overview: WorkspaceOverviewOut; reflections: SharedReflectionOut[] }) {
  const { t } = useLocale(); const { user } = useAuth();
  const [items, setItems] = useState(reflections);
  const [sources, setSources] = useState<PrivateReflectionOut[] | null>(null);
  const [selected, setSelected] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const self = overview.dual_profile.find((m) => m.user_id === user?.id);
  const counterpart = overview.dual_profile.find((m) => m.user_id !== user?.id);
  const dissolved = overview.workspace.status === "DISSOLVED";
  const source = sources?.find((r) => r.id === selected);
  async function mutate(action: () => Promise<void>) { if (busy) return; setBusy(true); setError(false); try { await action(); } catch { setError(true); } finally { setBusy(false); } }
  return <div className="animate-rise-in"><RelationshipWorkspaceHeader workspaceId={workspaceId} workspace={overview.workspace} counterpartName={counterpart?.display_name ?? ""} /><WorkspaceNavTabs workspaceId={workspaceId} />
    <header className="mb-8 max-w-reading"><p className="text-xs uppercase tracking-[0.2em] text-bronze">{t("app.reflections.eyebrow")}</p><h1 className="mt-2 font-serif text-4xl text-ivory">{t("app.reflections.heading")}</h1><p className="mt-3 text-sm leading-6 text-muted">{t("app.reflections.intro")}</p></header>
    {dissolved ? <p className="mb-6 rounded-xl border border-white/10 p-5">{t("app.tasks.dissolvedBody")}</p> : <Card className="mb-6 border-gold/20"><CardContent className="space-y-4 p-5">
      {self?.self_person ? sources === null ? <Button loading={busy} onClick={() => mutate(async () => setSources(await loadAll((p) => api.people.privateReflections.list(self.self_person!.id, p))))}>{t("app.reflections.choose")}</Button> : <>
        <label className="block text-sm">{t("app.reflections.source")}<Select value={selected} disabled={busy} onChange={(e) => setSelected(e.target.value)}><option value="">{t("app.reflections.select")}</option>{sources.map((r) => <option key={r.id} value={r.id}>{r.entry_date} — {r.content.slice(0, 60)}</option>)}</Select></label>
        {!sources.length && <p className="text-sm text-muted">{t("app.reflections.noPrivate")}</p>}
        {source && <div className="space-y-4"><h2 className="font-serif text-xl">{t("app.reflections.preview")}</h2><p className="whitespace-pre-wrap break-words rounded-xl bg-surface-2 p-4 text-sm">{source.content}</p><p className="text-sm text-muted">{t("app.reflections.shareNote")} {counterpart?.display_name}</p><Button loading={busy} onClick={() => mutate(async () => { const copy = await api.people.privateReflections.share(source.id, { workspace_id: workspaceId }); setItems((old) => [copy, ...old]); setSelected(""); setSources(null); })}>{t("app.reflections.confirmShare")}</Button></div>}
      </> : <p className="text-sm text-muted">{t("app.reflections.noProfile")}</p>}
      {self?.self_person && <Link className="block text-sm text-gold underline" href={`/people/${self.self_person.id}/workspace`}>{t("app.reflections.privateLink")}</Link>}
    </CardContent></Card>}
    {error && <p role="alert" className="mb-4 text-sm text-danger">{t("app.tasks.actionError")}</p>}
    <div className="space-y-4">{items.map((r) => <Card key={r.id}><CardContent className="space-y-3 p-5"><p className="text-xs text-bronze">{overview.dual_profile.find((m) => m.user_id === r.author_user_id)?.display_name ?? t("app.reflections.author")} · {r.entry_date}</p><p className="whitespace-pre-wrap break-words text-sm leading-7">{r.content}</p>
      {!dissolved && r.author_user_id === user?.id && (confirmDelete === r.id ? <div className="space-y-2"><p className="text-sm text-muted">{t("app.reflections.deleteNote")}</p><Button disabled={busy} onClick={() => mutate(async () => { await api.workspaces.sharedReflections.remove(workspaceId, r.id); setItems((old) => old.filter((x) => x.id !== r.id)); setConfirmDelete(null); })}>{t("app.roadmaps.confirmRemove")}</Button><Button variant="ghost" disabled={busy} onClick={() => setConfirmDelete(null)}>{t("app.tasks.cancel")}</Button></div> : <Button variant="ghost" disabled={busy} onClick={() => setConfirmDelete(r.id)}>{t("app.reflections.remove")}</Button>)}
    </CardContent></Card>)}{!items.length && <Card><CardContent className="p-8 text-center text-muted">{t("app.reflections.empty")}</CardContent></Card>}</div>
  </div>;
}
