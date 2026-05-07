"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { Notification } from "@/components/notifications/NotificationCenter";
import { API_BASE_URL, WS_BASE_URL } from "@/lib/config/api";

interface UseNotificationsOptions {
  userId: string;
  autoConnect?: boolean;
  pollInterval?: number;
}

interface UseNotificationsReturn {
  notifications: Notification[];
  unreadCount: number;
  loading: boolean;
  error: string | null;
  connected: boolean;
  toastQueue: Notification[];
  markAsRead: (notificationId: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  deleteNotification: (notificationId: string) => Promise<void>;
  refetch: () => Promise<void>;
  dismissToast: (notificationId: string) => void;
}

export const useNotifications = (
  options?: UseNotificationsOptions
): UseNotificationsReturn => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [toastQueue, setToastQueue] = useState<Notification[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const shownToastsRef = useRef<Set<string>>(new Set());

  // Store userId in a ref to avoid recreating callbacks
  const userIdRef = useRef<string | null>(null);

  // Update userIdRef when options change
  useEffect(() => {
    if (options?.userId) {
      userIdRef.current = options.userId;
    } else if (typeof window !== "undefined") {
      // Try to get user from auth-storage (Zustand persist)
      const authStorage = localStorage.getItem("auth-storage");
      if (authStorage) {
        try {
          const authState = JSON.parse(authStorage);
          if (authState.state?.user?.id) {
            userIdRef.current = authState.state.user.id;
          }
        } catch (e) {
          console.error("Failed to parse auth-storage from localStorage:", e);
          userIdRef.current = null;
        }
      }
    }
  }, [options?.userId]);

  // Get user ID from ref
  const getUserId = useCallback(() => userIdRef.current, []);

  // Mark notification as read
  const markAsRead = useCallback(async (notificationId: string) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/notifications/${notificationId}/read`,
        { method: "POST" }
      );

      if (!response.ok) {
        throw new Error("Failed to mark as read");
      }

      // Update local state
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notificationId ? { ...n, is_read: true } : n
        )
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error("Error marking notification as read:", err);
    }
  }, []);

  // Mark all notifications as read
  const markAllAsRead = useCallback(async () => {
    const userId = getUserId();
    if (!userId) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/notifications/mark-all-read?user_id=${userId}`,
        { method: "POST" }
      );

      if (!response.ok) {
        throw new Error("Failed to mark all as read");
      }

      // Update local state
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true }))
      );
      setUnreadCount(0);
    } catch (err) {
      console.error("Error marking all as read:", err);
    }
  }, [getUserId]);

  // Delete notification
  const deleteNotification = useCallback(async (notificationId: string) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/notifications/${notificationId}`,
        { method: "DELETE" }
      );

      if (!response.ok) {
        throw new Error("Failed to delete notification");
      }

      // Update local state
      setNotifications((prev) => {
        const notification = prev.find((n) => n.id === notificationId);
        if (notification && !notification.is_read) {
          setUnreadCount((count) => Math.max(0, count - 1));
        }
        return prev.filter((n) => n.id !== notificationId);
      });
    } catch (err) {
      console.error("Error deleting notification:", err);
    }
  }, []);

  // Dismiss toast
  const dismissToast = useCallback((notificationId: string) => {
    setToastQueue((prev) => prev.filter((n) => n.id !== notificationId));
  }, []);

  // Refetch notifications
  const refetch = useCallback(async () => {
    const userId = getUserId();

    try {
      // Build URL with or without userId
      const url = userId
        ? `${API_BASE_URL}/notifications?user_id=${userId}&limit=50`
        : `${API_BASE_URL}/notifications?limit=50`;

      const response = await fetch(url);

      if (!response.ok) {
        // Don't throw error for auth issues
        if (response.status === 401 || response.status === 403) {
          setNotifications([]);
          setUnreadCount(0);
          setError(null);
          return;
        }
        throw new Error("Failed to fetch notifications");
      }

      const data = await response.json();
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count || 0);
      setError(null);
    } catch (err) {
      console.error("Error fetching notifications:", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }, [getUserId]);

  // Initial fetch (only if we have options/user)
  useEffect(() => {
    const userId = options?.userId || userIdRef.current;
    console.log("[useNotifications] Fetching with userId:", userId);

    const fetchData = async () => {
      try {
        // Build URL with or without userId
        const url = userId
          ? `${API_BASE_URL}/notifications?user_id=${userId}&limit=50`
          : `${API_BASE_URL}/notifications?limit=50`;

        console.log("[useNotifications] Fetching from:", url);
        const response = await fetch(url);

        if (!response.ok) {
          const errorText = await response.text();
          console.error("Notifications API error:", response.status, errorText);

          // Don't throw error for auth issues, just set empty state
          if (response.status === 401 || response.status === 403) {
            console.log("[useNotifications] Auth error, setting empty state");
            setNotifications([]);
            setUnreadCount(0);
            setError(null);
            setLoading(false);
            return;
          }

          throw new Error(`Failed to fetch notifications: ${response.status}`);
        }

        const data = await response.json();
        console.log("[useNotifications] Received data:", data);
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count || 0);
        setError(null);
      } catch (err) {
        console.error("Error fetching notifications:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [options?.userId]);

  // Setup WebSocket connection (only if we have options/user)
  useEffect(() => {
    const userId = options?.userId || userIdRef.current;
    if (!options?.autoConnect || !userId) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      const wsUrl = `${API_BASE_URL.replace("http", "ws")}/notifications/ws/${userId}`;
      console.log("[useNotifications] WebSocket URL:", wsUrl);
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("✓ Notification WebSocket connected");
        setConnected(true);
        setError(null);

        // Clear reconnect timeout
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          // Ignore "pong" keepalive responses (WebSocket ping/pong protocol)
          if (event.data === "pong") {
            return;
          }

          const data = JSON.parse(event.data);

          if (data.type === "new_notification") {
            const notification = data.notification as Notification;

            // Add to notifications list
            setNotifications((prev) => [notification, ...prev]);
            setUnreadCount((prev) => prev + 1);

            // Add to toast queue if not already shown
            if (!shownToastsRef.current.has(notification.id)) {
              setToastQueue((prev) => [...prev, notification]);
              shownToastsRef.current.add(notification.id);
            }
          } else if (data.type === "unread_count") {
            setUnreadCount(data.count);
          } else if (data.type === "all_marked_read") {
            setNotifications((prev) =>
              prev.map((n) => ({ ...n, is_read: true }))
            );
            setUnreadCount(0);
          }
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      ws.onerror = () => {
        // Only log error if we have a userId (not on login page)
        if (userId) {
          console.warn("Notification WebSocket connection issue - falling back to polling");
        }
        setError(null); // Don't set error state, polling will handle it
      };

      ws.onclose = () => {
        if (userId) {
          console.log("✗ Notification WebSocket disconnected - using polling fallback");
        }
        setConnected(false);

        // Attempt to reconnect after 5 seconds (only if user is still logged in)
        if (options?.autoConnect && userId) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log("Attempting to reconnect WebSocket...");
            // Trigger re-render to reconnect by updating a dummy state
            setError(null);
          }, 5000);
        }
      };

      wsRef.current = ws;

      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, 30000);

      return () => {
        clearInterval(pingInterval);
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
      };
    } catch (err) {
      console.error("Error connecting WebSocket:", err);
      setError(err instanceof Error ? err.message : "Failed to connect");
    }
  }, [options?.autoConnect, options?.userId]);

  // Setup polling fallback (only if we have options/user)
  useEffect(() => {
    const userId = options?.userId || userIdRef.current;
    if (!options?.pollInterval || !userId || connected) return;

    const pollData = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/notifications?user_id=${userId}&limit=50`
        );

        if (!response.ok) {
          throw new Error("Failed to fetch notifications");
        }

        const data = await response.json();
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count || 0);
        setError(null);
      } catch (err) {
        console.error("Error fetching notifications:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    };

    pollIntervalRef.current = setInterval(pollData, options.pollInterval);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [options?.pollInterval, options?.userId, connected]);

  return {
    notifications,
    unreadCount,
    loading,
    error,
    connected,
    toastQueue,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    refetch,
    dismissToast,
  };
};
