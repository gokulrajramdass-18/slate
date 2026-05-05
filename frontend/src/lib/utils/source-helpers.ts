/**
 * Utility functions for source data handling
 */

import type { Source, AssetData } from "@/lib/types";

/**
 * Parse asset_data JSON safely
 * Handles both JSON strings and already-parsed objects
 */
export function parseAssetData(source: Source): AssetData | null {
  if (!source.asset_data) return null;

  try {
    return typeof source.asset_data === 'string'
      ? JSON.parse(source.asset_data)
      : source.asset_data;
  } catch (error) {
    console.error('Failed to parse asset_data:', error);
    return null;
  }
}

/**
 * Format duration seconds as MM:SS or HH:MM:SS
 * @param seconds - Duration in seconds
 * @returns Formatted duration string (e.g., "3:31" or "1:23:45")
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  const pad = (n: number) => n.toString().padStart(2, '0');

  if (hours > 0) {
    return `${hours}:${pad(minutes)}:${pad(secs)}`;
  }
  return `${minutes}:${pad(secs)}`;
}

/**
 * Format view count with abbreviations
 * @param count - Number of views
 * @returns Formatted string (e.g., "1.7M", "150K", "999")
 */
export function formatViewCount(count: number): string {
  if (count >= 1_000_000_000) {
    return `${(count / 1_000_000_000).toFixed(1)}B`;
  }
  if (count >= 1_000_000) {
    return `${(count / 1_000_000).toFixed(1)}M`;
  }
  if (count >= 1_000) {
    return `${(count / 1_000).toFixed(1)}K`;
  }
  return count.toString();
}

/**
 * Remove sensitive keys from connection config
 * Filters out passwords, API keys, tokens, etc.
 */
export function sanitizeConnectionConfig(config: any): any {
  const SENSITIVE = [
    'password',
    'client_secret',
    'api_key',
    'access_token',
    'refresh_token',
    'bearer_token',
  ];

  if (!config) return {};

  return Object.keys(config).reduce((acc, key) => {
    if (!SENSITIVE.some((s) => key.toLowerCase().includes(s))) {
      acc[key] = config[key];
    }
    return acc;
  }, {} as any);
}
