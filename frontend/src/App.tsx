import { Mail } from "lucide-react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { RequireAuth } from "@/auth/RequireAuth";
import { useAuth } from "@/auth/AuthProvider";
import CabinetPage from "./pages/CabinetPage";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import PricingPage from "./pages/PricingPage";
import ProfilePage from "./pages/ProfilePage";
import RehearsalAttemptsPage from "./pages/RehearsalAttemptsPage";
import RehearsalPage from "./pages/RehearsalPage";
import RehearsalRecordPage from "./pages/RehearsalRecordPage";
import RehearsalReportPage from "./pages/RehearsalReportPage";
import ReportPage from "./pages/ReportPage";

function HeaderNav() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <nav className="mx-auto flex max-w-7xl flex-wrap items-center gap-6 text-sm">
      <Link className="flex items-center gap-2 font-semibold text-foreground" to="/">
        <span className="flex h-5 w-5 items-center justify-center rounded bg-primary text-primary-foreground">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round">
            <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
          </svg>
        </span>
        SlideLens
      </Link>
      {isAuthenticated && (
        <>
          <Link className="font-medium text-muted-foreground hover:text-foreground" to="/cabinet">
            Кабинет
          </Link>
          <Link className="font-medium text-muted-foreground hover:text-foreground" to="/rehearsal">
            Репетиция
          </Link>
        </>
      )}
      <Link className="font-medium text-muted-foreground hover:text-foreground" to="/pricing">
        Тарифы
      </Link>
      <div className="ml-auto flex items-center gap-4">
        {isAuthenticated ? (
          <>
            <Link className="text-muted-foreground hover:text-foreground" to="/profile">
              {user?.email}
            </Link>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => {
                logout();
                navigate("/");
              }}
            >
              Выход
            </button>
          </>
        ) : (
          <Link className="text-muted-foreground hover:text-foreground" to="/login">
            Войти
          </Link>
        )}
      </div>
    </nav>
  );
}

const SUPPORT_EMAIL = "midavnibush@gmail.com";

function SiteFooter() {
  return (
    <footer className="border-t border-border bg-card px-6 py-6">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 text-sm text-muted-foreground sm:flex-row">
        <span>© {new Date().getFullYear()} SlideLens</span>
        <a
          href={`mailto:${SUPPORT_EMAIL}`}
          className="flex items-center gap-1.5 hover:text-foreground"
        >
          <Mail className="h-3.5 w-3.5" />
          {SUPPORT_EMAIL}
        </a>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-card px-6 py-4">
        <HeaderNav />
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-10">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route
            path="/cabinet"
            element={
              <RequireAuth>
                <CabinetPage />
              </RequireAuth>
            }
          />
          <Route
            path="/reviews/:id"
            element={
              <RequireAuth>
                <ReportPage />
              </RequireAuth>
            }
          />
          <Route
            path="/rehearsal"
            element={
              <RequireAuth>
                <RehearsalPage />
              </RequireAuth>
            }
          />
          <Route
            path="/rehearsal/:reviewId"
            element={
              <RequireAuth>
                <RehearsalAttemptsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/rehearsal/:reviewId/new"
            element={
              <RequireAuth>
                <RehearsalRecordPage />
              </RequireAuth>
            }
          />
          <Route
            path="/rehearsal/:reviewId/attempts/:rehearsalId"
            element={
              <RequireAuth>
                <RehearsalReportPage />
              </RequireAuth>
            }
          />
          <Route
            path="/profile"
            element={
              <RequireAuth>
                <ProfilePage />
              </RequireAuth>
            }
          />
        </Routes>
      </main>
      <SiteFooter />
    </div>
  );
}
