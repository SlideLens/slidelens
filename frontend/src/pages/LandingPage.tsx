import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { ReviewReport } from "@/components/report/ReviewReport";
import { reportWithAudio } from "@/fixtures/report";
import { initAnalytics, trackPlausibleEvent } from "@/lib/analytics";

export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    initAnalytics();
  }, []);

  return (
    <div className="flex flex-col gap-16">
      <section className="hero-dotgrid pb-8 pt-4 text-center sm:pt-10">
        <h1 className="mx-auto max-w-2xl text-4xl font-semibold tracking-tight text-balance">
        Загрузите Деку. Получите взгляд, которого не хватает перед сценой
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
        Загрузите Деку — получите разбор: аннотированные находки, проверка графиков на честность, сверка «речь ↔ слайды» и исправленная дека.
        </p>
        <Button
          asChild
          size="lg"
          className="mt-6"
          onClick={() => trackPlausibleEvent("cta_click")}
        >
          <Link to={isAuthenticated ? "/cabinet" : "/login?mode=register"}>
            {isAuthenticated ? "Перейти в Кабинет" : "Начать бесплатно"}
          </Link>
        </Button>
        <p className="mt-2 text-xs text-muted-foreground">2 бесплатных Разбора, без карты</p>

        <dl className="mx-auto mt-14 flex max-w-lg flex-wrap justify-center gap-x-12 gap-y-6">
          {[
            ["8", "категорий Находок"],
            ["2–5", "минут на Разбор"],
            ["3", "безопасных автофикса"],
          ].map(([n, label]) => (
            <div key={label}>
              <dt className="sr-only">{label}</dt>
              <dd className="text-2xl font-extrabold tabular-nums text-foreground">{n}</dd>
              <div className="mt-1 text-xs text-muted-foreground">{label}</div>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h2 className="text-center text-2xl font-semibold tracking-tight">Живой пример Отчёта</h2>
        <p className="mx-auto mt-2 max-w-lg text-center text-sm text-muted-foreground">
          Так выглядит Отчёт после Разбора: Скор, аннотированные слайды и Находки с
          подсказками, как исправить.
        </p>
        <div className="mt-8 rounded-xl border border-border bg-card/50 p-6">
          <ReviewReport report={reportWithAudio} showDownloads={false} interactive={false} />
        </div>
      </section>
    </div>
  );
}
