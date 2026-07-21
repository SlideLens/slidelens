import { useState, type FormEvent } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useAuth } from "@/auth/AuthProvider";
import { ApiError } from "@/api/client";

type Mode = "login" | "register";

const emailSchema = z.string().email("Введите корректный email");
const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Введите пароль"),
});
const registerSchema = z.object({
  email: emailSchema,
  password: z.string().min(8, "Минимум 8 символов"),
});

type FieldErrors = Partial<Record<"email" | "password", string>>;
type LocationState = { from?: { pathname: string; search: string } };

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const [mode, setMode] = useState<Mode>(searchParams.get("mode") === "register" ? "register" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setFieldErrors({});
    setApiError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setApiError(null);

    const schema = mode === "login" ? loginSchema : registerSchema;
    const result = schema.safeParse({ email, password });
    if (!result.success) {
      const errors: FieldErrors = {};
      for (const issue of result.error.issues) {
        const field = issue.path[0] as "email" | "password";
        errors[field] = issue.message;
      }
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(result.data.email, result.data.password);
      } else {
        await register(result.data.email, result.data.password);
      }
      const from = (location.state as LocationState | null)?.from;
      navigate(from ? `${from.pathname}${from.search}` : "/cabinet", { replace: true });
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : "Что-то пошло не так, попробуйте ещё раз");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-sm py-10">
      <Card>
        <CardHeader>
          <div className="flex gap-1 rounded-lg bg-background p-1">
            {(["login", "register"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => switchMode(tab)}
                className={cn(
                  "flex-1 rounded-md py-1.5 text-sm font-medium transition-colors",
                  mode === tab ? "bg-card shadow-sm" : "text-muted-foreground",
                )}
              >
                {tab === "login" ? "Вход" : "Регистрация"}
              </button>
            ))}
          </div>
          <CardTitle className="pt-2 text-base font-normal text-muted-foreground">
            {mode === "login" ? "Войдите в свой аккаунт" : "Создайте аккаунт — 2 бесплатных Разбора"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-3" onSubmit={handleSubmit} noValidate>
            {apiError && (
              <p className="rounded-md bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
                {apiError}
              </p>
            )}
            <label className="flex flex-col gap-1 text-sm">
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/40"
                placeholder="you@company.com"
              />
              {fieldErrors.email && (
                <span className="text-xs text-severity-critical">{fieldErrors.email}</span>
              )}
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Пароль
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/40"
                placeholder="••••••••"
              />
              {fieldErrors.password && (
                <span className="text-xs text-severity-critical">{fieldErrors.password}</span>
              )}
            </label>
            <Button type="submit" className="mt-2" disabled={submitting}>
              {submitting
                ? "Секунду…"
                : mode === "login"
                  ? "Войти"
                  : "Зарегистрироваться"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}
