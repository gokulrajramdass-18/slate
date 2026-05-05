import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ThemeState {
  theme: "light" | "dark" | "system";
  resolvedTheme: "light" | "dark";
  setTheme: (theme: "light" | "dark" | "system") => void;
  setResolvedTheme: (theme: "light" | "dark") => void;
}

/**
 * Theme state management
 * Persists theme preference to localStorage
 * Supports light, dark, and system (auto-detect) themes
 */
export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "system",
      resolvedTheme: "light", // Default resolved theme
      setTheme: (theme) => set({ theme }),
      setResolvedTheme: (theme) => set({ resolvedTheme: theme }),
    }),
    {
      name: "theme-storage",
      // Only persist the user's preference, not the resolved theme
      partialize: (state) => ({ theme: state.theme }),
    }
  )
);
