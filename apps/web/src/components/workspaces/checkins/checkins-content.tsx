"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, Clock3, History, Lock, Plus, RefreshCw, Settings2 } from "lucide-react";
import { api, ApiError, NetworkError, type CheckinDimensionOut, type CheckinOut, type CheckinSummaryOut, type CheckinTemplateOut, type WorkspaceOverviewOut } from "@/api/client";
import { RelationshipWorkspaceHeader } from "@/components/workspaces/relationship-workspace-header";
import { WorkspaceNavTabs } from "@/components/workspaces/workspace-nav-tabs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

type Props = {
  workspaceId: string;
  overview: WorkspaceOverviewOut;
  current: CheckinOut | null;
  history: CheckinSummaryOut[];
  template: CheckinTemplateOut | null;
  onReload: () => void;
};

type StoredAttempt = { key: string; roundId?: string };
const memoryAttempts = new Map<string, StoredAttempt>();
type SubmissionResponse = { dimension_id: string; value: number };
const memorySubmissionPayloads = new Map<string, SubmissionResponse[]>();
const uncertainSubmissions = new Set<string>();

function attemptKey(workspaceId: string, operation: "start" | "submit", actorId: string) {
  return `avenyth:checkin-attempt:v1:${actorId}:${workspaceId}:${operation}`;
}

function readAttempt(workspaceId: string, operation: "start" | "submit", actorId: string): StoredAttempt | null {
  const storageKey = attemptKey(workspaceId, operation, actorId);
  try {
    const raw = sessionStorage.getItem(storageKey);
    if (raw) return JSON.parse(raw) as StoredAttempt;
  } catch { /* use the in-memory fallback */ }
  return memoryAttempts.get(storageKey) ?? null;
}

function getAttempt(workspaceId: string, operation: "start" | "submit", actorId: string, details: Omit<StoredAttempt, "key"> = {}) {
  const stored = readAttempt(workspaceId, operation, actorId);
  if (stored && stored.roundId === details.roundId) return stored;
  const next = { key: crypto.randomUUID(), ...details };
  memoryAttempts.set(attemptKey(workspaceId, operation, actorId), next);
  try { sessionStorage.setItem(attemptKey(workspaceId, operation, actorId), JSON.stringify(next)); } catch { /* the in-memory fallback preserves this page's retry */ }
  return next;
}

function clearAttempt(workspaceId: string, operation: "start" | "submit", actorId: string) {
  const storageKey = attemptKey(workspaceId, operation, actorId);
  memoryAttempts.delete(storageKey);
  if (operation === "submit") {
    memorySubmissionPayloads.delete(storageKey);
    uncertainSubmissions.delete(storageKey);
  }
  try { sessionStorage.removeItem(storageKey); } catch { /* storage can be unavailable */ }
}

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value));
}

function provenance(origin: CheckinOut["snapshot_origin"], t: ReturnType<typeof useLocale>["t"]) {
  if (origin === "MIGRATION_CURRENT") return t("app.checkins.originMigration");
  if (origin === "LEGACY_MISSING") return t("app.checkins.originMissing");
  return t("app.checkins.originRoundStart");
}

function directionLabel(direction: string, t: ReturnType<typeof useLocale>["t"]) {
  if (direction === "CONVERGING") return t("app.checkins.directionConverging");
  if (direction === "DIVERGING") return t("app.checkins.directionDiverging");
  if (direction === "STABLE") return t("app.checkins.directionStable");
  if (direction === "NO_PRIOR_DATA") return t("app.checkins.directionNoPrior");
  return direction;
}

