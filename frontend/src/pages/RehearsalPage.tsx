import { useState } from "react";
import { History, Loader2, Mic, Trash2, Upload } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDeleteReview } from "@/hooks/useDeleteReview";
import { useReviewPolling } from "@/hooks/useReviewPolling";
import { pluralizeRu } from "@/lib/pluralize";

export default function RehearsalPage() {
  const { data: reviews, isLoading } = useReviewPolling();
  const doneReviews = (reviews ?? []).filter((r) => r.status === "done");

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Репетиция</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Выберите готовую Деку, чтобы записать репетицию.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/cabinet">
            <Upload className="h-3.5 w-3.5" />
            Загрузить новую Деку
          </Link>
        </Button>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-semibold">Готовые Деки</h2>
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : doneReviews.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border bg-card px-6 py-16 text-center">
            <Mic className="h-10 w-10 text-muted-foreground" />
            <p className="font-medium">Пока нет готовых Разборов</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Загрузите Деку в Кабинете и дождитесь Разбора — затем сможете отрепетировать
              питч по её слайдам.
            </p>
            <Button asChild size="sm" className="mt-1">
              <Link to="/cabinet">
                <Upload className="h-3.5 w-3.5" />
                Перейти в Кабинет
              </Link>
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {doneReviews.map((review) => (
              <DeckCard key={review.id} review={review} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function DeckCard({ review }: { review: ReviewOut }) {
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const deleteReview = useDeleteReview();

  if (confirming) {
    return (
      <Card className="flex h-full flex-col justify-between border-severity-critical/30 bg-severity-critical/5">
        <CardContent className="pt-5 text-sm">
          <p className="font-medium text-foreground">Удалить «{review.deck_filename}»?</p>
          <p className="mt-1 text-muted-foreground">
            Пропадёт весь Разбор, скачанные файлы и все попытки репетиции по этой Деке.
            Отменить будет нельзя.
          </p>
          {deleteReview.isError && (
            <p className="mt-2 text-severity-critical">
              {deleteReview.error instanceof ApiError
                ? deleteReview.error.message
                : "Не удалось удалить"}
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
            {deleteReview.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              "Да, удалить"
            )}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setConfirming(false)}>
            Отмена
          </Button>
        </CardFooter>
      </Card>
    );
  }

  return (
    <Card className="flex h-full flex-col justify-between">
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <CardTitle className="truncate text-base">{review.deck_filename ?? "Дека"}</CardTitle>
        <button
          type="button"
          aria-label="Удалить Деку"
          onClick={() => setConfirming(true)}
          className="shrink-0 rounded-full p-1 text-muted-foreground transition-colors hover:bg-background hover:text-severity-critical"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        {review.n_slides != null && (
          <div>
            {review.n_slides} {pluralizeRu(review.n_slides, ["слайд", "слайда", "слайдов"])}
          </div>
        )}
      </CardContent>
      <CardFooter className="flex-wrap gap-2">
        <Button size="sm" onClick={() => navigate(`/rehearsal/${review.id}/new`)}>
          <Mic className="h-3.5 w-3.5" />
          Записать репетицию
        </Button>
        <Button variant="outline" size="sm" onClick={() => navigate(`/rehearsal/${review.id}`)}>
          <History className="h-3.5 w-3.5" />
          Все попытки
        </Button>
      </CardFooter>
    </Card>
  );
}
