"use client";

import { useAuthStore } from "@/lib/stores/auth-store";
import { ReactNode } from "react";

interface CanProps {
  /**
   * Resource type to check permission for
   */
  resource: string;

  /**
   * Action to check permission for
   */
  action: string;

  /**
   * Content to render if user has permission
   */
  children: ReactNode;

  /**
   * Optional fallback content to render if user doesn't have permission
   */
  fallback?: ReactNode;
}

/**
 * Permission-based rendering component
 *
 * Shows children only if user has the required permission.
 * Superadmins always see the content.
 *
 * Example:
 * ```tsx
 * <Can resource="workspace" action="create">
 *   <Button>Create Workspace</Button>
 * </Can>
 * ```
 */
export function Can({ resource, action, children, fallback = null }: CanProps) {
  const user = useAuthStore((state) => state.user);

  // No user = no permission
  if (!user) {
    return <>{fallback}</>;
  }

  // Superadmin bypass
  if (user.is_superadmin) {
    return <>{children}</>;
  }

  // Check user's permission
  // For now, we rely on backend enforcement
  // TODO: Implement client-side permission checking by loading
  // role permissions and checking against user's roles
  const hasPermission = useAuthStore.getState().hasPermission(resource, action);

  if (hasPermission) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
}

/**
 * Hook to check if user has a specific role
 */
export function useHasRole(roleName: string): boolean {
  return useAuthStore((state) => state.hasRole(roleName));
}

/**
 * Hook to check if user has a specific permission
 */
export function useHasPermission(resource: string, action: string): boolean {
  return useAuthStore((state) => state.hasPermission(resource, action));
}

/**
 * Hook to check if user is superadmin
 */
export function useIsSuperadmin(): boolean {
  const user = useAuthStore((state) => state.user);
  return user?.is_superadmin ?? false;
}
