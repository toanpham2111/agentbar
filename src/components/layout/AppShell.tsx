import {
  Activity,
  BellRing,
  Bot,
  ChartNoAxesCombined,
  Gauge,
  PanelLeftClose,
  Settings,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAppStore } from "../../stores/app-store";

const navigation = [
  { label: "Dashboard", path: "/dashboard", icon: Gauge },
  { label: "Analytics", path: "/analytics", icon: ChartNoAxesCombined },
  { label: "AI Providers", path: "/providers", icon: Bot },
  { label: "Alerts", path: "/alerts", icon: BellRing },
  { label: "Settings", path: "/settings", icon: Settings },
];

export function AppShell() {
  const [compact, setCompact] = useState(false);
  const monitoring = useAppStore((state) => state.monitoring);

  return (
    <div className={`app-shell ${compact ? "sidebar-compact" : ""}`}>
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand-row">
          <img src="/kio-mark.svg" width="36" height="36" alt="" />
          <div className="brand-copy">
            <strong>KIO</strong>
            <span>Usage Monitor</span>
          </div>
          <button
            className="icon-button sidebar-toggle"
            type="button"
            aria-label={compact ? "Expand sidebar" : "Collapse sidebar"}
            aria-pressed={compact}
            onClick={() => setCompact((value) => !value)}
          >
            <PanelLeftClose aria-hidden="true" size={18} />
          </button>
        </div>

        <nav className="nav-list">
          {navigation.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
              aria-label={label}
              title={compact ? label : undefined}
            >
              <Icon aria-hidden="true" size={19} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="monitor-status" role="status">
          <span className={`status-dot ${monitoring ? "online" : "offline"}`} />
          <div>
            <strong>{monitoring ? "Monitoring active" : "Monitoring paused"}</strong>
            <span>Local background service</span>
          </div>
          <Activity aria-hidden="true" size={18} />
        </div>
      </aside>

      <main className="main-content" id="main-content" tabIndex={-1}>
        {import.meta.env.DEV && import.meta.env.VITE_DEMO_MODE === "true" && (
          <div className="demo-banner" role="status">UI preview mode — all values are labeled demo fixtures.</div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
