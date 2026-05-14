/**
 * API Configuration
 *
 * Centralized API URL configuration for all API calls.
 * Uses NEXT_PUBLIC_API_URL environment variable for client-side calls,
 * falls back to relative '/api' which works through Next.js rewrites for server-side calls.
 */

// Base API URL - use environment variable for client-side, relative path for server-side
export const API_BASE_URL =
  typeof window !== "undefined" && import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL + "/api"
    : "/api";

// WebSocket base URL - derived from API base URL
export const WS_BASE_URL = typeof window !== "undefined"
  ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`
  : "";

/**
 * Get full API URL for a given path
 * @param path - API path (e.g., '/workflows' or 'workflows')
 * @returns Full URL
 */
export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${cleanPath}`;
}

/**
 * Get WebSocket URL for a given path
 * @param path - WebSocket path (e.g., '/ws/notifications')
 * @returns Full WebSocket URL
 */
export function getWsUrl(path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${WS_BASE_URL}${API_BASE_URL}${cleanPath}`;
}
