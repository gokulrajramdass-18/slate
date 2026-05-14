import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { databaseApi } from "@/lib/api/database";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Database, CheckCircle, XCircle, HardDrive, Download } from "lucide-react";
import { toast } from "sonner";
import { DatabaseConnectionForm } from "@/components/settings/database-connection-form";
import { DatabaseSwitcher } from "@/components/settings/database-switcher";
import type { DatabaseConfig } from "@/lib/types";

import { SettingsHeader } from "@/components/settings/settings-header";

export default function SettingsDatabasePage() {
  const queryClient = useQueryClient();
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const { data: config } = useQuery({
    queryKey: ["database-config"],
    queryFn: databaseApi.getConfig,
  });

  const { data: status } = useQuery({
    queryKey: ["database-status"],
    queryFn: databaseApi.getStatus,
    refetchInterval: 30000, // Poll every 30s
  });

  const [hanaConfig, setHanaConfig] = useState<Partial<DatabaseConfig>>({
    hana_host: "",
    hana_port: 443,
    hana_database: "",
    hana_user: "",
  });

  const switchMutation = useMutation({
    mutationFn: async ({
      targetType,
      config,
    }: {
      targetType: "sqlite" | "hana";
      config?: DatabaseConfig;
    }) => {
      return databaseApi.switch(targetType, config);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["database-config"] });
      queryClient.invalidateQueries({ queryKey: ["database-status"] });
      toast.success("Database switched successfully");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.error?.message || "Failed to switch database");
    },
  });

  const backupMutation = useMutation({
    mutationFn: databaseApi.backup,
    onSuccess: (data) => {
      toast.success(`Backup created: ${data.path}`);
    },
    onError: () => {
      toast.error("Backup failed");
    },
  });

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setTestResult(null);
    try {
      const result = await databaseApi.testConnection({
        type: "hana",
        hana_host: hanaConfig.hana_host,
        hana_port: hanaConfig.hana_port,
        hana_database: hanaConfig.hana_database,
        hana_user: hanaConfig.hana_user,
        hana_encrypt: true,
      });
      setTestResult(result);
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error.response?.data?.error?.message || "Connection test failed",
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSwitch = async (targetType: "sqlite" | "hana", dbConfig?: DatabaseConfig) => {
    await switchMutation.mutateAsync({ targetType, config: dbConfig });
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <SettingsHeader
        title="Database Configuration"
        description="Manage your database connection and switch between SQLite and HANA Cloud"
      />

      {/* Current Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="w-5 h-5" />
            Current Database
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-lg">
                {config?.type === "sqlite" ? "SQLite" : "HANA Cloud"}
              </p>
              <p className="text-sm text-gray-500">
                {config?.type === "sqlite"
                  ? `Path: ${config.sqlite_path || "./data/database.db"}`
                  : `Host: ${config?.hana_host || ""}:${config?.hana_port || ""}`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {status?.connected ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-sm font-medium text-green-600">Connected</span>
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-red-600" />
                  <span className="text-sm font-medium text-red-600">Disconnected</span>
                </>
              )}
            </div>
          </div>

          {status?.stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t">
              <StatCard label="Notebooks" value={status.stats.notebooks} />
              <StatCard label="Sources" value={status.stats.sources} />
              <StatCard label="Notes" value={status.stats.notes} />
              <StatCard label="Embeddings" value={status.stats.embeddings} />
            </div>
          )}

          {config?.type === "sqlite" && (
            <div className="pt-4 border-t">
              <Button
                variant="outline"
                onClick={() => backupMutation.mutate()}
                disabled={backupMutation.isPending}
                className="flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Create Backup
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Database Switcher */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Switch Database</h2>
        <DatabaseSwitcher
          currentType={config?.type || "sqlite"}
          onSwitch={handleSwitch}
          hanaConfig={hanaConfig}
          isSwitching={switchMutation.isPending}
        />
      </div>

      {/* HANA Cloud Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="w-5 h-5" />
            HANA Cloud Configuration
          </CardTitle>
          <CardDescription>
            Configure connection settings for HANA Cloud database
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DatabaseConnectionForm
            config={hanaConfig}
            onChange={setHanaConfig}
            onTest={handleTestConnection}
            isTestingConnection={testingConnection}
            testResult={testResult}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold">{value.toLocaleString()}</p>
    </div>
  );
}
