"use client";

import { useState } from "react";
import { Activity, BarChart3, CalendarDays, Save, Sparkles, Trash2 } from "lucide-react";
import {
  api,
  type ConfidenceCategory,
  type CorrelationTarget,
  type CustomMetricDefinitionOut,
  type EvidenceResultOut,
  type LifeTrackingEntryCreateRequest,
  type LifeTrackingEntryOut,
  type PatternAnalysisCreateRequest,
  type PatternAnalysisOut,
} from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ErrorState, LoadingState, PhaseDisabledState, isPhaseDisabledError } from "@/components/ui/states";
import { Textarea } from "@/components/ui/textarea";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { formatIsoDate, todayIsoDate } from "@/lib/utils";

const METRICS = ["mood", "energy", "sleep", "stress", "focus"] as const;
type Metric = (typeof METRICS)[number];
const PAGE_SIZE = 200;

const metricKeys: Record<Metric, "app.evidence.metricMood" | "app.evidence.metricEnergy" | "app.evidence.metricSleep" | "app.evidence.metricStress" | "app.evidence.metricFocus"> = {
  mood: "app.evidence.metricMood", energy: "app.evidence.metricEnergy", sleep: "app.evidence.metricSleep",
  stress: "app.evidence.metricStress", focus: "app.evidence.metricFocus",
};

const confidenceKeys: Record<ConfidenceCategory, "app.evidence.confidenceNone" | "app.evidence.confidenceLow" | "app.evidence.confidenceMedium" | "app.evidence.confidenceHigh"> = {
  NO_RELIABLE_PATTERN: "app.evidence.confidenceNone", LOW: "app.evidence.confidenceLow",
  MEDIUM: "app.evidence.confidenceMedium", HIGH: "app.evidence.confidenceHigh",
};

async function loadAll<T>(fetchPage: (offset: number) => Promise<T[]>): Promise<T[]> {
  const result: T[] = [];
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const page = await fetchPage(offset);
    result.push(...page);
    if (page.length < PAGE_SIZE) return result;
  }
}

function nullableScore(value: string): number | null {
  return value ? Number(value) : null;
}

function scaleValues(definition: CustomMetricDefinitionOut): number[] {
  return Array.from(
    { length: definition.scale_max - definition.scale_min + 1 },
    (_, index) => definition.scale_min + index,
  );
}

function ResultCard({ result, onSave, saving, saveDisabled }: { result: EvidenceResultOut; onSave: () => void; saving: boolean; saveDisabled: boolean }) {
  const { t } = useLocale();
  const reliable = result.confidence_category !== "NO_RELIABLE_PATTERN";
  return <Card className="border-gold/20 bg-[radial-gradient(circle_at_top_right,rgba(200,169,107,0.10),transparent_45%)]">
    <CardHeader>
      <div className="flex items-center gap-2"><BarChart3 className="h-5 w-5 text-gold" /><CardTitle>{reliable ? t("app.evidence.resultTitle") : t("app.evidence.noPatternTitle")}</CardTitle></div>
      <CardDescription>{reliable ? t("app.evidence.resultIntro") : t("app.evidence.noPatternBody")}</CardDescription>
    </CardHeader>
    <CardContent className="space-y-5">
      {result.statement_text ? <p className="font-serif text-xl leading-8 text-ivory">{result.statement_text}</p> : null}
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-white/10 bg-surface-2 p-3"><dt className="text-xs text-muted">{t("app.evidence.sample")}</dt><dd className="mt-1 font-semibold text-ivory">{result.sample_size} {t("app.evidence.observations")}</dd></div>
        <div className="rounded-lg border border-white/10 bg-surface-2 p-3"><dt className="text-xs text-muted">{t("app.evidence.window")}</dt><dd className="mt-1 font-semibold text-ivory">{result.observation_window_days} {t("app.evidence.daysWindow")}</dd></div>
        <div className="rounded-lg border border-white/10 bg-surface-2 p-3"><dt className="text-xs text-muted">{t("app.evidence.uncertainty")}</dt><dd className="mt-1"><Badge variant="neutral">{t(confidenceKeys[result.confidence_category])}</Badge></dd></div>
      </dl>
      <p className="text-xs leading-5 text-muted">{t("app.evidence.nonCausal")}</p>
      <Button variant="secondary" onClick={onSave} loading={saving} disabled={saveDisabled}><Save className="h-4 w-4" />{t("app.evidence.saveAnalysis")}</Button>
    </CardContent>
  </Card>;
}

