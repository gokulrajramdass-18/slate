"use client";

import React, { useState, useEffect } from "react";
import { Bell, Check, CheckCheck, Trash2, Archive, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useNotifications } from "@/lib/hooks/use-notifications";
import { useAuthStore } from "@/lib/stores/auth-store";

export interface Notification {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  category?: string;
  priority: string;
  entity_type?: string;
  entity_id?: string;
  action_url?: string;
  action_label?: string;
  metadata?: Record<string, any>;
  is_read: boolean;
  is_archived: boolean;
  read_at?: string;
  created_at?: string;
  expires_at?: string;
}

const getPriorityColor = (priority: string) => {
  switch (priority) {
    case "urgent":
      return "text-red-600 dark:text-red-400";
    case "high":
      return "text-orange-600 dark:text-orange-400";
    case "normal":
      return "text-blue-600 dark:text-blue-400";
    case "low":
      return "text-gray-600 dark:text-gray-400";
    default:
      return "text-blue-600 dark:text-blue-400";
  }
};

const getCategoryIcon = (category?: string) => {
  switch (category) {
    case "approval":
      return "✅";
    case "workflow":
      return "⚡";
    case "agent":
      return "🤖";
    case "schedule":
      return "📅";
    case "system":
      return "⚙️";
    default:
      return "📬";
  }
};

const getTimeAgo = (dateString?: string) => {
  if (!dateString) return "";

  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

  return date.toLocaleDateString();
};

interface NotificationItemProps {
  notification: Notification;
  onMarkRead: (id: string) => void;
  onDelete: (id: string) => void;
  onAction?: (url: string) => void;
}

const NotificationItem: React.FC<NotificationItemProps> = ({
  notification,
  onMarkRead,
  onDelete,
  onAction,
}) => {
  return (
    <div
      className={cn(
        "group relative p-4 border-b border-gray-200 dark:border-gray-700 transition-all duration-200",
        !notification.is_read && "bg-blue-50/50 dark:bg-blue-950/20",
        "hover:bg-gray-50 dark:hover:bg-gray-800/50"
      )}
    >
      {/* Unread indicator */}
      {!notification.is_read && (
        <div className="absolute left-2 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
      )}

      <div className="flex items-start gap-3 ml-2">
        {/* Category icon */}
        <div className="text-2xl flex-shrink-0 mt-1">
          {getCategoryIcon(notification.category)}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h4
              className={cn(
                "font-semibold text-sm",
                !notification.is_read
                  ? "text-gray-900 dark:text-gray-100"
                  : "text-gray-700 dark:text-gray-300"
              )}
            >
              {notification.title}
            </h4>
            <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
              {getTimeAgo(notification.created_at)}
            </span>
          </div>

          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 line-clamp-2">
            {notification.message}
          </p>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-wrap">
            {notification.action_url && notification.action_label && (
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={() => onAction?.(notification.action_url!)}
              >
                {notification.action_label}
              </Button>
            )}

            <div className="flex items-center gap-1 ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
              {!notification.is_read && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  onClick={() => onMarkRead(notification.id)}
                  title="Mark as read"
                >
                  <Check className="w-4 h-4" />
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0 text-red-600 hover:text-red-700"
                onClick={() => onDelete(notification.id)}
                title="Delete"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Priority badge */}
          {notification.priority !== "normal" && (
            <Badge
              variant="outline"
              className={cn("text-xs mt-2", getPriorityColor(notification.priority))}
            >
              {notification.priority}
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
};

export const NotificationCenter: React.FC = () => {
  const user = useAuthStore((state) => state.user);
  const {
    notifications,
    unreadCount,
    loading,
    markAsRead,
    markAllAsRead,
    deleteNotification,
  } = useNotifications(
    (user as any)?.uuid || user?.id
      ? { userId: (user as any)?.uuid || user!.id, autoConnect: true }
      : undefined
  );

  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<string>("all");

  const handleAction = (url: string) => {
    // Navigate to the action URL
    window.location.href = url;
    setIsOpen(false);
  };

  const filteredNotifications = notifications.filter((n) => {
    if (activeTab === "all") return true;
    if (activeTab === "unread") return !n.is_read;
    return n.category === activeTab;
  });

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="relative h-9 w-9 p-0"
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              className="absolute -top-1 -right-1 h-5 min-w-[20px] rounded-full p-0 flex items-center justify-center bg-red-600 text-white text-xs font-bold animate-in zoom-in duration-200"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        className="w-[420px] p-0"
        sideOffset={8}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-lg">Notifications</h3>
            {unreadCount > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={markAllAsRead}
                className="h-8 text-xs"
              >
                <CheckCheck className="w-4 h-4 mr-1" />
                Mark all read
              </Button>
            )}
          </div>

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-5 h-8">
              <TabsTrigger value="all" className="text-xs">
                All
              </TabsTrigger>
              <TabsTrigger value="unread" className="text-xs">
                Unread
              </TabsTrigger>
              <TabsTrigger value="approval" className="text-xs">
                Approvals
              </TabsTrigger>
              <TabsTrigger value="workflow" className="text-xs">
                Workflows
              </TabsTrigger>
              <TabsTrigger value="agent" className="text-xs">
                Agents
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {/* Notification list */}
        <ScrollArea className="h-[500px]">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          ) : filteredNotifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-gray-500">
              <Bell className="w-12 h-12 mb-2 opacity-20" />
              <p className="text-sm">No notifications</p>
            </div>
          ) : (
            <div>
              {filteredNotifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onMarkRead={markAsRead}
                  onDelete={deleteNotification}
                  onAction={handleAction}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
