/**
 * API Configuration
 *
 * Centralized API URL configuration for all API calls.
 * Uses relative URL '/api' which works through Next.js rewrites to proxy to backend.
 */

// Base API URL - use relative path for production deployment
export const API_BASE_URL = "/api";

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
