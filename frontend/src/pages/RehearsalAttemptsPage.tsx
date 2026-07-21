import { useState } from "react";
import { ArrowLeft, Loader2, Mic, Trash2, TriangleAlert } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import type { RehearsalOut } from "@/api/schemas";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDeleteRehearsal } from "@/hooks/useDeleteRehearsal";
import { useRehearsals } from "@/hooks/useRehearsalPolling";
import { useReviewStatus } from "@/hooks/useReviewPolling";

const STATUS_LABELS: Record<RehearsalOut["status"], string> = {
  queued: "В очереди",
  processing: "Обрабатывается",
  done: "Готово",
  failed: "Ошибка",
};

export default function RehearsalAttemptsPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const navigate = useNavigate();
  const { data: review } = useReviewStatus(reviewId);
  const { data: attempts, isLoading, isError, error } = useRehearsals(reviewId);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to="/rehearsal"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Все Деки
        </Link>
        <div className="mt-2 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Репетиция</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {review?.deck_filename ?? "Дека"}
            </p>
          </div>
          <Button onClick={() => navigate(`/rehearsal/${reviewId}/new`)}>
            <Mic className="h-4 w-4" />
            Записать новую попытку
          </Button>
        </div>
      </div>

      {isError ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-status-failed/30 bg-status-failed/5 px-6 py-16 text-center">
          <TriangleAlert className="h-10 w-10 text-status-failed" />
          <p className="text-lg font-medium">Не удалось загрузить попытки</p>
          <p className="max-w-md text-sm text-muted-foreground">
            {error instanceof ApiError ? error.message : "Попробуйте обновить страницу"}
          </p>
        </div>
      ) : isLoading ? (
        <div className="flex flex-col gap-3">
          {[1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : !attempts || attempts.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border bg-card px-6 py-16 text-center">
          <Mic className="h-10 w-10 text-muted-foreground" />
          <p className="font-medium">Пока нет попыток</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Запишите первую репетицию — отчёт останется здесь и не пропадёт при уходе со
            страницы.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {[...attempts].reverse().map((attempt) => (
            <AttemptRow key={attempt.id} reviewId={reviewId!} attempt={attempt} />
          ))}
        </div>
      )}
    </div>
  );
}

function AttemptRow({ reviewId, attempt }: { reviewId: string; attempt: RehearsalOut }) {
  const [confirming, setConfirming] = useState(false);
  const deleteRehearsal = useDeleteRehearsal(reviewId);

  return (
    <Card className="flex items-center justify-between gap-4 p-4">
      <Link
        to={`/rehearsal/${reviewId}/attempts/${attempt.id}`}
        className="flex-1 transition-colors hover:text-foreground"
      >
        <div className="font-medium text-foreground">Попытка №{attempt.attempt_num}</div>
        <div className="text-sm text-muted-foreground">
          {new Date(attempt.created_at).toLocaleString("ru-RU")}
        </div>
      </Link>

      <Badge variant={attempt.status}>{STATUS_LABELS[attempt.status]}</Badge>

      {confirming ? (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Удалить?</span>
          <Button
            variant="destructive"
            size="sm"
            disabled={deleteRehearsal.isPending}
            onClick={() => deleteRehearsal.mutate(attempt.id)}
          >
            {deleteRehearsal.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Да"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setConfirming(false)}>
            Нет
          </Button>
        </div>
      ) : (
        <button
          type="button"
          aria-label="Удалить попытку"
          onClick={() => setConfirming(true)}
          className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-background hover:text-severity-critical"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      )}

      {deleteRehearsal.isError && (
        <p className="text-xs text-severity-critical">
          {deleteRehearsal.error instanceof ApiError
            ? deleteRehearsal.error.message
            : "Не удалось удалить"}
        </p>
      )}
    </Card>
  );
}
