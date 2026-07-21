import { useMemo, useState } from "react";
import { Download, FileDown, Loader2 } from "lucide-react";
import type { ReportOut } from "@/api/schemas";
import { apiClient, ApiError } from "@/api/client";
import { saveBlob } from "@/lib/download";
import { pluralizeRu } from "@/lib/pluralize";
import { findRecurringPatterns } from "@/lib/recurringFindings";
import { useTrackEvent } from "@/hooks/useTrackEvent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DeliveryPanel } from "@/components/report/DeliveryPanel";
import { FindingCard } from "@/components/report/FindingCard";
import { FindingFilters, applyFindingFilters, useFindingFilters } from "@/components/report/FindingFilters";
import { MismatchPanel } from "@/components/report/MismatchPanel";
import { RecurringIssuesPanel } from "@/components/report/RecurringIssuesPanel";
import { ScoreGauge } from "@/components/report/ScoreGauge";
import { SlideViewer } from "@/components/report/SlideViewer";

export interface ReviewReportProps {
  report: ReportOut;
  /** Скачивание PDF/PPTX (по умолчанию включено); выключается для фикстур без реальных файлов. */
  showDownloads?: boolean;
  /** false = 👍/👎/«Применить» работают только визуально, без запросов к API. */
  interactive?: boolean;
  /**
   * Номер слайда → URL его сырого рендера. Если передан, `SlideViewer` рисует рамки
   * Находок сам, и они подчиняются фильтрам. Без него компонент откатывается на
   * впечатанные сервером рамки из `screenshot_url` (лендинг с фикстурами, старые
   * Разборы, у которых исходная Дека уже протухла).
   */
  slideUrls?: Record<number, string>;
}

export function ReviewReport({
  report,
  showDownloads = true,
  interactive = true,
  slideUrls,
}: ReviewReportProps) {
  const [filters, setFilters] = useFindingFilters();
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"pdf" | "pptx" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const trackEvent = useTrackEvent();

  const filtered = useMemo(() => applyFindingFilters(report.findings, filters), [report.findings, filters]);

  // Stable across filtering: only bbox findings get a number (it must match the
  // pin drawn on the slide); the rest show a "Дека целиком"-style ◆ marker.
  const findingNumbers = useMemo(() => {
    const map = new Map<string, number>();
    let n = 0;
    for (const finding of report.findings) {
      if (finding.bbox) map.set(finding.id, ++n);
    }
    return map;
  }, [report.findings]);
  const numberOf = (id: string) => findingNumbers.get(id);

  const bySlide = useMemo(() => {
    const map = new Map<number, typeof filtered>();
    for (const finding of filtered) {
      if (finding.slide_num == null) continue;
      const list = map.get(finding.slide_num) ?? [];
      list.push(finding);
      map.set(finding.slide_num, list);
    }
    return [...map.entries()].sort(([a], [b]) => a - b);
  }, [filtered]);

  const deckLevel = filtered.filter((f) => f.slide_num == null);
  const recurringGroups = useMemo(() => findRecurringPatterns(filtered), [filtered]);

  function scrollToFinding(id: string) {
    setActiveFindingId(id);
    trackEvent("finding_expanded", { finding_id: id, review_id: report.review_id });
    document.getElementById(`finding-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function scrollToSlide(slideNum: number) {
    document.getElementById(`slide-${slideNum}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function handleDownload(kind: "pdf" | "pptx", assetId: string, filename: string) {
    setDownloadError(null);
    setDownloading(kind);
    try {
      const blob = await apiClient.download(`/files/${assetId}`);
      saveBlob(blob, filename);
      trackEvent(kind === "pdf" ? "pdf_downloaded" : "fixed_pptx_downloaded", {
        review_id: report.review_id,
      });
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : "Не удалось скачать файл");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <ScoreGauge score={report.score} />
          <div className="text-sm text-muted-foreground">
            <div>
              {report.n_slides} {pluralizeRu(report.n_slides, ["слайд", "слайда", "слайдов"])}
            </div>
            <div>
              {report.findings.length}{" "}
              {pluralizeRu(report.findings.length, ["Находка", "Находки", "Находок"])}
            </div>
            {report.auto_fixed_count > 0 && <div>{report.auto_fixed_count} исправлено автоматически</div>}
          </div>
        </div>
        {showDownloads && (
          <div className="flex flex-col items-end gap-1">
            <div className="flex gap-2">
              {report.pdf_asset_id && (
                <Button
                  variant="outline"
                  disabled={downloading !== null}
                  onClick={() => handleDownload("pdf", report.pdf_asset_id!, "report.pdf")}
                >
                  {downloading === "pdf" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FileDown className="h-4 w-4" />
                  )}
                  Скачать PDF-отчёт
                </Button>
              )}
              {report.fixed_pptx_asset_id && (
                <Button
                  variant="outline"
                  disabled={downloading !== null}
                  onClick={() =>
                    handleDownload(
                      "pptx",
                      report.fixed_pptx_asset_id!,
                      report.fixed_pptx_filename ?? "fixed.pptx",
                    )
                  }
                >
                  {downloading === "pptx" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Скачать исправленный PPTX
                </Button>
              )}
            </div>
            {downloadError && <p className="text-xs text-severity-critical">{downloadError}</p>}
          </div>
        )}
      </div>

      {report.findings.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card p-10 text-center">
          <p className="text-lg font-medium">Серьёзных проблем не нашли 🎉</p>
          <p className="mt-1 text-sm text-muted-foreground">
            SlideLens не обнаружил Находок в этой Деке.
          </p>
        </div>
      ) : (
        <>
          <FindingFilters value={filters} onChange={setFilters} />

          <RecurringIssuesPanel groups={recurringGroups} onSlideClick={scrollToSlide} />

          <div className="flex flex-col gap-6">
            {bySlide.map(([slideNum, slideFindings]) => (
              <div
                key={slideNum}
                id={`slide-${slideNum}`}
                className="grid gap-4 scroll-mt-24 md:grid-cols-[1.55fr_1fr]"
              >
                <SlideViewer
                  slideNum={slideNum}
                  findings={slideFindings}
                  activeFindingId={activeFindingId}
                  onFrameClick={scrollToFinding}
                  numberOf={numberOf}
                  slideUrl={slideUrls?.[slideNum]}
                />
                <div className="flex flex-col gap-3">
                  {slideFindings.map((finding) => (
                    <FindingCard
                      key={finding.id}
                      finding={finding}
                      reviewId={report.review_id}
                      isActive={finding.id === activeFindingId}
                      number={numberOf(finding.id)}
                      interactive={interactive}
                    />
                  ))}
                </div>
              </div>
            ))}

            {deckLevel.length > 0 && (
              <div className="flex flex-col gap-3">
                <h3 className="font-semibold text-foreground">Дека целиком</h3>
                {deckLevel.map((finding) => (
                  <FindingCard
                    key={finding.id}
                    finding={finding}
                    reviewId={report.review_id}
                    isActive={finding.id === activeFindingId}
                    number={numberOf(finding.id)}
                    interactive={interactive}
                  />
                ))}
              </div>
            )}

            {bySlide.length === 0 && deckLevel.length === 0 && (
              <p className="text-sm text-muted-foreground">
                По выбранным фильтрам Находок нет — попробуйте снять часть фильтров.
              </p>
            )}
          </div>
        </>
      )}

      {report.delivery && (
        <>
          <Separator />
          <div className="grid gap-4 md:grid-cols-2">
            <DeliveryPanel delivery={report.delivery} />
            <MismatchPanel findings={report.findings} />
          </div>
        </>
      )}
    </div>
  );
}
