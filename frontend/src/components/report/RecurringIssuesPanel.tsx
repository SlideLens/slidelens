import { Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_LABELS, SEVERITY_BADGE_VARIANT, SEVERITY_LABELS } from "@/components/report/labels";
import { pluralizeRu } from "@/lib/pluralize";
import type { RecurringGroup } from "@/lib/recurringFindings";

export interface RecurringIssuesPanelProps {
  groups: RecurringGroup[];
  onSlideClick: (slideNum: number) => void;
}

/** Overview of issue types that repeat across many slides — the per-slide Находки below are unchanged. */
export function RecurringIssuesPanel({ groups, onSlideClick }: RecurringIssuesPanelProps) {
  if (groups.length === 0) return null;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2">
        <Layers className="h-4 w-4 text-muted-foreground" />
        <h3 className="font-semibold text-foreground">Повторяющиеся проблемы</h3>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Один и тот же тип проблемы встречается на нескольких слайдах — вероятно, дешевле решить
        её системно, чем слайд за слайдом.
      </p>
      <ul className="mt-3 flex flex-col gap-2.5">
        {groups.map((group) => (
          <li key={`${group.category}-${group.title}`} className="flex flex-wrap items-center gap-2 text-sm">
            <Badge variant={SEVERITY_BADGE_VARIANT[group.severity]}>{SEVERITY_LABELS[group.severity]}</Badge>
            <Badge variant="outline">{CATEGORY_LABELS[group.category]}</Badge>
            <span className="font-medium text-foreground">{group.title}</span>
            <span className="text-muted-foreground">
              — {group.slideNums.length}{" "}
              {pluralizeRu(group.slideNums.length, ["слайд", "слайда", "слайдов"])}:
            </span>
            <span className="flex flex-wrap gap-1">
              {group.slideNums.map((slideNum) => (
                <button
                  key={slideNum}
                  type="button"
                  onClick={() => onSlideClick(slideNum)}
                  className="rounded border border-border px-1.5 text-xs text-muted-foreground transition-colors hover:border-foreground hover:text-foreground"
                >
                  {slideNum}
                </button>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
