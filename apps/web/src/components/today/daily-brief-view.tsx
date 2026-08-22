"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { api } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { Sparkles } from "lucide-react";

/**
 * V1.5 Epic K: the reflective counterpart to the numbers-only view above it.
 * Every sentence here comes verbatim from GET /v1/people/{id}/daily-brief, which is
 * deterministic (no LLM, no randomness) and reflective/symbolic in register --
 * never phrased as a guaranteed outcome. Same person + date always renders the same
 * text.
 */
export function DailyBriefView({ personId, asOfDate }: { personId: string; asOfDate: string }) {
  const state = useAsync(() => api.people.dailyBrief(personId, asOfDate), [personId, asOfDate]);

  if (state.status === "loading") return <LoadingState label="Composing reflection…" />;
  if (state.status === "error") {
    return (
      <ErrorState error={state.error} onRetry={state.reload} title="Could not load the reflection" />
    );
  }

  return (
    <div className="mt-6">
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-gold" aria-hidden="true" />
        <h2 className="font-serif text-lg text-ivory">Reflection</h2>
      </div>
      <div className="grid gap-3">
        {state.data.sections.map((section) => (
          <Card key={section.metric_id}>
            <CardHeader>
              <CardTitle className="text-base">
                {section.display_name_de} ({section.display_value})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="leading-relaxed text-text">
                {section.text_de}
              </CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="mt-4 max-w-reading text-xs leading-relaxed text-muted">
        Reflective and symbolic, sourced from Numra&apos;s knowledge package -- not a prediction
        and not written by a language model. Recomputed for {asOfDate}, not stored.
      </p>
    </div>
  );
}
