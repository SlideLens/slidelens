import { describe, expect, it } from "vitest";
import type { Finding } from "@/api/schemas";
import { findings as fixtureFindings } from "@/fixtures/findings";
import { findRecurringPatterns } from "./recurringFindings";

function finding(overrides: Partial<Finding>): Finding {
  return {
    id: crypto.randomUUID(),
    slide_num: 1,
    category: "READABILITY",
    severity: "MAJOR",
    title: "Низкий контраст текста и фона",
    description: "...",
    fix_suggestion: "...",
    bbox: null,
    auto_fixable: false,
    auto_fixed: false,
    source: "slide_analyzer",
    ...overrides,
  };
}

describe("findRecurringPatterns", () => {
  it("finds nothing in a deck with no repeated issue type", () => {
    expect(findRecurringPatterns(fixtureFindings)).toEqual([]);
  });

  it("groups near-identical titles across 3+ distinct slides", () => {
    const findings = [
      finding({ slide_num: 1, title: "Низкий контраст текста и фона" }),
      finding({ slide_num: 2, title: "Низкий контраст текста и фона в подзаголовке" }),
      finding({ slide_num: 3, title: "Низкий контраст текста и фона в блоках" }),
    ];
    const groups = findRecurringPatterns(findings);
    expect(groups).toHaveLength(1);
    expect(groups[0].slideNums).toEqual([1, 2, 3]);
    expect(groups[0].title).toBe("Низкий контраст текста и фона"); // shortest representative
  });

  it("does not group below the minSlides threshold", () => {
    const findings = [
      finding({ slide_num: 1 }),
      finding({ slide_num: 2 }),
    ];
    expect(findRecurringPatterns(findings)).toEqual([]);
  });

  it("does not group different categories even with similar wording", () => {
    const findings = [
      finding({ slide_num: 1, category: "READABILITY" }),
      finding({ slide_num: 2, category: "TYPOGRAPHY" }),
      finding({ slide_num: 3, category: "READABILITY" }),
    ];
    expect(findRecurringPatterns(findings)).toEqual([]);
  });

  it("does not merge repeats within the same slide into extra distinct-slide count", () => {
    const findings = [
      finding({ slide_num: 1 }),
      finding({ slide_num: 1 }),
      finding({ slide_num: 1 }),
    ];
    expect(findRecurringPatterns(findings)).toEqual([]);
  });

  it("ignores deck-level findings (no slide_num)", () => {
    const findings = [
      finding({ slide_num: null }),
      finding({ slide_num: null }),
      finding({ slide_num: null }),
    ];
    expect(findRecurringPatterns(findings)).toEqual([]);
  });

  it("escalates to the worst severity present in the group", () => {
    const findings = [
      finding({ slide_num: 1, severity: "MINOR" }),
      finding({ slide_num: 2, severity: "CRITICAL" }),
      finding({ slide_num: 3, severity: "MAJOR" }),
    ];
    const groups = findRecurringPatterns(findings);
    expect(groups[0].severity).toBe("CRITICAL");
  });

  it("does not group unrelated titles in the same category", () => {
    const findings = [
      finding({ slide_num: 1, title: "Низкий контраст текста и фона" }),
      finding({ slide_num: 2, title: "Слишком много текста на слайде" }),
      finding({ slide_num: 3, title: "Мелкие элементы неразличимы при проекции" }),
    ];
    expect(findRecurringPatterns(findings)).toEqual([]);
  });
});
