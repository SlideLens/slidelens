import { BarChart3, CheckCircle2, Mail } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useReviewPolling } from "@/hooks/useReviewPolling";
import { pluralizeRu } from "@/lib/pluralize";

/** Total free Разбора a new account starts with — matches the backend default (app/models/entities.py). */
const FREE_PLAN_TOTAL = 2;

export default function ProfilePage() {
  const { user } = useAuth();
  const { data: reviews } = useReviewPolling();
  if (!user) return null;

  const isFree = user.plan === "free";
  const used = Math.max(0, FREE_PLAN_TOTAL - user.free_reviews_left);
  // Пробные тратятся раньше купленных, но для «можно ли запустить Разбор» важна сумма.
  const reviewsLeft = user.free_reviews_left + user.balance_reviews;

  const doneReviews = (reviews ?? []).filter((r) => r.status === "done" && r.score != null);
  const avgScore = doneReviews.length
    ? Math.round(doneReviews.reduce((sum, r) => sum + (r.score ?? 0), 0) / doneReviews.length)
    : null;
  const totalSlides = doneReviews.reduce((sum, r) => sum + (r.n_slides ?? 0), 0);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Профиль</h1>
        <p className="mt-1 text-sm text-muted-foreground">Аккаунт и план</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Mail className="h-4 w-4 text-muted-foreground" />
              Аккаунт
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div className="text-foreground">{user.email}</div>
            {user.created_at && (
              <div className="text-muted-foreground">
                Регистрация: {new Date(user.created_at).toLocaleDateString("ru-RU")}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              План
              <Badge variant={isFree ? "outline" : "done"}>{isFree ? "Бесплатный" : "Платный"}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            {user.is_admin ? (
              <div className="flex items-center gap-2 text-status-done">
                <CheckCircle2 className="h-4 w-4" />
                Безлимитные Разборы (администратор)
              </div>
            ) : (
              <>
                {isFree && (
                  <>
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>
                        Пробных использовано {used} из {FREE_PLAN_TOTAL}
                      </span>
                      <span>
                        {user.free_reviews_left}{" "}
                        {pluralizeRu(user.free_reviews_left, ["Разбор", "Разбора", "Разборов"])}{" "}
                        осталось
                      </span>
                    </div>
                    <Progress value={(used / FREE_PLAN_TOTAL) * 100} />
                  </>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">На балансе</span>
                  <span className="font-medium text-foreground">
                    {user.balance_reviews}{" "}
                    {pluralizeRu(user.balance_reviews, ["Разбор", "Разбора", "Разборов"])}
                  </span>
                </div>
                {reviewsLeft === 0 && (
                  <p className="text-muted-foreground">
                    Разборы закончились —{" "}
                    <Link to="/pricing" className="text-accent hover:underline">
                      пополните баланс
                    </Link>
                    , чтобы запустить новый.
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            Статистика
          </CardTitle>
        </CardHeader>
        <CardContent>
          {(reviews?.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">
              Пока нет завершённых Разборов — статистика появится после первого.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <div className="text-2xl font-semibold">{reviews?.length ?? 0}</div>
                <div className="text-sm text-muted-foreground">
                  {pluralizeRu(reviews?.length ?? 0, ["Разбор", "Разбора", "Разборов"])} всего
                </div>
              </div>
              <div>
                <div className="text-2xl font-semibold">{avgScore ?? "—"}</div>
                <div className="text-sm text-muted-foreground">средний Скор</div>
              </div>
              <div>
                <div className="text-2xl font-semibold">{totalSlides}</div>
                <div className="text-sm text-muted-foreground">
                  {pluralizeRu(totalSlides, ["слайд", "слайда", "слайдов"])} проанализировано
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
