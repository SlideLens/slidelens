import { useEffect, useMemo, useRef } from "react";
import { useParams } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { ApiError } from "@/api/client";
import { ReviewReport } from "@/components/report/ReviewReport";
import { Skeleton } from "@/components/ui/skeleton";
import { useReviewStatus } from "@/hooks/useReviewPolling";
import { useReport } from "@/hooks/useReport";
import { useSlides } from "@/hooks/useSlides";
import { useTrackEvent } from "@/hooks/useTrackEvent";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const { data: review, isLoading, isError, error } = useReviewStatus(id);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Отчёт</h1>

      {isError ? (
        <ErrorState
          reason={error instanceof ApiError ? error.message : "Не удалось загрузить Разбор"}
        />
      ) : isLoading || !review ? (
        <ProcessingState />
      ) : review.status === "failed" ? (
        <FailedState reason={review.fail_reason ?? "Неизвестная ошибка"} />
      ) : review.status !== "done" ? (
        <ProcessingState />
      ) : (
        <DoneReport reviewId={review.id} />
      )}
    </div>
  );
}

function DoneReport({ reviewId }: { reviewId: string }) {
  const { data: report, isLoading, isError, error } = useReport(reviewId, true);
  // Сырые слайды: по ним отчёт рисует рамки Находок сам. Запрос не блокирующий —
  // если он не удался (исходная Дека протухла), SlideViewer откатится на
  // впечатанные сервером рамки из screenshot_url.
  const { data: slides } = useSlides(reviewId);
  const trackEvent = useTrackEvent();
  const openedFor = useRef<string | null>(null);

  const slideUrls = useMemo(
    () => Object.fromEntries((slides ?? []).map((s) => [s.slide_num, s.url])),
    [slides],
  );

  useEffect(() => {
    if (report && openedFor.current !== report.review_id) {
      openedFor.current = report.review_id;
      trackEvent("report_opened", { review_id: report.review_id });
    }
  }, [report, trackEvent]);

  if (isError) {
    return (
      <ErrorState reason={error instanceof ApiError ? error.message : "Не удалось загрузить Отчёт"} />
    );
  }
  if (isLoading || !report) {
    return <ProcessingState />;
  }
  return <ReviewReport report={report} slideUrls={slideUrls} />;
}

function ProcessingState() {
  return (
    <div className="flex flex-col gap-6 rounded-lg border border-border bg-card p-8">
      <div className="text-center">
        <p className="text-lg font-medium">SlideLens изучает вашу Деку…</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Обычно 2–5 минут. Статус обновится автоматически, когда Разбор будет готов.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="aspect-video w-full" />
        <div className="flex flex-col gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    </div>
  );
}

function FailedState({ reason }: { reason: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-status-failed/30 bg-status-failed/5 px-6 py-16 text-center">
      <AlertTriangle className="h-10 w-10 text-status-failed" />
      <p className="text-lg font-medium">Разбор не удалось завершить</p>
      <p className="max-w-md text-sm text-muted-foreground">{reason}</p>
    </div>
  );
}

function ErrorState({ reason }: { reason: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-status-failed/30 bg-status-failed/5 px-6 py-16 text-center">
      <AlertTriangle className="h-10 w-10 text-status-failed" />
      <p className="text-lg font-medium">Не удалось открыть Отчёт</p>
      <p className="max-w-md text-sm text-muted-foreground">{reason}</p>
    </div>
  );
}
