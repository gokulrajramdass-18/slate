"use client";

import { AppSidebar } from "./app-sidebar";
import { AppHeader } from "./app-header";
import { cn } from "@/lib/utils";
import { useSidebarStore } from "@/lib/stores/sidebar-store";
import { useAuthStore } from "@/lib/stores/auth-store";
import { useNotifications } from "@/lib/hooks/use-notifications";
import { NotificationToastContainer } from "@/components/notifications/NotificationToast";
import { NotificationDialogManager } from "@/components/notifications/NotificationDialog";
import { ApprovalDialogManager } from "@/components/notifications/ApprovalDialog";
import { Outlet } from "react-router-dom";
import { useRouter } from "@/lib/routing/navigation";

export function AppShell() {
  const { isOpen: sidebarOpen, toggle: toggleSidebar } = useSidebarStore();
  const user = useAuthStore((state) => state.user);
  const router = useRouter();

  // Setup notifications with WebSocket when user is logged in
  const {
    notifications,
    toastQueue,
    dismissToast,
    markAsRead,
  } = useNotifications(
    user
      ? {
          userId: user.id,
          autoConnect: true,
          pollInterval: 60000, // Fallback polling every 60 seconds
        }
      : undefined
  );

  // Log user info for debugging
  console.log("🔑 Current user in AppShell:", user ? { id: user.id, username: user.username } : "No user");

  const handleToastAction = (url: string) => {
    router.push(url);
  };

  const handleDialogDismiss = (id: string) => {
    // Mark as read when dismissed
    markAsRead(id);
  };

  return (
    <div className="h-screen bg-gray-50 dark:bg-gray-900 relative overflow-hidden flex flex-col">
      {/* Animated background gradient */}
      <div className="fixed inset-0 -z-10 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-purple-500/5 to-pink-500/5 animate-gradient-shift" />
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/5 rounded-full blur-3xl animate-pulse-slow animation-delay-2000" />
      </div>

      {/* Approval Dialog - Shows when there are pending approvals */}
      {user && (
        <ApprovalDialogManager userId={user.id} />
      )}

      {/* Notification Dialog for high-priority notifications */}
      {user && (
        <NotificationDialogManager
          notifications={notifications}
          onDismiss={handleDialogDismiss}
        />
      )}

      {/* Notification Toasts for regular notifications */}
      {user && (
        <NotificationToastContainer
          notifications={toastQueue}
          onClose={dismissToast}
          onAction={handleToastAction}
        />
      )}

      <AppHeader
        sidebarOpen={sidebarOpen}
        toggleSidebar={toggleSidebar}
      />
      <div className="flex flex-1 min-h-0 pt-16">
        <AppSidebar open={sidebarOpen} onClose={() => useSidebarStore.getState().close()} />
        <main
          className={cn(
            "flex-1 transition-all duration-300 overflow-auto w-full",
            sidebarOpen ? "ml-64" : "ml-16"
          )}
        >
          <div className="h-full w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
