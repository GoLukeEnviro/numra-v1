"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { ComparisonTable } from "@/components/relationships/comparison-table";
import { api } from "@/api/client";
import { asRelationshipComparison } from "@/api/canonical-profile";
import { useAsync } from "@/lib/use-async";
import { formatDateTime } from "@/lib/utils";

function RelationshipContent({ relationshipId }: { relationshipId: string }) {
  const state = useAsync(() => api.relationships.get(relationshipId), [relationshipId]);

  if (state.status === "loading") return <LoadingState label="Loading comparison…" />;
  if (state.status === "error") {
    return <ErrorState error={state.error} onRetry={state.reload} title="Could not load this comparison" />;
  }

  const relationship = state.data;
  const comparison = asRelationshipComparison(relationship.comparison);

  return (
    <div>
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">Relationship comparison</h1>
        <p className="mt-1 text-sm text-muted">Created {formatDateTime(relationship.created_at)}</p>
        <p className="mt-1 text-xs text-muted">
          Numra never computes a compatibility percentage — only per-metric matches, deterministically.
        </p>
      </div>
      <ComparisonTable comparison={comparison} />
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
