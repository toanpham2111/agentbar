import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Moon, Save, Sun, SunMoon } from "lucide-react";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { ErrorState, LoadingState } from "../components/ui/QueryState";
import { monitorApi } from "../lib/api";
import { useAppStore } from "../stores/app-store";
import type { Settings } from "../types/usage";

export function SettingsPage() {
  const query = useQuery({ queryKey: ["settings"], queryFn: monitorApi.getSettings });
  const [draft, setDraft] = useState<Settings | null>(null);
  const setTheme = useAppStore((state) => state.setTheme);
  const save = useMutation({ mutationFn: monitorApi.updateSettings, onSuccess: setDraft });

  useEffect(() => { if (query.data) setDraft(query.data); }, [query.data]);

  if (query.isLoading) return <div className="page-wrap"><LoadingState label="Loading settings" /></div>;
  if (query.error || !draft) return <div className="page-wrap"><ErrorState message={query.error?.message ?? "Settings are unavailable."} onRetry={() => void query.refetch()} /></div>;

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => setDraft({ ...draft, [key]: value });

  return (
    <div className="page-wrap">
      <PageHeader eyebrow="Application preferences" title="Settings" description="Configure local monitoring, notifications, theme, and startup behavior." actions={<Button onClick={() => save.mutate(draft)} disabled={save.isPending}><Save aria-hidden="true" size={16} />{save.isPending ? "Saving" : "Save changes"}</Button>} />
      <section className="settings-card">
        <div className="settings-row"><div><h2>Refresh interval</h2><p>Collectors skip overlapping runs and respect provider limits.</p></div><select aria-label="Refresh interval" value={draft.refreshIntervalMinutes} onChange={(event) => update("refreshIntervalMinutes", Number(event.target.value) as Settings["refreshIntervalMinutes"])}>{[1, 5, 15, 30].map((value) => <option key={value} value={value}>{value} minute{value > 1 ? "s" : ""}</option>)}</select></div>
        <div className="settings-row"><div><h2>Theme</h2><p>System mode follows the operating system preference.</p></div><div className="theme-options">{(["system", "light", "dark"] as const).map((value) => { const Icon = value === "light" ? Sun : value === "dark" ? Moon : SunMoon; return <Button key={value} variant={draft.theme === value ? "primary" : "secondary"} aria-pressed={draft.theme === value} onClick={() => { update("theme", value); setTheme(value); }}><Icon aria-hidden="true" size={15} />{value}</Button>; })}</div></div>
        {[{ key: "notificationsEnabled", title: "Desktop notifications", description: "Notify only for verified quota thresholds." }, { key: "startOnLogin", title: "Start on login", description: "Launch monitoring without administrator privileges." }, { key: "closeToTray", title: "Close to tray", description: "Keep the scheduler active when the main window closes." }].map((item) => <label className="settings-row" key={item.key}><div><h2>{item.title}</h2><p>{item.description}</p></div><input className="switch" type="checkbox" checked={Boolean(draft[item.key as keyof Settings])} onChange={(event) => update(item.key as keyof Settings, event.target.checked as never)} /></label>)}
      </section>
    </div>
  );
}