export function EvidenceLayerContent({ personId, personName }: { personId: string; personName: string }) {
  const { t } = useLocale();
  const state = useAsync(() => Promise.all([
    loadAll((offset) => api.people.lifeTracking.list(personId, { limit: PAGE_SIZE, offset })),
    loadAll((offset) => api.evidence.analyses.list(personId, { limit: PAGE_SIZE, offset })),
    api.people.customMetrics.list(personId),
  ]), [personId]);
  const [entries, setEntries] = useState<LifeTrackingEntryOut[] | null>(null);
  const [analyses, setAnalyses] = useState<PatternAnalysisOut[] | null>(null);
  const [definitions, setDefinitions] = useState<CustomMetricDefinitionOut[] | null>(null);
  const [entryDate, setEntryDate] = useState(todayIsoDate);
  const [scores, setScores] = useState<Record<Metric, string>>({ mood: "", energy: "", sleep: "", stress: "", focus: "" });
  const [customScores, setCustomScores] = useState<Record<string, string>>({});
  const [customKey, setCustomKey] = useState("");
  const [customLabel, setCustomLabel] = useState("");
  const [metricBusy, setMetricBusy] = useState(false);
  const [metricError, setMetricError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [savingEntry, setSavingEntry] = useState(false);
  const [entryError, setEntryError] = useState<string | null>(null);
  const [query, setQuery] = useState<PatternAnalysisCreateRequest>({ metric_key: "mood", correlation_target: "PERSONAL_DAY", correlation_target_value: 1 });
  const [resolved, setResolved] = useState<{ result: EvidenceResultOut; query: PatternAnalysisCreateRequest } | null>(null);
  const [checking, setChecking] = useState(false);
  const [savingAnalysis, setSavingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [deletingEntries, setDeletingEntries] = useState<Set<string>>(new Set());
  const [phaseDisabledCode, setPhaseDisabledCode] = useState<Parameters<typeof PhaseDisabledState>[0]["code"] | null>(null);

  if (state.status === "loading") return <LoadingState label={t("app.evidence.loading")} />;
  if (state.status === "error") return isPhaseDisabledError(state.error)
    ? <PhaseDisabledState code={state.error.code} title={t("app.evidence.disabled")} description={t("app.evidence.disabledBody")} />
    : <ErrorState error={state.error} onRetry={state.reload} />;
  const initialEntries = state.data[0];
  const initialAnalyses = state.data[1];
  const initialDefinitions = state.data[2];
  const shownEntries = entries ?? initialEntries;
  const shownAnalyses = analyses ?? initialAnalyses;
  const shownDefinitions = definitions ?? initialDefinitions;
  const activeDefinitions = shownDefinitions.filter((definition) => definition.active);

  if (phaseDisabledCode) return <PhaseDisabledState code={phaseDisabledCode} title={t("app.evidence.disabled")} description={t("app.evidence.disabledBody")} />;

  function handleMutationError(cause: unknown, fallback: string, setMessage: (message: string) => void) {
    if (isPhaseDisabledError(cause)) { setPhaseDisabledCode(cause.code); return; }
    setMessage(cause instanceof Error ? cause.message : fallback);
  }

  async function createEntry() {
    if (checking || savingAnalysis || metricBusy || deletingEntries.size > 0) return;
    if (!METRICS.some((metric) => scores[metric]) && !Object.values(customScores).some(Boolean)) { setEntryError(t("app.evidence.metricRequired")); return; }
    setSavingEntry(true); setEntryError(null);
    const body: LifeTrackingEntryCreateRequest = {
      entry_date: entryDate, note: note.trim() || null,
      custom_metrics: Object.fromEntries(activeDefinitions.flatMap((definition) => customScores[definition.metric_key] ? [[definition.metric_key, Number(customScores[definition.metric_key])]] : [])),
      ...Object.fromEntries(METRICS.map((metric) => [metric, nullableScore(scores[metric])])),
    };
    try {
      const created = await api.people.lifeTracking.create(personId, body);
      setEntries((current) => (current ?? initialEntries).filter((item) => item.entry_date !== created.entry_date).concat(created).sort((a, b) => b.entry_date.localeCompare(a.entry_date)));
      setResolved(null);
      setScores({ mood: "", energy: "", sleep: "", stress: "", focus: "" }); setCustomScores({}); setNote("");
    } catch (cause) { handleMutationError(cause, t("app.evidence.saveError"), setEntryError); }
    finally { setSavingEntry(false); }
  }

  async function checkPattern() {
    if (savingEntry || savingAnalysis || metricBusy || deletingEntries.size > 0) return;
    const querySnapshot = { ...query };
    setChecking(true); setAnalysisError(null); setResolved(null);
    try { setResolved({ result: await api.evidence.result(personId, querySnapshot), query: querySnapshot }); }
    catch (cause) { handleMutationError(cause, t("app.evidence.analysisError"), setAnalysisError); }
    finally { setChecking(false); }
  }

  async function saveAnalysis() {
    if (!resolved || savingEntry || metricBusy || deletingEntries.size > 0) return;
    setSavingAnalysis(true); setAnalysisError(null);
    try { const saved = await api.evidence.analyses.create(personId, resolved.query); setAnalyses((current) => [saved, ...(current ?? initialAnalyses)]); }
    catch (cause) { handleMutationError(cause, t("app.evidence.saveAnalysisError"), setAnalysisError); }
    finally { setSavingAnalysis(false); }
  }

  async function deleteEntry(entryId: string) {
    if (deletingEntries.has(entryId) || checking || savingEntry || savingAnalysis || metricBusy) return;
    setDeletingEntries((current) => new Set(current).add(entryId));
    setEntryError(null);
    try {
      await api.people.lifeTracking.remove(entryId);
      setEntries((current) => (current ?? initialEntries).filter((entry) => entry.id !== entryId));
      setResolved(null);
    } catch (cause) { handleMutationError(cause, t("app.evidence.deleteError"), setEntryError); }
    finally { setDeletingEntries((current) => { const next = new Set(current); next.delete(entryId); return next; }); }
  }

  async function createCustomMetric() {
    if (metricBusy || checking || savingEntry || savingAnalysis || deletingEntries.size > 0) return;
    const metricKey = customKey.trim();
    const label = customLabel.trim();
    if (!/^[a-z][a-z0-9_]*$/.test(metricKey) || !label) { setMetricError(t("app.evidence.customInvalid")); return; }
    setMetricBusy(true); setMetricError(null);
    try {
      const created = await api.people.customMetrics.create(personId, { metric_key: metricKey, label, scale_min: 1, scale_max: 10 });
      setDefinitions((current) => [...(current ?? initialDefinitions), created]);
      setCustomKey(""); setCustomLabel("");
    } catch (cause) { handleMutationError(cause, t("app.evidence.customError"), setMetricError); }
    finally { setMetricBusy(false); }
  }

  async function retireCustomMetric(definition: CustomMetricDefinitionOut) {
    if (metricBusy || checking || savingEntry || savingAnalysis || deletingEntries.size > 0) return;
    setMetricBusy(true); setMetricError(null);
    try {
      const retired = await api.people.customMetrics.patch(definition.id, { active: false });
      setDefinitions((current) => (current ?? initialDefinitions).map((item) => item.id === retired.id ? retired : item));
      setCustomScores((current) => { const next = { ...current }; delete next[definition.metric_key]; return next; });
      if (query.metric_key === definition.metric_key) setQuery((current) => ({ ...current, metric_key: "mood" }));
      setResolved(null);
    } catch (cause) { handleMutationError(cause, t("app.evidence.customError"), setMetricError); }
    finally { setMetricBusy(false); }
  }

  return <div className="animate-rise-in space-y-8">
    <header className="relative overflow-hidden rounded-xl border border-white/10 bg-surface p-6 shadow-elevated sm:p-8">
      <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-gold/5 blur-3xl" />
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-bronze">{t("app.evidence.eyebrow")}</p>
      <h1 className="mt-2 font-serif text-3xl text-ivory sm:text-4xl">{t("app.evidence.title")}</h1>
      <p className="mt-3 max-w-reading text-sm leading-6 text-muted">{t("app.evidence.intro").replace("{name}", personName)}</p>
    </header>
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(22rem,0.95fr)]">
      <section className="space-y-5" aria-labelledby="journal-title">
        <div><h2 id="journal-title" className="font-serif text-2xl text-ivory">{t("app.evidence.journalTitle")}</h2><p className="mt-1 text-sm text-muted">{t("app.evidence.journalIntro")}</p></div>
        <Card><CardContent className="space-y-5 p-5">
          <div><Label htmlFor="evidence-date">{t("app.evidence.date")}</Label><Input id="evidence-date" type="date" value={entryDate} max={todayIsoDate()} disabled={savingEntry} onChange={(event) => setEntryDate(event.target.value)} /></div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">{METRICS.map((metric) => <div key={metric}><Label htmlFor={`metric-${metric}`}>{t(metricKeys[metric])}</Label><Select id={`metric-${metric}`} aria-label={t(metricKeys[metric])} value={scores[metric]} disabled={savingEntry} onChange={(event) => setScores((old) => ({ ...old, [metric]: event.target.value }))}><option value="">—</option>{Array.from({ length: 10 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>{value}</option>)}</Select></div>)}</div>
          {activeDefinitions.length ? <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{activeDefinitions.map((definition) => <div key={definition.id}><Label htmlFor={`metric-${definition.metric_key}`}>{definition.label}</Label><Select id={`metric-${definition.metric_key}`} aria-label={definition.label} value={customScores[definition.metric_key] ?? ""} disabled={savingEntry || metricBusy} onChange={(event) => setCustomScores((old) => ({ ...old, [definition.metric_key]: event.target.value }))}><option value="">—</option>{scaleValues(definition).map((value) => <option key={value} value={value}>{value}</option>)}</Select></div>)}</div> : null}
          <div><Label htmlFor="evidence-note">{t("app.evidence.note")}</Label><Textarea id="evidence-note" maxLength={2000} value={note} disabled={savingEntry} onChange={(event) => setNote(event.target.value)} /></div>
          {entryError ? <p role="alert" className="text-sm text-danger">{entryError}</p> : null}
          <Button onClick={() => void createEntry()} loading={savingEntry} disabled={checking || savingAnalysis || metricBusy || deletingEntries.size > 0}><CalendarDays className="h-4 w-4" />{t("app.evidence.saveDay")}</Button>
        </CardContent></Card>
        <Card><CardHeader><CardTitle>{t("app.evidence.customTitle")}</CardTitle><CardDescription>{t("app.evidence.customIntro")}</CardDescription></CardHeader><CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2"><div><Label htmlFor="custom-metric-key">{t("app.evidence.customKey")}</Label><Input id="custom-metric-key" value={customKey} disabled={metricBusy} pattern="[a-z][a-z0-9_]*" aria-describedby="custom-metric-key-hint" onChange={(event) => setCustomKey(event.target.value)} /><p id="custom-metric-key-hint" className="mt-1 text-xs text-muted">{t("app.evidence.customKeyHint")}</p></div><div><Label htmlFor="custom-metric-label">{t("app.evidence.customLabel")}</Label><Input id="custom-metric-label" value={customLabel} disabled={metricBusy} maxLength={80} onChange={(event) => setCustomLabel(event.target.value)} /></div></div>
          {metricError ? <p role="alert" className="text-sm text-danger">{metricError}</p> : null}
          <Button variant="secondary" onClick={() => void createCustomMetric()} loading={metricBusy} disabled={checking || savingEntry || savingAnalysis || deletingEntries.size > 0}>{t("app.evidence.customCreate")}</Button>
          {activeDefinitions.length ? <div className="flex flex-wrap gap-2">{activeDefinitions.map((definition) => <Button key={definition.id} variant="ghost" size="sm" disabled={metricBusy || checking || savingEntry || savingAnalysis || deletingEntries.size > 0} aria-label={`${definition.label} ${t("app.evidence.customRetire")}`} onClick={() => void retireCustomMetric(definition)}>{definition.label} · {t("app.evidence.customRetire")}</Button>)}</div> : null}
        </CardContent></Card>
        <div className="space-y-3">{shownEntries.length === 0 ? <p className="rounded-xl border border-dashed border-white/15 p-6 text-sm text-muted">{t("app.evidence.empty")}</p> : shownEntries.map((item) => <Card key={item.id}><CardContent className="p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-medium text-ivory">{formatIsoDate(item.entry_date)}</p><div className="mt-2 flex flex-wrap gap-2">{METRICS.filter((metric) => item[metric] !== null).map((metric) => <Badge key={metric} variant="neutral">{t(metricKeys[metric])} {item[metric]}/10</Badge>)}{Object.entries(item.custom_metrics).map(([key, value]) => { const definition = shownDefinitions.find((item) => item.metric_key === key); return <Badge key={key} variant="neutral">{definition?.label ?? key} {value}{definition ? `/${definition.scale_max}` : ""}</Badge>; })}</div>{item.note ? <p className="mt-3 text-sm text-text">{item.note}</p> : null}</div><Button variant="ghost" size="sm" loading={deletingEntries.has(item.id)} disabled={deletingEntries.has(item.id) || checking || savingEntry || savingAnalysis || metricBusy} aria-label={t("app.evidence.deleteEntry")} onClick={() => void deleteEntry(item.id)}><Trash2 className="h-4 w-4" /></Button></div></CardContent></Card>)}</div>
      </section>
      <section className="space-y-5" aria-labelledby="pattern-title">
        <div><h2 id="pattern-title" className="font-serif text-2xl text-ivory">{t("app.evidence.patternTitle")}</h2><p className="mt-1 text-sm text-muted">{t("app.evidence.patternIntro")}</p></div>
        <Card><CardContent className="grid gap-4 p-5 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
          <div><Label htmlFor="pattern-metric">{t("app.evidence.metric")}</Label><Select id="pattern-metric" value={query.metric_key} disabled={checking || savingAnalysis || metricBusy} onChange={(event) => setQuery((old) => ({ ...old, metric_key: event.target.value }))}>{METRICS.map((metric) => <option key={metric} value={metric}>{t(metricKeys[metric])}</option>)}{activeDefinitions.map((definition) => <option key={definition.id} value={definition.metric_key}>{definition.label}</option>)}</Select></div>
          <div><Label htmlFor="pattern-target">{t("app.evidence.target")}</Label><Select id="pattern-target" value={query.correlation_target} disabled={checking || savingAnalysis} onChange={(event) => setQuery((old) => ({ ...old, correlation_target: event.target.value as CorrelationTarget }))}><option value="PERSONAL_DAY">{t("app.evidence.personalDay")}</option><option value="PERSONAL_MONTH">{t("app.evidence.personalMonth")}</option><option value="PERSONAL_YEAR">{t("app.evidence.personalYear")}</option></Select></div>
          <div><Label htmlFor="pattern-value">{t("app.evidence.targetValue")}</Label><Select id="pattern-value" value={query.correlation_target_value} disabled={checking || savingAnalysis} onChange={(event) => setQuery((old) => ({ ...old, correlation_target_value: Number(event.target.value) }))}>{Array.from({ length: 10 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>{value}</option>)}</Select></div>
          <Button className="sm:col-span-3 xl:col-span-1 2xl:col-span-3" onClick={() => void checkPattern()} loading={checking} disabled={savingEntry || savingAnalysis || metricBusy || deletingEntries.size > 0}><Sparkles className="h-4 w-4" />{t("app.evidence.check")}</Button>
        </CardContent></Card>
        {analysisError ? <p role="alert" className="text-sm text-danger">{analysisError}</p> : null}
        {resolved ? <ResultCard result={resolved.result} onSave={() => void saveAnalysis()} saving={savingAnalysis} saveDisabled={savingEntry || metricBusy || deletingEntries.size > 0} /> : null}
        {shownAnalyses.length ? <div><h3 className="mb-3 flex items-center gap-2 font-serif text-xl text-ivory"><Activity className="h-4 w-4 text-bronze" />{t("app.evidence.savedTitle")}</h3><div className="space-y-3">{shownAnalyses.map((analysis) => <Card key={analysis.id}><CardContent className="p-4"><p className="text-sm text-text">{analysis.result.statement_text ?? t("app.evidence.noPatternTitle")}</p><div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted"><span>{analysis.result.sample_size} {t("app.evidence.observations")}</span><span>·</span><span>{analysis.result.observation_window_days} {t("app.evidence.daysWindow")}</span><Badge variant="neutral">{t(confidenceKeys[analysis.result.confidence_category])}</Badge></div><p className="mt-3 text-xs leading-5 text-muted">{t("app.evidence.nonCausal")}</p></CardContent></Card>)}</div></div> : null}
      </section>
    </div>
  </div>;
}
