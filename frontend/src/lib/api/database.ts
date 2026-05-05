import { apiClient } from "./client";
import type { DatabaseConfig, DatabaseStatus } from "@/lib/types";

export const databaseApi = {
  // Get current database configuration
  getConfig: async (): Promise<DatabaseConfig> => {
    const { data } = await apiClient.get("/database/config");
    return data;
  },

  // Update database configuration
  updateConfig: async (config: DatabaseConfig): Promise<DatabaseConfig> => {
    const { data } = await apiClient.put("/database/config", config);
    return data;
  },

  // Test database connection
  testConnection: async (config: DatabaseConfig): Promise<{
    success: boolean;
    message: string;
  }> => {
    const { data } = await apiClient.post("/database/test-connection", config);
    return data;
  },

  // Switch database (SQLite <-> HANA)
  switch: async (targetType: "sqlite" | "hana", config?: DatabaseConfig): Promise<{
    success: boolean;
    message: string;
  }> => {
    const { data } = await apiClient.post("/database/switch", {
      target_type: targetType,
      config,
    });
    return data;
  },

  // Get database status
  getStatus: async (): Promise<DatabaseStatus> => {
    const { data } = await apiClient.get("/database/status");
    return data;
  },

  // Backup database (optional)
  backup: async (): Promise<{ path: string }> => {
    const { data } = await apiClient.post("/database/backup");
    return data;
  },

  // Restore database (optional)
  restore: async (backupPath: string): Promise<{ success: boolean }> => {
    const { data } = await apiClient.post("/database/restore", {
      backup_path: backupPath,
    });
    return data;
  },
};
