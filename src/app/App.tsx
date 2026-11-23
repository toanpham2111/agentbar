import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { useAppStore } from "../stores/app-store";

const DashboardPage = lazy(() => import("../pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const AnalyticsPage = lazy(() => import("../pages/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })));
const ProvidersPage = lazy(() => import("../pages/ProvidersPage").then((module) => ({ default: module.ProvidersPage })));
const AlertsPage = lazy(() => import("../pages/AlertsPage").then((module) => ({ default: module.AlertsPage })));
const SettingsPage = lazy(() => import("../pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));

export function App() {
  const theme = useAppStore((state) => state.theme);

  useEffect(() => {
    const root = document.documentElement;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const dark = theme === "dark" || (theme === "system" && media.matches);
      root.dataset.theme = dark ? "dark" : "light";
    };
    applyTheme();
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [theme]);

  return (
    <Suspense fallback={<div className="app-loading" role="status">Loading KIO Usage Monitor…</div>}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/providers" element={<ProvidersPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
