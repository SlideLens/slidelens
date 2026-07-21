import { ArrowDown, ArrowUp, Minus, TriangleAlert } from "lucide-react";
import { ApiError } from "@/api/client";
import type { RehearsalFinding as RehearsalFindingType, TimingMapEntry } from "@/api/schemas";
import { DeliveryPanel } from "@/components/report/DeliveryPanel";
import { CATEGORY_LABELS, SEVERITY_BADGE_VARIANT, SEVERITY_LABELS } from "@/components/report/labels";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRehearsalReport } from "@/hooks/useRehearsalReport";
import { pluralizeRu } from "@/lib/pluralize";

export interface RehearsalReportViewProps {
  rehearsalId: string;
}

export function RehearsalReportView({ rehearsalId }: RehearsalReportViewProps) {
  const { data: report, isLoading, isError, error } = useRehearsalReport(rehearsalId, true);

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-status-failed/30 bg-status-failed/5 px-6 py-16 text-center">
        <TriangleAlert className="h-10 w-10 text-status-failed" />
        <p className="text-lg font-medium">Не удалось открыть отчёт репетиции</p>
        <p className="max-w-md text-sm text-muted-foreground">
          {error instanceof ApiError ? error.message : "Попробуйте обновить страницу"}
        </p>
      </div>
    );
  }

  if (isLoading || !report) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {report.delta && <DeltaPanel delta={report.delta} />}
      {report.delivery && <DeliveryPanel delivery={report.delivery} />}
      {report.timing_map.length > 0 && <TimingMap entries={report.timing_map} />}
      {report.findings.length > 0 ? (
        <div className="flex flex-col gap-3">
          <h3 className="font-semibold text-foreground">Находки репетиции</h3>
          {report.findings.map((finding) => (
            <RehearsalFindingCard key={finding.id} finding={finding} />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border bg-card p-10 text-center">
          <p className="text-lg font-medium">Явных проблем в подаче не нашли 🎉</p>
        </div>
      )}
    </div>
  );
}

function TimingMap({ entries }: { entries: TimingMapEntry[] }) {
  const maxDuration = Math.max(...entries.map((e) => e.duration), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Карта тайминга</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {entries.map((entry) => (
          <div key={entry.slide_num} className="flex items-center gap-3 text-sm">
            <span className="w-16 shrink-0 text-muted-foreground">Слайд {entry.slide_num}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-border">
              <div
                className={
                  "h-full rounded-full " +
                  (entry.pacing === "swamp"
                    ? "bg-severity-critical"
                    : entry.pacing === "stub"
                      ? "bg-severity-major"
                      : "bg-accent")
                }
                style={{ width: `${Math.max(4, (entry.duration / maxDuration) * 100)}%` }}
              />
            </div>
            <span className="w-12 shrink-0 text-right text-muted-foreground">
              {Math.round(entry.duration)} с
            </span>
            {entry.pacing === "swamp" && <Badge variant="critical">болото</Badge>}
            {entry.pacing === "stub" && <Badge variant="major">заглушка</Badge>}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function RehearsalFindingCard({ finding }: { finding: RehearsalFindingType }) {
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={SEVERITY_BADGE_VARIANT[finding.severity]}>{SEVERITY_LABELS[finding.severity]}</Badge>
        <Badge variant="outline">{CATEGORY_LABELS[finding.category]}</Badge>
        {finding.slide_num != null && <Badge variant="outline">Слайд {finding.slide_num}</Badge>}
      </div>
      <h4 className="mt-2 font-semibold text-foreground">{finding.title}</h4>
      <p className="mt-1 text-sm text-muted-foreground">{finding.description}</p>
      <p className="mt-2 text-sm">
        <span className="font-medium">Как исправить: </span>
        {finding.fix_suggestion}
      </p>
    </Card>
  );
}

function DeltaTrend({ value, betterWhenLower }: { value: number; betterWhenLower: boolean }) {
  if (Math.round(value) === 0) return <Minus className="h-4 w-4 text-muted-foreground" />;
  const isImprovement = betterWhenLower ? value < 0 : value > 0;
  const Icon = value > 0 ? ArrowUp : ArrowDown;
  return (
    <Icon className={`h-4 w-4 ${isImprovement ? "text-status-done" : "text-severity-critical"}`} />
  );
}

function DeltaPanel({
  delta,
}: {
  delta: NonNullable<import("@/api/schemas").RehearsalReportOut["delta"]>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Прогресс с попытки №{delta.previous_attempt_num}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        <div className="flex items-center gap-2">
          <DeltaTrend value={delta.words_per_minute_delta} betterWhenLower={false} />
          <div>
            <div className="text-lg font-semibold">
              {delta.words_per_minute_delta > 0 ? "+" : ""}
              {Math.round(delta.words_per_minute_delta)}
            </div>
            <div className="text-xs text-muted-foreground">слов/мин</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <DeltaTrend value={delta.filler_words_delta} betterWhenLower />
          <div>
            <div className="text-lg font-semibold">
              {delta.filler_words_delta > 0 ? "+" : ""}
              {delta.filler_words_delta}
            </div>
            <div className="text-xs text-muted-foreground">
              {pluralizeRu(Math.abs(delta.filler_words_delta), [
                "слово-паразит",
                "слова-паразита",
                "слов-паразитов",
              ])}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <DeltaTrend value={delta.long_pauses_delta} betterWhenLower />
          <div>
            <div className="text-lg font-semibold">
              {delta.long_pauses_delta > 0 ? "+" : ""}
              {delta.long_pauses_delta}
            </div>
            <div className="text-xs text-muted-foreground">
              {pluralizeRu(Math.abs(delta.long_pauses_delta), [
                "длинная пауза",
                "длинные паузы",
                "длинных пауз",
              ])}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