function ResultView({ round }: { round: CheckinOut }) {
  const { t } = useLocale();
  const labels = new Map(round.dimensions.map((d) => [d.semantic_key, d.label]));
  const results = Object.entries(round.analysis?.result ?? {});
  return (
    <section className="space-y-4" aria-labelledby="checkin-result-title">
      <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-bronze">{t("app.checkins.resultEyebrow")}</p><h2 id="checkin-result-title" className="mt-1 font-serif text-2xl text-ivory">{t("app.checkins.resultTitle")}</h2></div>
      <div className="grid gap-4 md:grid-cols-2">
        {results.map(([key, result]) => (
          <Card key={key} className="overflow-hidden">
            <CardHeader><CardTitle>{labels.get(key) ?? key}</CardTitle><CardDescription>{result.sufficient_evidence ? t("app.checkins.evidenceEnough") : t("app.checkins.evidenceBuilding")}</CardDescription></CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="block text-xs uppercase tracking-wide text-muted">{t("app.checkins.gap")}</span><strong className="text-xl text-ivory">{result.absolute_gap}</strong></div>
              <div><span className="block text-xs uppercase tracking-wide text-muted">{t("app.checkins.direction")}</span><strong className="text-ivory">{directionLabel(result.direction, t)}</strong></div>
              <div><span className="block text-xs uppercase tracking-wide text-muted">{t("app.checkins.trend")}</span><strong className="text-ivory">{result.rolling_trend}</strong></div>
              <div><span className="block text-xs uppercase tracking-wide text-muted">{t("app.checkins.sample")}</span><strong className="text-ivory">{result.sample_size}</strong></div>
              <div className="col-span-2"><span className="block text-xs uppercase tracking-wide text-muted">{t("app.checkins.historicalDelta")}</span><strong className="text-ivory">{result.historical_delta ?? t("app.checkins.notAvailable")}</strong></div>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="rounded-lg border border-white/10 bg-surface-2 p-3 text-xs text-muted">{provenance(round.snapshot_origin, t)} · {t("app.checkins.privacyNote")}</p>
    </section>
  );
}

function MyResponses({ round }: { round: CheckinOut }) {
  const { t } = useLocale();
  const labels = new Map(round.dimensions.map((dimension) => [dimension.semantic_key, dimension.label]));
  if (!round.my_responses.length) return null;
  return <Card><CardHeader><CardTitle>{t("app.checkins.myResponses")}</CardTitle><CardDescription>{t("app.checkins.myResponsesBody")}</CardDescription></CardHeader><CardContent className="space-y-2">{round.my_responses.map((response) => <div key={response.dimension_id} className="flex items-center justify-between gap-4 rounded-lg bg-surface-2 p-3 text-sm"><span className="text-text">{labels.get(response.semantic_key) ?? response.semantic_key}</span><strong className="text-ivory">{response.value}</strong></div>)}</CardContent></Card>;
}

function AnswerForm({ workspaceId, round, onReload }: { workspaceId: string; round: CheckinOut; onReload: () => void }) {
  const { t } = useLocale();
  const { user } = useAuth();
  const actorId = user?.id ?? "anonymous";
  const submissionKey = `${attemptKey(workspaceId, "submit", actorId)}:${round.id}`;
  const restoredPayload = memorySubmissionPayloads.get(submissionKey);
  const [values, setValues] = useState<Record<string, number>>(() => Object.fromEntries((restoredPayload ?? []).map((response) => [response.dimension_id, response.value])));
  const [pending, setPending] = useState(false);
  const [uncertain, setUncertain] = useState(() => uncertainSubmissions.has(submissionKey));
  const [error, setError] = useState<string | null>(null);
  const complete = round.dimensions.length > 0 && round.dimensions.every((d) => Number.isInteger(values[d.dimension_id]));
  async function submit() {
    if (!complete) return;
    const responses = memorySubmissionPayloads.get(submissionKey) ?? round.dimensions.map((d) => ({ dimension_id: d.dimension_id, value: values[d.dimension_id]! }));
    memorySubmissionPayloads.set(submissionKey, responses);
    const attempt = getAttempt(workspaceId, "submit", actorId, { roundId: round.id });
    setPending(true); setError(null);
    try {
      await api.workspaces.checkins.submit(workspaceId, { round_id: round.id, responses }, attempt.key);
      clearAttempt(workspaceId, "submit", actorId); memorySubmissionPayloads.delete(submissionKey); uncertainSubmissions.delete(submissionKey); onReload();
    } catch (cause) {
      if (cause instanceof NetworkError) { uncertainSubmissions.add(submissionKey); setUncertain(true); setError(t("app.checkins.uncertainSubmit")); }
      else if (cause instanceof ApiError && cause.code === "CHECKIN_IDEMPOTENCY_CONFLICT") { uncertainSubmissions.add(submissionKey); setUncertain(true); setError(t("app.checkins.idempotencyConflict")); }
      else { clearAttempt(workspaceId, "submit", actorId); memorySubmissionPayloads.delete(submissionKey); uncertainSubmissions.delete(submissionKey); setError(cause instanceof Error ? cause.message : t("app.checkins.submitError")); }
    } finally { setPending(false); }
  }
  return (
    <Card className="border-gold/20 bg-[radial-gradient(circle_at_top_right,rgba(200,169,107,0.08),transparent_38%),#13131A]">
      <CardHeader><CardTitle>{t("app.checkins.questionsTitle")}</CardTitle><CardDescription>{t("app.checkins.questionsBody")}</CardDescription></CardHeader>
      <CardContent className="space-y-7">
        {round.dimensions.map((dimension) => (
          <fieldset key={dimension.dimension_id} className="space-y-3">
            <legend className="font-serif text-lg text-ivory">{dimension.label}</legend>
            {dimension.description ? <p className="text-sm text-muted">{dimension.description}</p> : null}
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={dimension.label}>
              {Array.from({ length: dimension.scale_max - dimension.scale_min + 1 }, (_, i) => i + dimension.scale_min).map((value) => (
                <button key={value} type="button" role="radio" disabled={pending || uncertain} aria-checked={values[dimension.dimension_id] === value} onClick={() => setValues((old) => ({ ...old, [dimension.dimension_id]: value }))} className={`h-11 min-w-11 rounded-full border px-3 text-sm transition disabled:opacity-50 ${values[dimension.dimension_id] === value ? "border-gold bg-gold text-background" : "border-white/15 bg-surface-2 text-text hover:border-gold/60"}`}>{value}</button>
              ))}
            </div>
          </fieldset>
        ))}
        {error ? <p role="alert" className="rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-danger">{error}</p> : null}
        <div className="flex flex-wrap gap-2"><Button onClick={submit} disabled={!complete} loading={pending}>{uncertain ? t("app.checkins.retrySubmit") : t("app.checkins.submit")}</Button>{uncertain ? <Button variant="secondary" onClick={onReload}>{t("app.checkins.refresh")}</Button> : null}</div>
      </CardContent>
    </Card>
  );
}

function DimensionEditor({ workspaceId, dimension, locked, onReload, onError }: { workspaceId: string; dimension: CheckinDimensionOut; locked: boolean; onReload: () => void; onError: (message: string) => void }) {
  const { t } = useLocale();
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(dimension.label);
  const [description, setDescription] = useState(dimension.description ?? "");
  async function update(body: { active?: boolean; label?: string; description?: string | null }) {
    try { await api.workspaces.checkinDimensions.update(workspaceId, dimension.id, body); setEditing(false); onReload(); }
    catch (cause) { onError(cause instanceof Error ? cause.message : t("app.checkins.configError")); }
  }
  if (editing) return <div className="space-y-3 rounded-lg border border-gold/20 p-4"><Label htmlFor={`label-${dimension.id}`}>{t("app.checkins.label")}</Label><Input id={`label-${dimension.id}`} value={label} onChange={(event) => setLabel(event.target.value)} /><Label htmlFor={`description-${dimension.id}`}>{t("app.checkins.description")}</Label><Textarea id={`description-${dimension.id}`} value={description} onChange={(event) => setDescription(event.target.value)} /><div className="flex gap-2"><Button size="sm" disabled={!label.trim()} onClick={() => update({ label: label.trim(), description: description.trim() })}>{t("app.checkins.save")}</Button><Button size="sm" variant="ghost" onClick={() => setEditing(false)}>{t("app.checkins.cancel")}</Button></div></div>;
  return <div className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 p-3"><div><p className={dimension.active ? "text-text" : "text-muted line-through"}>{dimension.label}</p><p className="font-mono text-xs text-muted">{dimension.semantic_key} · {dimension.scale_min}–{dimension.scale_max}</p></div><div className="flex gap-1"><Button size="sm" variant="ghost" disabled={locked} onClick={() => setEditing(true)}>{t("app.checkins.edit")}</Button><Button size="sm" variant="ghost" disabled={locked} onClick={() => update({ active: !dimension.active })}>{dimension.active ? t("app.checkins.deactivate") : t("app.checkins.reactivate")}</Button></div></div>;
}

function TemplateEditor({ workspaceId, template, locked, onReload }: { workspaceId: string; template: CheckinTemplateOut; locked: boolean; onReload: () => void }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [semanticKey, setSemanticKey] = useState("");
  const [intimate, setIntimate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function create() {
    setError(null); try {
      await api.workspaces.checkinDimensions.create(workspaceId, { semantic_key: semanticKey, label, description: null, dimension_class: intimate ? "INTIMATE" : null, scale_min: 1, scale_max: 10, sort_order: template.dimensions.length });
      setLabel(""); setSemanticKey(""); setOpen(false); onReload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("app.checkins.configError")); }
  }
  return (
    <Card><CardHeader><div className="flex items-start justify-between gap-4"><div><CardTitle>{t("app.checkins.configTitle")}</CardTitle><CardDescription>{locked ? t("app.checkins.configLocked") : t("app.checkins.configBody")}</CardDescription></div><Settings2 className="h-5 w-5 text-bronze" /></div></CardHeader>
      <CardContent className="space-y-3">
        {template.dimensions.map((dimension) => <DimensionEditor key={dimension.id} workspaceId={workspaceId} dimension={dimension} locked={locked} onReload={onReload} onError={setError} />)}
        {!locked && (open ? <div className="space-y-3 rounded-lg border border-white/10 p-4"><Label htmlFor="dimension-label">{t("app.checkins.label")}</Label><Input id="dimension-label" value={label} onChange={(e) => setLabel(e.target.value)} /><Label htmlFor="dimension-key">{t("app.checkins.semanticKey")}</Label><Input id="dimension-key" value={semanticKey} onChange={(e) => setSemanticKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))} /><label className="flex items-center gap-2 text-sm text-text"><input type="checkbox" checked={intimate} onChange={(e) => setIntimate(e.target.checked)} />{t("app.checkins.intimate")}</label><div className="flex gap-2"><Button onClick={create} disabled={!label.trim() || !semanticKey.trim()}>{t("app.checkins.create")}</Button><Button variant="ghost" onClick={() => setOpen(false)}>{t("app.checkins.cancel")}</Button></div></div> : <Button variant="secondary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" />{t("app.checkins.addDimension")}</Button>)}
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      </CardContent></Card>
  );
}

export function CheckinsContent({ workspaceId, overview, current, history, template, onReload }: Props) {
  const { t, locale } = useLocale();
  const { user } = useAuth();
  const [starting, setStarting] = useState(false);
  const [confirmingStart, setConfirmingStart] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [selectedRound, setSelectedRound] = useState<CheckinOut | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const counterpart = overview.dual_profile.find((member) => member.user_id !== user?.id);
  const dissolved = overview.workspace.status === "DISSOLVED";
  const submitted = (current?.my_responses.length ?? 0) > 0;
  const displayRound = selectedRound ?? current;
  const actorId = user?.id ?? "anonymous";
  useEffect(() => {
    if (!submitted) return;
    clearAttempt(workspaceId, "submit", actorId);
    for (const key of memorySubmissionPayloads.keys()) {
      if (key.startsWith(`${attemptKey(workspaceId, "submit", actorId)}:`)) {
        memorySubmissionPayloads.delete(key);
        uncertainSubmissions.delete(key);
      }
    }
  }, [actorId, submitted, workspaceId]);
  useEffect(() => {
    if (!submitted || current?.status === "ANALYZED") return;
    const refresh = () => { if (document.visibilityState === "visible") onReload(); };
    window.addEventListener("focus", refresh); document.addEventListener("visibilitychange", refresh);
    return () => { window.removeEventListener("focus", refresh); document.removeEventListener("visibilitychange", refresh); };
  }, [current?.status, onReload, submitted]);
  const sortedHistory = useMemo(() => [...history].sort((a, b) => b.cycle_started_at.localeCompare(a.cycle_started_at)), [history]);
  async function start() {
    const attempt = getAttempt(workspaceId, "start", actorId); setStarting(true); setStartError(null);
    try { await api.workspaces.checkins.startRound(workspaceId, attempt.key); clearAttempt(workspaceId, "start", actorId); onReload(); }
    catch (cause) { setStartError(cause instanceof NetworkError ? t("app.checkins.uncertainStart") : cause instanceof Error ? cause.message : t("app.checkins.startError")); }
    finally { setStarting(false); }
  }
  return <div className="animate-rise-in">
    <RelationshipWorkspaceHeader workspaceId={workspaceId} workspace={overview.workspace} counterpartName={counterpart?.display_name ?? ""} />
    <WorkspaceNavTabs workspaceId={workspaceId} />
    <header className="mb-8 max-w-reading"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-bronze">{t("app.checkins.eyebrow")}</p><h1 className="mt-2 font-serif text-3xl text-ivory md:text-4xl">{t("app.checkins.title")}</h1><p className="mt-3 text-sm leading-6 text-muted">{t("app.checkins.intro")}</p></header>
    <div className="space-y-8">
      {dissolved ? <Card><CardContent className="flex gap-3 p-6"><Lock className="h-5 w-5 text-muted" /><div><h2 className="font-serif text-lg text-ivory">{t("app.checkins.dissolvedTitle")}</h2><p className="mt-1 text-sm text-muted">{t("app.checkins.dissolvedBody")}</p></div></CardContent></Card> : null}
      {!current && !dissolved ? <Card className="border-gold/20"><CardContent className="flex flex-col items-start gap-4 p-8"><Clock3 className="h-7 w-7 text-gold" /><div><h2 className="font-serif text-2xl text-ivory">{t("app.checkins.emptyTitle")}</h2><p className="mt-2 max-w-reading text-sm text-muted">{t("app.checkins.emptyBody")}</p></div>{confirmingStart ? <div className="rounded-lg border border-gold/20 bg-surface-2 p-4"><p className="mb-3 text-sm text-text">{t("app.checkins.startConfirmBody")}</p><div className="flex gap-2"><Button onClick={start} loading={starting}>{t("app.checkins.startConfirm")}</Button><Button variant="ghost" onClick={() => setConfirmingStart(false)}>{t("app.checkins.cancel")}</Button></div></div> : <Button onClick={() => setConfirmingStart(true)}>{t("app.checkins.start")}<ArrowRight className="h-4 w-4" /></Button>}{startError ? <p role="alert" className="text-sm text-danger">{startError}</p> : null}</CardContent></Card> : null}
      {current?.status === "AWAITING_SUBMISSIONS" && !submitted && current.partner_submitted && !dissolved ? <p className="rounded-lg border border-gold/20 bg-gold/5 p-3 text-sm text-text">{t("app.checkins.partnerWaiting")}</p> : null}
      {current?.status === "AWAITING_SUBMISSIONS" && !submitted && !dissolved ? <AnswerForm workspaceId={workspaceId} round={current} onReload={onReload} /> : null}
      {current?.status === "AWAITING_SUBMISSIONS" && submitted && !dissolved ? <Card><CardContent className="flex flex-col items-start gap-4 p-8"><div className="rounded-full bg-gold/10 p-3"><Check className="h-6 w-6 text-gold" /></div><div><h2 className="font-serif text-2xl text-ivory">{current.partner_submitted ? t("app.checkins.partnerSubmitted") : t("app.checkins.waitingTitle")}</h2><p className="mt-2 text-sm text-muted">{t("app.checkins.waitingBody")}</p></div><Button variant="secondary" onClick={onReload}><RefreshCw className="h-4 w-4" />{t("app.checkins.refresh")}</Button></CardContent></Card> : null}
      {displayRound ? <MyResponses round={displayRound} /> : null}
      {current?.status === "AWAITING_SUBMISSIONS" && current.snapshot_origin !== "ROUND_START" ? <p className="rounded-lg border border-white/10 bg-surface-2 p-3 text-xs text-muted">{provenance(current.snapshot_origin, t)}</p> : null}
      {displayRound?.status === "ANALYZED" && displayRound.analysis ? <ResultView round={displayRound} /> : null}
      {current?.status === "ANALYZED" && !dissolved ? <div className="flex flex-wrap items-center gap-3">{confirmingStart ? <><span className="text-sm text-text">{t("app.checkins.startConfirmBody")}</span><Button onClick={start} loading={starting}>{t("app.checkins.startConfirm")}</Button><Button variant="ghost" onClick={() => setConfirmingStart(false)}>{t("app.checkins.cancel")}</Button></> : <Button onClick={() => setConfirmingStart(true)}>{t("app.checkins.newRound")}<ArrowRight className="h-4 w-4" /></Button>}{startError ? <p role="alert" className="text-sm text-danger">{startError}</p> : null}</div> : null}
      {template && !dissolved ? <TemplateEditor workspaceId={workspaceId} template={template} locked={current?.status === "AWAITING_SUBMISSIONS"} onReload={onReload} /> : null}
      <section aria-labelledby="checkin-history-title"><div className="mb-3 flex items-center gap-2"><History className="h-5 w-5 text-bronze" /><h2 id="checkin-history-title" className="font-serif text-xl text-ivory">{t("app.checkins.historyTitle")}</h2></div>{sortedHistory.length ? <div className="divide-y divide-white/10 rounded-xl border border-white/10 bg-surface">{sortedHistory.map((item) => <button type="button" key={item.id} aria-pressed={selectedRound?.id === item.id} onClick={async () => { setHistoryError(null); try { setSelectedRound(await api.workspaces.checkins.get(workspaceId, item.id)); } catch (cause) { setHistoryError(cause instanceof Error ? cause.message : t("app.checkins.loadError")); } }} className="flex w-full items-center justify-between gap-4 p-4 text-left hover:bg-white/[0.03] aria-pressed:bg-white/[0.05]"><span><span className="block text-sm text-text">{formatDate(item.cycle_started_at, locale)}</span><span className="text-xs text-muted">{t("app.checkins.version")} {item.checkin_template_version}</span></span><span className="text-xs uppercase tracking-wide text-bronze">{item.status === "ANALYZED" ? t("app.checkins.analyzed") : t("app.checkins.open")}</span></button>)}</div> : <p className="rounded-xl border border-dashed border-white/15 p-6 text-sm text-muted">{dissolved ? t("app.checkins.emptyDissolved") : t("app.checkins.historyEmpty")}</p>}{historyError ? <p role="alert" className="mt-3 text-sm text-danger">{historyError}</p> : null}</section>
    </div>
  </div>;
}
