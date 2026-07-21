import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Clock, Info, Layers } from "lucide-react";
import { useAuth } from "@/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { pluralizeRu } from "@/lib/pluralize";
import { cn } from "@/lib/utils";

/** Лимиты одного Разбора — держим синхронно с core/constants.py
 * (MAX_DECK_SLIDES, MAX_AUDIO_MINUTES). Показываем до оплаты, а не после. */
const MAX_SLIDES = 25;
const MAX_AUDIO_MINUTES = 30;

/** Разбор — единица списания: пакет пополняет balance_reviews у пользователя. */
interface Pack {
  id: string;
  reviews: number;
  priceRub: number;
  highlighted?: boolean;
}

const PACKS: Pack[] = [
  { id: "single", reviews: 1, priceRub: 149 },
  { id: "five", reviews: 5, priceRub: 595, highlighted: true },
  { id: "twenty", reviews: 20, priceRub: 1980 },
];

const INCLUDED = [
  "Аннотированные Находки по каждому слайду",
  "Проверка графиков на честность",
  "Сверка «речь ↔ слайды» по записи питча",
  "Исправленная Дека и PDF-отчёт",
];

function formatRub(value: number) {
  return `${value.toLocaleString("ru-RU")} ₽`;
}

function perReview(pack: Pack) {
  return Math.round(pack.priceRub / pack.reviews);
}

export default function PricingPage() {
  const { isAuthenticated } = useAuth();
  const [pendingPack, setPendingPack] = useState<string | null>(null);

  const cheapest = Math.min(...PACKS.map(perReview));

  return (
    <div className="flex flex-col gap-12">
      <section className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Тарифы</h1>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          Платите за Разборы, а не за подписку. Купленные Разборы не сгорают — расходуйте
          когда удобно.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {PACKS.map((pack) => {
          const saves = perReview(pack) < PACKS[0].priceRub;
          return (
            <Card
              key={pack.id}
              className={cn(
                "flex flex-col",
                pack.highlighted && "border-accent shadow-sm ring-1 ring-accent/30",
              )}
            >
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-base">
                  <span>
                    {pack.reviews}{" "}
                    {pluralizeRu(pack.reviews, ["Разбор", "Разбора", "Разборов"])}
                  </span>
                  {pack.highlighted && <Badge variant="accent">Выгодно</Badge>}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-4">
                <div>
                  <div className="text-3xl font-semibold tabular-nums">
                    {formatRub(pack.priceRub)}
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {formatRub(perReview(pack))} за Разбор
                    {saves && perReview(pack) === cheapest && " — лучшая цена"}
                  </div>
                </div>
                <Button
                  className="mt-auto w-full"
                  variant={pack.highlighted ? "default" : "outline"}
                  onClick={() => setPendingPack(pack.id)}
                >
                  Купить
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </section>

      {pendingPack && (
        <div
          role="status"
          className="rounded-lg border border-accent/40 bg-accent/5 px-4 py-3 text-sm"
        >
          <div className="flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
            <div>
              <p className="font-medium text-foreground">Оплата пока не подключена</p>
              <p className="mt-1 text-muted-foreground">
                Мы ещё не запустили приём платежей. Напишите на{" "}
                <a className="text-accent hover:underline" href="mailto:midavnibush@gmail.com">
                  midavnibush@gmail.com
                </a>{" "}
                — пополним баланс вручную.
              </p>
            </div>
          </div>
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Что входит в каждый Разбор</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2 text-sm">
              {INCLUDED.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-status-done" />
                  <span className="text-muted-foreground">{item}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Ограничения одного Разбора</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <div className="flex items-start gap-2">
              <Layers className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="text-muted-foreground">
                Дека до <span className="font-medium text-foreground">{MAX_SLIDES} слайдов</span>,
                PPTX или PDF до 50 МБ
              </span>
            </div>
            <div className="flex items-start gap-2">
              <Clock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="text-muted-foreground">
                Запись питча до{" "}
                <span className="font-medium text-foreground">
                  {MAX_AUDIO_MINUTES} минут
                </span>
                , это опционально
              </span>
            </div>
            <p className="text-muted-foreground">
              Если Разбор не удался, списанный Разбор возвращается на баланс автоматически.
            </p>
          </CardContent>
        </Card>
      </section>

      <section className="rounded-xl border border-dashed border-border bg-card/50 px-6 py-8 text-center">
        <h2 className="text-lg font-medium">Сначала попробуйте бесплатно</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          При регистрации даём 2 Разбора без карты — этого хватит, чтобы понять, стоит ли
          платить.
        </p>
        <Button asChild className="mt-5" variant={isAuthenticated ? "outline" : "default"}>
          <Link to={isAuthenticated ? "/cabinet" : "/login?mode=register"}>
            {isAuthenticated ? "Перейти в Кабинет" : "Начать бесплатно"}
          </Link>
        </Button>
      </section>
    </div>
  );
}
