"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { ComparisonTable } from "@/components/relationships/comparison-table";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { api } from "@/api/client";
import { asRelationshipComparison } from "@/api/canonical-profile";
import { useAsync } from "@/lib/use-async";
import { formatDateTime } from "@/lib/utils";
import { ArrowLeft } from "lucide-react";

function RelationshipContent({ relationshipId }: { relationshipId: string }) {
  const state = useAsync(() => api.relationships.get(relationshipId), [relationshipId]);

  if (state.status === "loading") return <LoadingState label="Loading comparison…" />;
  if (state.status === "error") {
    return (
      <ErrorState
        error={state.error}
        onRetry={state.reload}
        title="Could not load this comparison"
      />
    );
  }

  const relationship = state.data;
  const comparison = asRelationshipComparison(relationship.comparison);
  // Server-resolved names (V1.5 Epic A/E) — real cross-device identities, not a
  // browser-only cache. Falls back to a neutral label only if the backing Person
  // row was itself deleted after this comparison was created.
  const labelA = relationship.person_a.display_name || "Person A";
  const labelB = relationship.person_b.display_name || "Person B";

  return (
    <div className="animate-rise-in">
      <Link
        href="/relationships"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-gold"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All comparisons
      </Link>

      <header className="sacred-wheel-bg-left relative mb-8 overflow-hidden rounded-xl border border-white/10 bg-surface p-6 shadow-elevated sm:p-8">
        <NumericWheel className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 opacity-[0.12]" />
        <div className="relative">
          <p className="mb-2 text-xs uppercase tracking-wider text-bronze">Comparison</p>
          <h1 className="font-serif text-3xl text-ivory sm:text-4xl">
            {labelA} <span className="text-muted">&amp;</span> {labelB}
          </h1>
          <p className="mt-2 text-sm text-muted">Created {formatDateTime(relationship.created_at)}</p>

          <div className="mt-6 grid gap-3 border-t border-white/10 pt-5 text-xs sm:grid-cols-2">
            <div>
              <p className="text-muted">Calculation A</p>
              <Link
                href={`/analysis/${relationship.calculation_a_id}`}
                className="mt-0.5 block truncate font-mono text-text transition-colors hover:text-gold"
              >
                {relationship.calculation_a_id}
              </Link>
            </div>
            <div>
              <p className="text-muted">Calculation B</p>
              <Link
                href={`/analysis/${relationship.calculation_b_id}`}
                className="mt-0.5 block truncate font-mono text-text transition-colors hover:text-gold"
              >
                {relationship.calculation_b_id}
              </Link>
            </div>
          </div>
        </div>
      </header>

      <div
        role="note"
        className="mb-6 rounded-xl border border-white/10 bg-surface-2 p-5 text-sm leading-relaxed text-muted"
      >
        Numra compares two profiles metric by metric and stops there. It does not compute a
        compatibility percentage, a match count, or any other combined score — there is no
        defensible deterministic method for one, so inventing a number would undermine
        everything else on this page.
      </div>

      <ComparisonTable comparison={comparison} labelA={labelA} labelB={labelB} />
    </div>
  );
}

export default function RelationshipDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell>
      <RelationshipContent relationshipId={params.id} />
    </AppShell>
  );
}
