import type { Category, Severity } from "@/api/schemas";

export const CATEGORY_LABELS: Record<Category, string> = {
  TYPOGRAPHY: "Типографика",
  HIERARCHY: "Иерархия",
  READABILITY: "Читаемость",
  CONSISTENCY: "Консистентность",
  CHART: "График",
  NARRATIVE: "Нарратив",
  SPEECH_MISMATCH: "Речь ↔ слайд",
  DELIVERY: "Подача",
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  CRITICAL: "Критично",
  MAJOR: "Серьёзно",
  MINOR: "Мелочь",
};

export const SEVERITY_BADGE_VARIANT: Record<Severity, "critical" | "major" | "minor"> = {
  CRITICAL: "critical",
  MAJOR: "major",
  MINOR: "minor",
};
