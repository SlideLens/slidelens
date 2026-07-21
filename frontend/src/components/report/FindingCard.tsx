import { useEffect, useState } from "react";
import { ThumbsDown, ThumbsUp, Wand2 } from "lucide-react";
import type { Finding } from "@/api/schemas";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { CATEGORY_LABELS, SEVERITY_BADGE_VARIANT, SEVERITY_LABELS } from "@/components/report/labels";
import { useApplyFindingFix } from "@/hooks/useApplyFindingFix";
import { useFlagFinding } from "@/hooks/useFlagFinding";
import { useLikeFinding } from "@/hooks/useLikeFinding";
import { cn } from "@/lib/utils";

const SEVERITY_BG: Record<Finding["severity"], string> = {
  CRITICAL: "bg-severity-critical",
  MAJOR: "bg-severity-major",
  MINOR: "bg-severity-minor",
};

export interface FindingCardProps {
  finding: Finding;
  reviewId?: string;
  isActive?: boolean;
  /** Порядковый номер — совпадает с пином на слайде. Без bbox (Дека целиком) номер не задаётся. */
  number?: number;
  /** false = визуальная демонстрация без запросов к API (лендинг с фикстурой). */
  interactive?: boolean;
}

export function FindingCard({ finding, reviewId, isActive, number, interactive = true }: FindingCardProps) {
  const [flagged, setFlagged] = useState(finding.user_flag ?? false);
  const [liked, setLiked] = useState(finding.user_like ?? false);
  const [applied, setApplied] = useState(finding.auto_fixed ?? false);

  useEffect(() => {
    setFlagged(finding.user_flag ?? false);
    setLiked(finding.user_like ?? false);
    setApplied(finding.auto_fixed ?? false);
  }, [finding.user_flag, finding.user_like, finding.auto_fixed]);

  const flagFinding = useFlagFinding(reviewId);
  const likeFinding = useLikeFinding(reviewId);
  const applyFix = useApplyFindingFix(reviewId);

  function handleFlag() {
    if (flagged) return;
    setFlagged(true);
    setLiked(false);
    if (!interactive) return;
    flagFinding.mutate(finding.id, {
      onError: () => {
        setFlagged(false);
        setLiked(finding.user_like ?? false);
      },
    });
  }

  function handleLike() {
    if (liked) return;
    setLiked(true);
    setFlagged(false);
    if (!interactive) return;
    likeFinding.mutate(finding.id, {
      onError: () => {
        setLiked(false);
        setFlagged(finding.user_flag ?? false);
      },
    });
  }

  function handleApply() {
    if (applied || !finding.auto_fixable || applyFix.isPending) return;
    setApplied(true);
    if (!interactive) return;
    applyFix.mutate(finding.id, {
      onError: () => setApplied(false),
    });
  }

  return (
    <Card
      id={`finding-${finding.id}`}
      className={cn(
        "flex gap-3 p-4 scroll-mt-24 transition-shadow",
        isActive && "ring-2 ring-accent ring-offset-2",
      )}
    >
      <span
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-xs font-bold text-white",
          SEVERITY_BG[finding.severity],
        )}
        aria-hidden="true"
      >
        {number ?? "◆"}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={SEVERITY_BADGE_VARIANT[finding.severity]}>
              {SEVERITY_LABELS[finding.severity]}
            </Badge>
            <Badge variant="outline">{CATEGORY_LABELS[finding.category]}</Badge>
            {finding.slide_num == null && <Badge variant="outline">Дека целиком</Badge>}
            {applied && (
              <Badge variant="done" className="gap-1">
                <Wand2 className="h-3 w-3" /> исправлено
              </Badge>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              aria-pressed={liked}
              aria-label="Пометить находку как полезную"
              onClick={handleLike}
              className={cn(
                "rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-background",
                liked && "bg-status-done/10 text-status-done",
              )}
            >
              <ThumbsUp className="h-4 w-4" fill={liked ? "currentColor" : "none"} />
            </button>
            <button
              type="button"
              aria-pressed={flagged}
              aria-label="Пометить находку как мусорную"
              onClick={handleFlag}
              className={cn(
                "rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-background",
                flagged && "bg-severity-critical/10 text-severity-critical",
              )}
            >
              <ThumbsDown className="h-4 w-4" fill={flagged ? "currentColor" : "none"} />
            </button>
          </div>
        </div>

        <h4 className="mt-2 font-semibold text-foreground">{finding.title}</h4>
        <p className="mt-1 text-sm text-muted-foreground">{finding.description}</p>
        <p className="mt-2 text-sm">
          <span className="font-medium">Как исправить: </span>
          {finding.fix_suggestion}
        </p>

        {finding.auto_fixable && (
          <button
            type="button"
            onClick={handleApply}
            disabled={applied || applyFix.isPending}
            className={cn(
              "mt-3 inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium transition-colors",
              applied
                ? "cursor-default border-status-done/30 bg-status-done/10 text-status-done"
                : "hover:bg-background text-foreground",
            )}
          >
            <Wand2 className="h-3.5 w-3.5" />
            {applied ? "Применено" : applyFix.isPending ? "Применяем…" : "Применить"}
          </button>
        )}
      </div>
    </Card>
  );
}
