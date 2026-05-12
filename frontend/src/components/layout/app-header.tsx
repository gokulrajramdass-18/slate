"use client";

import { useAuthStore } from "@/lib/stores/auth-store";
import { useConnectionStore } from "@/lib/stores/connection-store";
import { Button } from "@/components/ui/button";
import { Menu, PenLine, Moon, Sun, LogOut } from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { NotificationCenter } from "@/components/notifications/NotificationCenter";

interface AppHeaderProps {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export function AppHeader({ sidebarOpen, toggleSidebar }: AppHeaderProps) {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);
  const { status, databaseType } = useConnectionStore();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 bg-white border-b border-gray-200 dark:bg-gray-950 dark:border-gray-800">
      <div className="flex items-center justify-between h-full px-4 md:px-6 gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            <Menu className="w-5 h-5" />
          </Button>
          <div className="relative w-6 h-6 shrink-0">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 animate-gradient-shift rounded-sm opacity-90"></div>
            <PenLine className="w-6 h-6 relative text-white mix-blend-screen" />
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-lg font-bold leading-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent animate-gradient-shift">
              Slate
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400 font-normal leading-tight truncate animate-pulse-subtle">
              Do Nothing, Redefine Everything
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 md:gap-3">
          {/* Database Status */}
          <div className="hidden md:flex items-center gap-2 text-sm">
            <div
              className={cn(
                "w-2 h-2 rounded-full",
                status === "connected" && "bg-green-500",
                status === "disconnected" && "bg-red-500",
                status === "reconnecting" && "bg-yellow-500 animate-pulse"
              )}
            />
            <span className="text-gray-600 dark:text-gray-400">
              {databaseType === "sqlite" ? "SQLite" : "HANA"}
            </span>
          </div>

          {/* Notifications */}
          <NotificationCenter />

          {/* Theme Toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? (
              <Sun className="w-5 h-5" />
            ) : (
              <Moon className="w-5 h-5" />
            )}
          </Button>

          {/* User Menu */}
          <div className="flex items-center gap-2 text-sm">
            <span className="hidden md:inline text-gray-600 dark:text-gray-400 whitespace-nowrap">
              {user?.username}
            </span>
            <Button variant="ghost" size="icon" className="shrink-0" onClick={handleLogout}>
              <LogOut className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
