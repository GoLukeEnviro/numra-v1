"use client";

import { useState } from "react";
import Link from "next/link";
import { ApiError } from "@/api/client";
import {
  asRelationshipAnalysisResult,
  asShadowDynamicsResult,
} from "@/api/analysis-content";
import { LoadingState, ErrorState, PhaseDisabledState, type PhaseErrorCode } from "@/components/ui/states";
import { useAnalysisProgress, type AnalysisKind } from "@/lib/use-analysis-progress";
import { useLocale } from "@/i18n/context";
import type { MessageKey } from "@/i18n/catalog";
import { AnalysisLauncher } from "@/components/workspaces/dynamics/analysis-launcher";
import {
  AnalysisProgressView,
  AnalysisFailedView,
} from "@/components/workspaces/dynamics/analysis-progress-view";
import { RelationshipAnalysisView } from "@/components/workspaces/dynamics/relationship-analysis-view";
import { ShadowDynamicsView } from "@/components/workspaces/dynamics/shadow-dynamics-view";

interface SectionCopy {
  title: MessageKey;
  intro: MessageKey;
  emptyTitle: MessageKey;
  emptyBody: MessageKey;
  cta: MessageKey;
  ctaBusy: MessageKey;
}

const RELATIONSHIP_COPY: SectionCopy = {
  title: "app.dynamics.relationship.title",
  intro: "app.dynamics.relationship.intro",
  emptyTitle: "app.dynamics.relationship.emptyTitle",
  emptyBody: "app.dynamics.relationship.emptyBody",
  cta: "app.dynamics.relationship.launch",
  ctaBusy: "app.dynamics.relationship.launching",
};

const SHADOW_COPY: SectionCopy = {
  title: "app.dynamics.shadow.title",
  intro: "app.dynamics.shadow.intro",
  emptyTitle: "app.dynamics.shadow.emptyTitle",
  emptyBody: "app.dynamics.shadow.emptyBody",
  cta: "app.dynamics.shadow.launch",
  ctaBusy: "app.dynamics.shadow.launching",
};

const GATE_COPY: Record<PhaseErrorCode, { title: MessageKey; body: MessageKey } | undefined> = {
  V2_DISABLED: undefined,
  V2_PHASE_DISABLED: undefined,
  WORKSPACE_DISSOLVED: {
    title: "app.dynamics.gate.workspaceDissolvedTitle",
    body: "app.dynamics.gate.workspaceDissolvedBody",
  },
  KNOWLEDGE_FRAME_NOT_AVAILABLE: {
    title: "app.dynamics.gate.knowledgeFrameTitle",
    body: "app.dynamics.gate.knowledgeFrameBody",
  },
  CONSENT_NOT_GRANTED: {
    title: "app.dynamics.gate.consentTitle",
    body: "app.dynamics.gate.consentBody",
  },
  RELATIONSHIP_TYPE_NOT_SET: {
    title: "app.dynamics.gate.relationshipTypeTitle",
    body: "app.dynamics.gate.relationshipTypeBody",
  },
  SELF_PROFILE_REQUIRED: {
    title: "app.dynamics.gate.selfProfileTitle",
    body: "app.dynamics.gate.selfProfileBody",
  },
};

export function AnalysisSection({
  workspaceId,
  kind,
}: {
  workspaceId: string;
  kind: AnalysisKind;
}) {
  const { t } = useLocale();
  const copy = kind === "relationship" ? RELATIONSHIP_COPY : SHADOW_COPY;
  const progress = useAnalysisProgress(workspaceId, kind);

  function body() {
    if (progress.phase === "loading") {
      return <LoadingState label={t("common.loading")} />;
    }

    if (progress.phase === "phaseDisabled") {
      const code = (progress.error as ApiError).code as PhaseErrorCode;
      const gate = GATE_COPY[code] ?? {
        title: "app.dynamics.gate.consentTitle",
        body: "app.dynamics.gate.consentBody",
      };
      return (
        <PhaseDisabledState
          code={code}
          title={t(gate.title)}
          description={t(gate.body)}
          action={
            code === "CONSENT_NOT_GRANTED" ? (
              <Link
                href={`/workspaces/${workspaceId}/consent`}
                className="mt-2 text-sm text-gold underline-offset-4 hover:underline"
              >
                {t("app.dynamics.gate.consentLink")}
              </Link>
            ) : undefined
          }
        />
      );
    }

    if (progress.phase === "error") {
      return (
        <ErrorState
          error={progress.error}
          onRetry={progress.reload}
          title={t("app.dynamics.errorTitle")}
        />
      );
    }

    if (progress.phase === "empty") {
      return (
        <AnalysisLauncher
          titleKey={copy.emptyTitle}
          bodyKey={copy.emptyBody}
          ctaKey={copy.cta}
          ctaBusyKey={copy.ctaBusy}
          onLaunch={progress.launch}
          launching={progress.launching}
        />
      );
    }

    if (progress.phase === "pending") {
      return <AnalysisProgressView job={progress.job} />;
    }

    if (progress.phase === "failed") {
      return (
        <AnalysisFailedView
          job={progress.job}
          onRetry={progress.launch}
          retrying={progress.launching}
        />
      );
    }

    // complete — narrow the open `result` JSON; a guard miss is "complete but unreadable".
    const unreadable = (
      <ErrorState
        error={new Error(t("app.dynamics.unreadableBody"))}
        title={t("app.dynamics.unreadableTitle")}
        onRetry={progress.reload}
      />
    );
    if (kind === "relationship") {
      const result = asRelationshipAnalysisResult(progress.analysis.result);
      return result ? <RelationshipAnalysisView result={result} /> : unreadable;
    }
    const result = asShadowDynamicsResult(progress.analysis.result);
    return result ? <ShadowDynamicsView result={result} /> : unreadable;
  }

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="font-serif text-2xl text-ivory">{t(copy.title)}</h2>
        <p className="mt-1 max-w-reading text-sm text-muted">{t(copy.intro)}</p>
      </div>
      {body()}
    </section>
  );
}
