import { useSearchParams } from "react-router-dom";
import type { Category, Severity } from "@/api/schemas";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_LABELS, SEVERITY_BADGE_VARIANT, SEVERITY_LABELS } from "@/components/report/labels";
import { cn } from "@/lib/utils";

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as Category[];
const ALL_SEVERITIES = Object.keys(SEVERITY_LABELS) as Severity[];

export interface FindingFiltersValue {
  categories: Category[];
  severities: Severity[];
}

/** Filter state lives in `?category=`/`?severity=` (comma-separated) — shareable by link. */
export function useFindingFilters(): [FindingFiltersValue, (next: FindingFiltersValue) => void] {
  const [searchParams, setSearchParams] = useSearchParams();

  const categories = (searchParams.get("category")?.split(",").filter(Boolean) ?? []) as Category[];
  const severities = (searchParams.get("severity")?.split(",").filter(Boolean) ?? []) as Severity[];

  const setValue = (next: FindingFiltersValue) => {
    const params = new URLSearchParams(searchParams);
    if (next.categories.length) params.set("category", next.categories.join(","));
    else params.delete("category");
    if (next.severities.length) params.set("severity", next.severities.join(","));
    else params.delete("severity");
    setSearchParams(params, { replace: true });
  };

  return [{ categories, severities }, setValue];
}

export interface FindingFiltersProps {
  value: FindingFiltersValue;
  onChange: (next: FindingFiltersValue) => void;
}

export function FindingFilters({ value, onChange }: FindingFiltersProps) {
  function toggleCategory(category: Category) {
    const has = value.categories.includes(category);
    onChange({
      ...value,
      categories: has
        ? value.categories.filter((c) => c !== category)
        : [...value.categories, category],
    });
  }

  function toggleSeverity(severity: Severity) {
    const has = value.severities.includes(severity);
    onChange({
      ...value,
      severities: has
        ? value.severities.filter((s) => s !== severity)
        : [...value.severities, severity],
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
          Серьёзность
        </span>
        {ALL_SEVERITIES.map((severity) => (
          <button key={severity} type="button" onClick={() => toggleSeverity(severity)}>
            <Badge
              variant={value.severities.includes(severity) ? SEVERITY_BADGE_VARIANT[severity] : "outline"}
              className={cn("cursor-pointer", !value.severities.includes(severity) && "opacity-60")}
            >
              {SEVERITY_LABELS[severity]}
            </Badge>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
          Категория
        </span>
        {ALL_CATEGORIES.map((category) => (
          <button key={category} type="button" onClick={() => toggleCategory(category)}>
            <Badge
              variant={value.categories.includes(category) ? "accent" : "outline"}
              className={cn("cursor-pointer", !value.categories.includes(category) && "opacity-60")}
            >
              {CATEGORY_LABELS[category]}
            </Badge>
          </button>
        ))}
      </div>
    </div>
  );
}

export function applyFindingFilters<T extends { category: Category; severity: Severity }>(
  findings: T[],
  filters: FindingFiltersValue,
): T[] {
  return findings.filter((f) => {
    const categoryOk = filters.categories.length === 0 || filters.categories.includes(f.category);
    const severityOk = filters.severities.length === 0 || filters.severities.includes(f.severity);
    return categoryOk && severityOk;
  });
}
