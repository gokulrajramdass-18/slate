"use client";

import { useEffect, ReactNode, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useRouter, usePathname } from "@/lib/routing/navigation";
import { useAuthStore } from "@/lib/stores/auth-store";

interface AuthGuardProps {
  children: ReactNode;
  requireAuth?: boolean;
  redirectTo?: string;
}

/**
 * AuthGuard component - Protects routes that require authentication
 *
 * Usage:
 * ```tsx
 * <AuthGuard>
 *   <ProtectedContent />
 * </AuthGuard>
 * ```
 *
 * Or wrap entire layout:
 * ```tsx
 * <AuthGuard requireAuth={true} redirectTo="/login">
 *   {children}
 * </AuthGuard>
 * ```
 */
export function AuthGuard({
  children,
  requireAuth = true,
  redirectTo = "/login",
}: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, token, loadPermissions, checkXsuaaSession } = useAuthStore();
  const [isHydrated, setIsHydrated] = useState(false);
  const [isCheckingXsuaa, setIsCheckingXsuaa] = useState(false);
  const [xsuaaChecked, setXsuaaChecked] = useState(false);

  // Check if XSUAA is enabled
  const isAppRouter = typeof window !== "undefined" && (window.location.port === "5001" || window.location.port === "5000");
  const isXsuaaEnabled = typeof window !== "undefined" && import.meta.env.VITE_XSUAA_ENABLED === "true";

  // Wait for Zustand to hydrate from localStorage
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Check for XSUAA session on mount if XSUAA is enabled
  useEffect(() => {
    if (!isHydrated) return;
    if (!(isAppRouter || isXsuaaEnabled)) return;
    if (isCheckingXsuaa || xsuaaChecked) return;

    console.log("[AuthGuard] XSUAA enabled - checking session...");
    setIsCheckingXsuaa(true);

    checkXsuaaSession()
      .then((hasSession) => {
        console.log("[AuthGuard] XSUAA session check result:", hasSession);
        setXsuaaChecked(true);
      })
      .catch((error) => {
        console.error("[AuthGuard] XSUAA session check error:", error);
        setXsuaaChecked(true);
      })
      .finally(() => {
        setIsCheckingXsuaa(false);
      });
  }, [isHydrated, isAppRouter, isXsuaaEnabled, checkXsuaaSession, isCheckingXsuaa, xsuaaChecked]);

  // Show loading while checking XSUAA
  if ((isAppRouter || isXsuaaEnabled) && !xsuaaChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // If XSUAA is enabled and session is checked, render children
  if ((isAppRouter || isXsuaaEnabled) && xsuaaChecked) {
    console.log("[AuthGuard] XSUAA session checked - rendering app");
    return <>{children}</>;
  }

  // Check for XSUAA session if accessed through AppRouter and not authenticated
  useEffect(() => {
    if (!isHydrated) return;

    const isAppRouter = typeof window !== "undefined" && (window.location.port === "5001" || window.location.port === "5000");

    if (isAppRouter && !isAuthenticated && requireAuth && !isCheckingXsuaa) {
      setIsCheckingXsuaa(true);
      checkXsuaaSession()
        .then((hasSession) => {
          console.log("[AuthGuard] XSUAA session check:", hasSession);
          if (!hasSession) {
            // No XSUAA session, will redirect to login
            console.log("[AuthGuard] No XSUAA session, redirecting to login");
          }
        })
        .finally(() => {
          setIsCheckingXsuaa(false);
        });
    }
  }, [isHydrated, isAuthenticated, requireAuth, checkXsuaaSession, isCheckingXsuaa]);

  // Load permissions when authenticated
  useEffect(() => {
    if (isHydrated && isAuthenticated && token) {
      loadPermissions().catch((error) => {
        console.error("Failed to load permissions:", error);
      });
    }
  }, [isHydrated, isAuthenticated, token, loadPermissions]);

  useEffect(() => {
    // Only run on client side and after hydration
    if (typeof window === "undefined" || !isHydrated) return;

    // Check authentication status
    const isAuthed = isAuthenticated && token;

    // Redirect handled by Navigate component below
  }, [isAuthenticated, token, requireAuth, redirectTo, pathname, router, isHydrated]);

  // Show loading until hydrated
  if (!isHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Show loading if auth is required but not authenticated
  if (requireAuth && !isAuthenticated) {
    // Redirect to login with return URL
    const returnUrl = pathname !== redirectTo ? pathname : undefined;
    return <Navigate to={redirectTo} state={{ from: returnUrl }} replace />;
  }

  // If authenticated and on login page, redirect to dashboard
  if (!requireAuth && isAuthenticated && pathname === "/login") {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

/**
 * Hook to check if user is authenticated
 *
 * Usage:
 * ```tsx
 * const isAuthenticated = useAuth();
 * if (!isAuthenticated) return <LoginPrompt />;
 * ```
 */
export function useAuth() {
  return useAuthStore((state) => state.isAuthenticated);
}

/**
 * Hook to get current user
 *
 * Usage:
 * ```tsx
 * const user = useCurrentUser();
 * return <div>Welcome, {user?.username}</div>;
 * ```
 */
export function useCurrentUser() {
  return useAuthStore((state) => state.user);
}
