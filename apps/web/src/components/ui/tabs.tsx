"use client";

import { useState, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TabDef {
  id: string;
  label: string;
  content: ReactNode;
}

export function Tabs({
  tabs,
  initialId,
  ariaLabel = "Analysis views",
}: {
  tabs: TabDef[];
  initialId?: string;
  ariaLabel?: string;
}) {
  const [active, setActive] = useState(initialId ?? tabs[0]?.id);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const idx = tabs.findIndex((t) => t.id === active);
    if (event.key === "ArrowRight") {
      event.preventDefault();
      setActive(tabs[(idx + 1) % tabs.length]?.id);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      setActive(tabs[(idx - 1 + tabs.length) % tabs.length]?.id);
    }
  }

  return (
    <div>
      <div
        role="tablist"
        aria-label={ariaLabel}
        onKeyDown={onKeyDown}
        className="mb-6 flex flex-wrap gap-1 border-b border-white/10"
      >
        {tabs.map((tab) => {
          const selected = tab.id === active;
          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls={`panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(tab.id)}
              className={cn(
                "-mb-px rounded-t-lg border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                selected
                  ? "border-gold text-gold"
                  : "border-transparent text-muted hover:text-ivory",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          id={`panel-${tab.id}`}
          role="tabpanel"
          aria-labelledby={`tab-${tab.id}`}
          hidden={tab.id !== active}
          tabIndex={0}
        >
          {tab.id === active && tab.content}
        </div>
      ))}
    </div>
  );
}
