import { create } from "zustand";
import { persist } from "zustand/middleware";
import { API_BASE_URL } from "@/lib/config/api";

interface Role {
  id: string;
  name: string;
  display_name: string;
}

interface Permission {
  resource_type: string;
  action: string;
  scope: string;
}

interface User {
  id: string;
  uuid?: string;  // Backend's real user UUID — used for notification routing
  username: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
  is_superadmin: boolean;
  status: string;
  last_login?: string;
  roles: Role[];
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  permissions: Permission[];
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<void>;
  setUser: (user: User) => void;
  loadPermissions: () => Promise<void>;
  checkXsuaaSession: () => Promise<boolean>;
  hasRole: (roleName: string) => boolean;
  hasPermission: (resource: string, action: string) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      permissions: [],
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

          // Load user permissions after login
          await get().loadPermissions();
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
          permissions: [],
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

          // Reload permissions after token refresh
          await get().loadPermissions();
        } catch (error) {
          console.error("Token refresh error:", error);
          get().logout();
          throw error;
        }
      },

      setUser: (user: User) => {
        set({ user });
      },

      loadPermissions: async () => {
        const { token, user } = get();
        if (!token || !user) {
          set({ permissions: [] });
          return;
        }

        // Superadmins don't need to load permissions
        if (user.is_superadmin) {
          set({ permissions: [] });
          return;
        }

        try {
          const response = await fetch(`${API_BASE_URL}/auth/me/permissions`, {
            method: "GET",
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });

          if (response.ok) {
            const data = await response.json();
            set({ permissions: data.permissions || [] });
          } else {
            console.error("Failed to load permissions");
            set({ permissions: [] });
          }
        } catch (error) {
          console.error("Error loading permissions:", error);
          set({ permissions: [] });
        }
      },

      checkXsuaaSession: async () => {
        try {
          console.log("[AUTH] Checking XSUAA session...");

          // Check if user is authenticated via XSUAA session
          // When accessing through AppRouter (localhost:5001), it forwards JWT to backend
          // Make request to /api/auth/me - AppRouter will add Authorization header
          const response = await fetch("/api/auth/me", {
            method: "GET",
            credentials: "include", // Include cookies for XSUAA session
          });

          console.log("[AUTH] Response status:", response.status);
          console.log("[AUTH] Response OK:", response.ok);

          if (!response.ok) {
            console.log("[AUTH] No XSUAA session - not authenticated");
            return false;
          }

          // Check if response is JSON (authenticated) or HTML (redirect to XSUAA)
          const contentType = response.headers.get("content-type");
          console.log("[AUTH] Content-Type:", contentType);

          if (!contentType || !contentType.includes("application/json")) {
            // Not JSON - likely HTML redirect page from AppRouter
            console.log("[AUTH] Response is not JSON - no XSUAA session");
            return false;
          }

          // Parse JSON response
          const userData = await response.json();
          console.log("[AUTH] User data received:", userData.username);

          set({
            user: userData,
            isAuthenticated: true,
            token: "xsuaa", // Mark as XSUAA authenticated (no token stored client-side)
            refreshToken: null,
          });

          console.log("[AUTH] XSUAA session validated");
          return true;
        } catch (error) {
          console.error("[AUTH] XSUAA session check error:", error);
          return false;
        }
      },

      hasRole: (roleName: string) => {
        const { user } = get();
        if (!user) return false;
        if (user.is_superadmin) return true;
        return user.roles.some((r) => r.name === roleName);
      },

      hasPermission: (resource: string, action: string) => {
        const { user, permissions } = get();
        if (!user) return false;

        // Superadmin has all permissions
        if (user.is_superadmin) return true;

        // Check if user has permission for this resource+action
        return permissions.some(
          (p) => p.resource_type === resource && p.action === action
        );
      },
    }),
    {
      name: "auth-storage",
    }
  )
);
