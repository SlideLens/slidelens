import { Inbox, TriangleAlert } from "lucide-react";
import { ReviewCard } from "@/components/cabinet/ReviewCard";
import { UploadDropzone } from "@/components/cabinet/UploadDropzone";
import { Skeleton } from "@/components/ui/skeleton";
import { useReviewPolling } from "@/hooks/useReviewPolling";

export default function CabinetPage() {
  const { data: reviews, isLoading, isError } = useReviewPolling();

  return (
    <div className="flex flex-col gap-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Кабинет</h1>
        <p className="mt-1 text-sm text-muted-foreground">Ваши Разборы и загрузка новой Деки</p>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-semibold">Новый Разбор</h2>
        <UploadDropzone />
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold">Разборы</h2>
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border bg-card px-6 py-16 text-center">
            <TriangleAlert className="h-10 w-10 text-severity-critical" />
            <p className="font-medium">Не удалось загрузить Разборы</p>
            <p className="max-w-sm text-sm text-muted-foreground">Попробуйте обновить страницу.</p>
          </div>
        ) : !reviews || reviews.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border bg-card px-6 py-16 text-center">
            <Inbox className="h-10 w-10 text-muted-foreground" />
            <p className="font-medium">Пока нет Разборов</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Загрузите первую Деку выше — после завершения Разбора он появится здесь.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {reviews.map((review) => (
              <ReviewCard key={review.id} review={review} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
