import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CalendarDays, FileText, Loader2, Trash2 } from "lucide-react";
import { ApiError } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { bandColor } from "@/components/report/ScoreGauge";
import { useDeleteReview } from "@/hooks/useDeleteReview";
import { pluralizeRu } from "@/lib/pluralize";

const STATUS_LABELS: Record<ReviewOut["status"], string> = {
  queued: "В очереди",
  processing: "Разбирается",
  done: "Готово",
  failed: "Ошибка",
};

function formatUploadDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export interface ReviewCardProps {
  review: ReviewOut;
}

export function ReviewCard({ review }: ReviewCardProps) {
  const [confirming, setConfirming] = useState(false);
  const deleteReview = useDeleteReview();

  if (confirming) {
    return (
      <Card className="flex h-full flex-col justify-between border-severity-critical/30 bg-severity-critical/5">
        <CardContent className="pt-5 text-sm">
          <p className="font-medium text-foreground">Удалить «{review.deck_filename ?? "Дека"}»?</p>
          <p className="mt-1 text-muted-foreground">
            Пропадёт весь Разбор, скачанные файлы и Находки. Отменить будет нельзя.
          </p>
          {deleteReview.isError && (
            <p className="mt-2 text-severity-critical">
              {deleteReview.error instanceof ApiError ? deleteReview.error.message : "Не удалось удалить"}
            </p>
          )}
        </CardContent>
        <CardFooter className="gap-2">
          <Button
            variant="destructive"
            size="sm"
            disabled={deleteReview.isPending}
            onClick={() => deleteReview.mutate(review.id)}
          >
            {deleteReview.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Да, удалить"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setConfirming(false)}>
            Отмена
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card className="relative h-full transition-shadow hover:shadow-md">
      <button
        type="button"
        aria-label="Удалить Разбор"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setConfirming(true);
        }}
        className="absolute right-3 top-3 z-10 rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-background hover:text-severity-critical"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
      <Link to={`/reviews/${review.id}`} className="block h-full">
        <CardHeader className="flex-row items-start justify-between gap-2 space-y-0 pr-9">
          <div className="flex items-center gap-2 overflow-hidden">
            <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
            <CardTitle className="truncate font-mono text-sm font-semibold">
              {review.deck_filename ?? "Дека"}
            </CardTitle>
          </div>
          <Badge variant={review.status} className="shrink-0 gap-1">
            {review.status === "processing" && <Loader2 className="h-3 w-3 animate-spin" />}
            {STATUS_LABELS[review.status]}
          </Badge>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm text-muted-foreground">
          {review.status === "done" && review.score != null && (
            <div className="flex items-center gap-2">
              <span
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 font-mono text-xs font-bold"
                style={{ borderColor: bandColor(review.score), color: bandColor(review.score) }}
              >
                {review.score}
              </span>
              <span>Скор</span>
            </div>
          )}
          {review.status === "failed" && review.fail_reason && (
            <div className="flex items-start gap-1.5 text-severity-critical">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{review.fail_reason}</span>
            </div>
          )}
          {review.n_slides != null && (
            <div>
              {review.n_slides} {pluralizeRu(review.n_slides, ["слайд", "слайда", "слайдов"])}
            </div>
          )}
          <div className="flex gap-2">
            {review.has_audio && <Badge variant="outline">запись питча</Badge>}
            {review.has_data && <Badge variant="outline">Excel</Badge>}
          </div>
          <div className="mt-1 flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground/80">
            <CalendarDays className="h-3 w-3" />
            загружено {formatUploadDate(review.created_at)}
          </div>
        </CardContent>
      </Link>
    </Card>
  );
}
