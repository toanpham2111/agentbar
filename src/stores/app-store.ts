import { create } from "zustand";

type Theme = "system" | "light" | "dark";

interface AppState {
  theme: Theme;
  monitoring: boolean;
  setTheme: (theme: Theme) => void;
  setMonitoring: (monitoring: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  theme: "system",
  monitoring: true,
  setTheme: (theme) => set({ theme }),
  setMonitoring: (monitoring) => set({ monitoring }),
}));
