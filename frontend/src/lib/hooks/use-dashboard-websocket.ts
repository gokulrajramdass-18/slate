// Updated: 2026-04-27T16:56:42.498Z
import { useEffect, useState, useCallback, useRef } from "react";

// Remove trailing /api if present to avoid double /api in URLs
const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:5055").replace(/\/api\/?$/, "");
const WS_BASE_URL = BASE_URL.replace("http", "ws");

interface UseDashboardWebSocketOptions {
  userId: string;
  onUpdate: (stats: any) => void;
  enabled?: boolean;
}

export function useDashboardWebSocket({
  userId,
  onUpdate,
  enabled = true,
}: UseDashboardWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<any>(undefined);
  const reconnectAttemptsRef = useRef(0);
  const isConnectingRef = useRef(false);
  const maxReconnectAttempts = 5;
  const onUpdateRef = useRef(onUpdate);
  const enabledRef = useRef(enabled);
  const userIdRef = useRef(userId);

  // Keep refs up to date
  useEffect(() => {
    onUpdateRef.current = onUpdate;
    enabledRef.current = enabled;
    userIdRef.current = userId;
  });

  const connect = useCallback(() => {
    // Don't attempt connection if disabled, no userId, or already connected/connecting
    if (!enabledRef.current || !userIdRef.current || wsRef.current?.readyState === WebSocket.OPEN || isConnectingRef.current) {
      return;
    }

    // Don't attempt if userId is placeholder/invalid
    if (userIdRef.current === "test" || userIdRef.current.length < 5) {
      return;
    }

    try {
      isConnectingRef.current = true;
      const ws = new WebSocket(`${WS_BASE_URL}/api/dashboard/ws/${userIdRef.current}`);

      ws.onopen = () => {
        console.log("✓ Dashboard WebSocket connected");
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        isConnectingRef.current = false;
      };

      ws.onmessage = (event) => {
        try {
          // Ignore "pong" keepalive responses
          if (event.data === "pong") {
            return;
          }

          const message = JSON.parse(event.data);

          if (message.type === "stats_update" && message.data) {
            onUpdateRef.current(message.data);
          }
        } catch (error) {
          console.error("Error parsing WebSocket message:", error);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        isConnectingRef.current = false;

        // Only attempt to reconnect if still enabled, have valid userId, and haven't exceeded max attempts
        const hasValidUser = userIdRef.current && userIdRef.current !== "test" && userIdRef.current.length >= 5;
        if (enabledRef.current && hasValidUser && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          reconnectAttemptsRef.current++;

          console.log(`Dashboard WebSocket disconnected. Reconnecting in ${delay/1000}s (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})...`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.warn("Dashboard WebSocket max reconnect attempts reached. Giving up.");
        }
      };

      ws.onerror = () => {
        isConnectingRef.current = false;
        // Silently fail - onclose will handle reconnection logic
        // Don't spam console with errors
      };

      wsRef.current = ws;

      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, 30000);

      // Clean up ping interval when WebSocket closes
      ws.addEventListener("close", () => clearInterval(pingInterval));
    } catch (error) {
      console.error("Failed to create WebSocket connection:", error);
      setIsConnected(false);
      isConnectingRef.current = false;
    }
  }, []); // No dependencies - uses refs instead

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    isConnectingRef.current = false;
    reconnectAttemptsRef.current = 0; // Reset reconnect attempts on explicit disconnect
    setIsConnected(false);
  }, []);

  useEffect(() => {
    // Only connect if enabled and userId is valid (not empty, not "test", length >= 5)
    const hasValidUser = userId && userId !== "test" && userId.length >= 5;
    if (enabled && hasValidUser) {
      connect();
    }

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, userId]); // Only re-run when enabled or userId changes

  return { isConnected, connect, disconnect };
}
