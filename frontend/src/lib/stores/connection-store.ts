import { create } from "zustand";

interface ConnectionState {
  status: "connected" | "disconnected" | "reconnecting";
  databaseType: "sqlite" | "hana";
  lastChecked: Date | null;
  setStatus: (status: "connected" | "disconnected" | "reconnecting") => void;
  setDatabaseType: (type: "sqlite" | "hana") => void;
  setLastChecked: (date: Date) => void;
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: "connected",
  databaseType: "sqlite",
  lastChecked: null,
  setStatus: (status) => set({ status }),
  setDatabaseType: (type) => set({ databaseType: type }),
  setLastChecked: (date) => set({ lastChecked: date }),
}));
