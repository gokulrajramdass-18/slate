import { create } from "zustand";
import { persist } from "zustand/middleware";
import { API_BASE_URL } from "@/lib/config/api";

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
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<void>;
  setUser: (user: User) => void;
  hasRole: (roleName: string) => boolean;
  hasPermission: (resource: string, action: string) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      login: async (username: string, password: string) => {
        try {
          const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ username, password }),
          });

          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Login failed");
          }

          const data = await response.json();
          set({
            token: data.access_token,
            refreshToken: data.refresh_token,
            user: data.user,
            isAuthenticated: true,
          });
        } catch (error) {
          console.error("Login error:", error);
          throw error;
        }
      },

      logout: () => {
        // Call logout endpoint (optional, since JWT is stateless)
        const token = get().token;
        if (token) {
          fetch(`${API_BASE_URL}/auth/logout`, {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }).catch(() => {
            // Ignore errors on logout
          });
        }

        set({
          token: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        });
      },

      refreshAccessToken: async () => {
        const { refreshToken } = get();
        if (!refreshToken) {
          throw new Error("No refresh token available");
        }

        try {
          const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });

          if (!response.ok) {
            // Refresh failed, logout
            get().logout();
            throw new Error("Token refresh failed");
          }

          const data = await response.json();
          set({
            token: data.access_token,
            user: data.user,
          });
        } catch (error) {
          console.error("Token refresh error:", error);
          get().logout();
          throw error;
        }
      },

      setUser: (user: User) => {
        set({ user });
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
