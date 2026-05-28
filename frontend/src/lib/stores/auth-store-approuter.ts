import { create } from "zustand";
import { persist } from "zustand/middleware";

interface Role {
  id: string;
  name: string;
  display_name: string;
}

interface User {
  id: string;
  username: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
  is_superadmin: boolean;
  status: string;
  roles: Role[];
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  logout: () => void;
  hasRole: (roleName: string) => boolean;
  hasPermission: (resource: string, action: string) => boolean;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,

      setUser: (user: User | null) => {
        set({ user, isAuthenticated: !!user });
      },

      logout: () => {
        // Clear local state
        set({
          user: null,
          isAuthenticated: false,
        });

        // Redirect to AppRouter logout
        if (typeof window !== 'undefined') {
          window.location.href = '/logout';
        }
      },

      hasRole: (roleName: string) => {
        const { user } = get();
        if (!user) return false;
        if (user.is_superadmin) return true;
        return user.roles.some((r) => r.name === roleName);
      },

      hasPermission: (resource: string, action: string) => {
        const { user } = get();
        if (!user) return false;
        // Superadmin has all permissions
        if (user.is_superadmin) return true;

        // TODO: Implement client-side permission check
        // For now, rely on backend enforcement
        return true;
      },
    }),
    {
      name: "auth-storage",
    }
  )
);
