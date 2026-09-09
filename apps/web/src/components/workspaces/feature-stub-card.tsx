import { ComingSoonState } from "@/components/ui/states";

export interface FeatureStubCardProps {
  eyebrow: string;
  title: string;
  description: string;
}

/**
 * Generic navigation/announcement card for a not-yet-built hub feature area.
 * Deliberately makes no fetch call even though `api.workspaces.checkins/tasks/
 * roadmaps/copilot.*` are already fully typed -- same PR-WEB-00 stub pattern as
 * the existing `/copilot` page.
 */
export function FeatureStubCard({ eyebrow, title, description }: FeatureStubCardProps) {
  return (
    <section>
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-bronze">{eyebrow}</h2>
      <ComingSoonState title={title} description={description} />
    </section>
  );
}
