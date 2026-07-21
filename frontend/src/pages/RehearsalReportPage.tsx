import { useState } from "react";
import { AlertTriangle, ArrowLeft, Download, Loader2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiClient, ApiError } from "@/api/client";
import { RehearsalReportView } from "@/components/rehearsal/RehearsalReportView";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { saveBlob } from "@/lib/download";
import { useRehearsalStatus } from "@/hooks/useRehearsalPolling";
import { useTrackEvent } from "@/hooks/useTrackEvent";

export default function RehearsalReportPage() {
  const { reviewId, rehearsalId } = useParams<{ reviewId: string; rehearsalId: string }>();
  const navigate = useNavigate();
  const { data: rehearsal, isLoading, isError, error } = useRehearsalStatus(rehearsalId);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const trackEvent = useTrackEvent();

  async function handleDownloadAudio() {
    if (!rehearsal) return;
    setDownloadError(null);
    setDownloading(true);
    try {
      const blob = await apiClient.download(`/rehearsals/${rehearsal.id}/audio`);
      saveBlob(blob, `репетиция_попытка№${rehearsal.attempt_num}.webm`);
      trackEvent("rehearsal_audio_downloaded", { rehearsal_id: rehearsal.id });
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : "Не удалось скачать запись");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to={`/rehearsal/${reviewId}`}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Все попытки
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Репетиция</h1>
            {rehearsal && (
              <p className="mt-1 text-sm text-muted-foreground">Попытка №{rehearsal.attempt_num}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-1">
            <div className="flex gap-2">
              {rehearsal && (
                <Button variant="outline" disabled={downloading} onClick={handleDownloadAudio}>
                  {downloading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Скачать запись
                </Button>
              )}
              <Button variant="outline" onClick={() => navigate(`/rehearsal/${reviewId}/new`)}>
                Новая репетиция
              </Button>
            </div>
            {downloadError && <p className="text-xs text-severity-critical">{downloadError}</p>}
          </div>
        </div>
      </div>

      {isError ? (
        <ErrorState reason={error instanceof ApiError ? error.message : "Не удалось загрузить репетицию"} />
      ) : isLoading || !rehearsal ? (
        <ProcessingState />
      ) : rehearsal.status === "failed" ? (
        <FailedState reason={rehearsal.fail_reason ?? "Неизвестная ошибка"} />
      ) : rehearsal.status !== "done" ? (
        <ProcessingState />
      ) : (
        <RehearsalReportView rehearsalId={rehearsal.id} />
      )}
    </div>
  );
}

function ProcessingState() {
  return (
    <div className="flex flex-col gap-6 rounded-lg border border-border bg-card p-8">
      <div className="text-center">
        <p className="text-lg font-medium">SlideLens разбирает вашу репетицию…</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Обычно 1-2 минуты. Статус обновится автоматически.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  );
}

function FailedState({ reason }: { reason: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-status-failed/30 bg-status-failed/5 px-6 py-16 text-center">
      <AlertTriangle className="h-10 w-10 text-status-failed" />
      <p className="text-lg font-medium">Репетицию не удалось обработать</p>
      <p className="max-w-md text-sm text-muted-foreground">{reason}</p>
    </div>
  );
}

function ErrorState({ reason }: { reason: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-status-failed/30 bg-status-failed/5 px-6 py-16 text-center">
      <AlertTriangle className="h-10 w-10 text-status-failed" />
      <p className="text-lg font-medium">Не удалось открыть репетицию</p>
      <p className="max-w-md text-sm text-muted-foreground">{reason}</p>
    </div>
  );
}
