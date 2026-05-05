import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SidebarState {
  isOpen: boolean;
  toggle: () => void;
  open: () => void;
  close: () => void;
}

/**
 * Sidebar state management
 * Persists sidebar open/closed state to localStorage
 */
export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      isOpen: true, // Default to open
      toggle: () => set((state) => ({ isOpen: !state.isOpen })),
      open: () => set({ isOpen: true }),
      close: () => set({ isOpen: false }),
    }),
    {
      name: "sidebar-storage",
    }
  )
);
