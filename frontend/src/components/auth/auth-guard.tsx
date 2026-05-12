"use client";

import { useEffect, ReactNode, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
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
  const { isAuthenticated, token, loadPermissions } = useAuthStore();
  const [isHydrated, setIsHydrated] = useState(false);

  // Wait for Zustand to hydrate from localStorage
  useEffect(() => {
    setIsHydrated(true);
  }, []);

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

    if (requireAuth && !isAuthed) {
      // User needs to be authenticated but isn't
      const returnUrl = pathname !== redirectTo ? `?returnUrl=${pathname}` : "";
      router.replace(`${redirectTo}${returnUrl}`);
    } else if (!requireAuth && isAuthed && pathname === "/login") {
      // If user is authenticated and on login page, redirect to dashboard
      router.replace("/dashboard");
    }
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
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Redirecting...</p>
        </div>
      </div>
    );
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
