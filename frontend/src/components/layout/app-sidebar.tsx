"use client";

import { Link } from "react-router-dom";
import { usePathname } from "@/lib/routing/navigation";
import { cn } from "@/lib/utils";
import {
  BookOpen,
  FileText,
  Search,
  Settings,
  Globe,
  Users,
  Workflow,
  Star,
  Network,
  Shield,
  UserCircle,
  Database,
  Key,
  Wrench,
  GitBranch,
  FileStack,
  Inbox,
  Home,
  BarChart3,
} from "lucide-react";
import { useAuthStore } from "@/lib/stores/auth-store";
import { useHasPermission, useIsSuperadmin } from "@/components/auth/can";

interface AppSidebarProps {
  open: boolean;
  onClose?: () => void;
}

const navItems = [
  { href: "/dashboard", label: "Home", icon: Home, resource: "workspace", action: "read" },
  { href: "/approvals", label: "Inbox", icon: Inbox, resource: "workflow", action: "read" },
  { href: "/workflows", label: "Workflows", icon: Workflow, resource: "workflow", action: "read" },
  { href: "/workspaces", label: "Workspaces", icon: BookOpen, resource: "workspace", action: "read" },
  { href: "/sources", label: "Sources", icon: FileText, resource: "source", action: "read" },
  { href: "/bookmarks", label: "Bookmarks", icon: Star, resource: "bookmark", action: "read" },
  { href: "/search", label: "Search", icon: Search, resource: "query_prompt", action: "execute" },
  { href: "/graph", label: "Graph", icon: Network, resource: "workspace", action: "read" },
  { href: "/agents", label: "Agents", icon: Users, resource: "agent", action: "read" },
  { href: "/evaluations", label: "Evaluations", icon: BarChart3, resource: "agent", action: "read" },
  { href: "/orchestration", label: "Orchestration", icon: Wrench, resource: "workflow", action: "execute" },
];

const settingsItems = [
  { href: "/settings", label: "Settings", icon: Settings, alwaysShow: true },
];

export function AppSidebar({ open, onClose }: AppSidebarProps) {
  const pathname = usePathname();
  const user = useAuthStore((state) => state.user);
  const isSuperadmin = useIsSuperadmin();
  const hasPermission = useAuthStore((state) => state.hasPermission);

  const canAccessItem = (item: any): boolean => {
    // Always show items marked as alwaysShow
    if (item.alwaysShow) return true;

    // Superadmins can access everything
    if (isSuperadmin) return true;

    // Check permission using the auth store
    if (item.resource && item.action) {
      return hasPermission(item.resource, item.action);
    }

    return false;
  };

  const visibleNavItems = navItems.filter(canAccessItem);
  const visibleSettingsItems = settingsItems.filter(canAccessItem);

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed top-16 left-0 z-40 h-[calc(100vh-4rem)] bg-white border-r border-gray-200 dark:bg-gray-950 dark:border-gray-800 transition-all duration-300",
          open ? "w-64" : "w-16"
        )}
      >
        <nav className="flex flex-col h-full p-2 space-y-6">
          {/* Main Navigation */}
          <div className="space-y-1">
            {visibleNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              return (
                <Link
                  key={item.href}
                  to={item.href}
                  title={!open ? item.label : undefined}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300"
                      : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800",
                    !open && "justify-center"
                  )}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  {open && <span>{item.label}</span>}
                </Link>
              );
            })}
          </div>

          {/* Divider */}
          {open && <div className="border-t border-gray-200 dark:border-gray-800" />}

          {/* Settings */}
          <div className="space-y-1">
            {open && (
              <p className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Settings
              </p>
            )}
            {visibleSettingsItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              return (
                <Link
                  key={item.href}
                  to={item.href}
                  title={!open ? item.label : undefined}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300"
                      : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800",
                    !open && "justify-center"
                  )}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  {open && <span>{item.label}</span>}
                </Link>
              );
            })}
          </div>
        </nav>
      </aside>
    </>
  );
}
