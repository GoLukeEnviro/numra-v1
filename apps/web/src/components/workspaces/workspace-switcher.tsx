import { Select } from "@/components/ui/select";
import { useLocale } from "@/i18n/context";

export interface WorkspaceOption {
  id: string;
  label: string;
  kind: "PERSONAL" | "RELATIONSHIP";
}

export interface WorkspaceSwitcherProps {
  options: WorkspaceOption[];
  activeId: string | null;
  onSelect: (id: string) => void;
  className?: string;
}

// Native <select> via the existing Select primitive -- no bespoke dropdown overlay.
// Pure presentation: caller owns the options and the active selection (PR-WEB-00
// scope boundary, see api/client.ts's V2 namespace block comment).
export function WorkspaceSwitcher({ options, activeId, onSelect, className }: WorkspaceSwitcherProps) {
  const { t } = useLocale();

  function optionLabel(option: WorkspaceOption): string {
    return option.kind === "PERSONAL" ? `${t("workspace.personalPrefix")} — ${option.label}` : option.label;
  }

  return (
    <Select
      className={className}
      aria-label={t("workspace.switcherAriaLabel")}
      value={activeId ?? ""}
      onChange={(e) => onSelect(e.target.value)}
    >
      {options.map((option) => (
        <option key={option.id} value={option.id}>
          {optionLabel(option)}
        </option>
      ))}
    </Select>
  );
}
