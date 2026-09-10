"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { PhaseDisabledState, isPhaseDisabledError } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { api, type RelationshipType, type WorkspaceOut } from "@/api/client";
import type { MessageKey } from "@/i18n/catalog";

const RELATIONSHIP_TYPES: RelationshipType[] = [
  "PARTNER",
  "DATING",
  "FRIENDSHIP",
  "FAMILY",
  "SIBLINGS",
  "PARENT_CHILD",
  "WORK",
  "OTHER",
];

const RELATIONSHIP_TYPE_KEYS: Record<RelationshipType, MessageKey> = {
  PARTNER: "app.relationshipWorkspace.typePartner",
  DATING: "app.relationshipWorkspace.typeDating",
  FRIENDSHIP: "app.relationshipWorkspace.typeFriendship",
  FAMILY: "app.relationshipWorkspace.typeFamily",
  SIBLINGS: "app.relationshipWorkspace.typeSiblings",
  PARENT_CHILD: "app.relationshipWorkspace.typeParentChild",
  WORK: "app.relationshipWorkspace.typeWork",
  OTHER: "app.relationshipWorkspace.typeOther",
};

export interface RelationshipTypeSelectorProps {
  workspaceId: string;
  workspace: WorkspaceOut;
  checkinRoundOpen?: boolean;
}

/**
 * Sets `WorkspaceOut.relationship_type` via `PATCH /v1/workspaces/{id}`. A native
 * `<Select>` plus a separate Save button -- no auto-submit on change, so a
 * misclick never fires a PATCH. DISSOLVED workspaces (both the initial state and
 * the race where the PATCH itself comes back 409/WORKSPACE_DISSOLVED) render as a
 * read-only `PhaseDisabledState` instead of an interactive control.
 */
export function RelationshipTypeSelector({ workspaceId, workspace, checkinRoundOpen = false }: RelationshipTypeSelectorProps) {
  const { t } = useLocale();
  const [selected, setSelected] = useState<RelationshipType | "">(workspace.relationship_type ?? "");
  const [saved, setSaved] = useState<RelationshipType | null>(workspace.relationship_type);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const [dissolvedRace, setDissolvedRace] = useState(false);

  if (workspace.status === "DISSOLVED" || dissolvedRace) {
    return (
      <PhaseDisabledState
        code="WORKSPACE_DISSOLVED"
        title={t("app.relationshipWorkspace.typeSelectorDissolvedTitle")}
        description={t("app.relationshipWorkspace.typeSelectorDissolvedBody")}
        action={
          saved && (
            <p className="text-sm text-text">
              {t("app.relationshipWorkspace.typeSelectorLastTypePrefix")} {t(RELATIONSHIP_TYPE_KEYS[saved])}
            </p>
          )
        }
      />
    );
  }

  async function handleSave() {
    if (!selected) return;
    setSaving(true);
    setError(false);
    setJustSaved(false);
    try {
      const updated = await api.workspaces.patch(workspaceId, { relationship_type: selected });
      setSaved(updated.relationship_type);
      setJustSaved(true);
    } catch (err) {
      if (isPhaseDisabledError(err) && err.code === "WORKSPACE_DISSOLVED") {
        setDissolvedRace(true);
      } else {
        setError(true);
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor="relationship-type-select" className="text-sm font-medium text-ivory">
        {t("app.relationshipWorkspace.typeSelectorLabel")}
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <Select
          id="relationship-type-select"
          className="w-56"
          value={selected}
          disabled={checkinRoundOpen}
          onChange={(e) => {
            setSelected(e.target.value as RelationshipType);
            setJustSaved(false);
            setError(false);
          }}
        >
          <option value="" disabled>
            {t("app.relationshipWorkspace.typeSelectorPlaceholder")}
          </option>
          {RELATIONSHIP_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(RELATIONSHIP_TYPE_KEYS[type])}
            </option>
          ))}
        </Select>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleSave}
          loading={saving}
          disabled={checkinRoundOpen || !selected || selected === saved}
          aria-disabled={checkinRoundOpen || undefined}
        >
          {t("app.relationshipWorkspace.typeSelectorSave")}
        </Button>
      </div>
      {checkinRoundOpen ? <p className="text-xs text-muted">{t("app.relationshipWorkspace.typeSelectorCheckinOpen")}</p> : null}
      {justSaved && !error && (
        <p className="text-xs text-success">{t("app.relationshipWorkspace.typeSelectorSuccess")}</p>
      )}
      {error && <p className="text-xs text-danger">{t("app.relationshipWorkspace.typeSelectorError")}</p>}
    </div>
  );
}
