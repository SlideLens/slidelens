import type { Category, Finding, Severity } from "@/api/schemas";

export interface RecurringGroup {
  category: Category;
  severity: Severity;
  title: string;
  slideNums: number[];
}

const SEVERITY_ORDER: Record<Severity, number> = { CRITICAL: 0, MAJOR: 1, MINOR: 2 };

function tokenize(title: string): Set<string> {
  return new Set(
    title
      .toLowerCase()
      .replace(/[^a-zа-яё0-9\s]/gi, " ")
      .split(/\s+/)
      .filter(Boolean),
  );
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let intersection = 0;
  for (const token of a) if (b.has(token)) intersection++;
  const union = a.size + b.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

/**
 * Groups per-slide findings whose title is near-identical (same category, high word
 * overlap) across at least `minSlides` distinct slides — e.g. the same low-contrast
 * issue flagged slide after slide. Each analyzer only ever sees one slide at a time
 * (ADR 0002), so it can't notice this itself; this is a pure presentation grouping,
 * the underlying per-slide Находки are untouched (still individually visible/fixable).
 */
export function findRecurringPatterns(
  findings: Finding[],
  { minSlides = 3, similarity = 0.5 }: { minSlides?: number; similarity?: number } = {},
): RecurringGroup[] {
  const perSlide = findings.filter((f): f is Finding & { slide_num: number } => f.slide_num != null);

  const groups: { category: Category; tokens: Set<string>; members: (Finding & { slide_num: number })[] }[] = [];
  for (const finding of perSlide) {
    const tokens = tokenize(finding.title);
    const match = groups.find(
      (g) => g.category === finding.category && jaccard(g.tokens, tokens) >= similarity,
    );
    if (match) {
      match.members.push(finding);
    } else {
      groups.push({ category: finding.category, tokens, members: [finding] });
    }
  }

  const result: RecurringGroup[] = [];
  for (const group of groups) {
    const slideNums = [...new Set(group.members.map((m) => m.slide_num))].sort((a, b) => a - b);
    if (slideNums.length < minSlides) continue;

    const severity = group.members.reduce<Severity>(
      (worst, m) => (SEVERITY_ORDER[m.severity] < SEVERITY_ORDER[worst] ? m.severity : worst),
      group.members[0].severity,
    );
    const title = group.members.reduce(
      (shortest, m) => (m.title.length < shortest.length ? m.title : shortest),
      group.members[0].title,
    );
    result.push({ category: group.category, severity, title, slideNums });
  }

  return result.sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || b.slideNums.length - a.slideNums.length,
  );
}
