"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, CheckCircle, XCircle } from "lucide-react";
import type { DatabaseConfig } from "@/lib/types";

interface DatabaseConnectionFormProps {
  config: Partial<DatabaseConfig>;
  onChange: (config: Partial<DatabaseConfig>) => void;
  onTest?: () => void;
  isTestingConnection?: boolean;
  testResult?: { success: boolean; message: string } | null;
}

export function DatabaseConnectionForm({
  config,
  onChange,
  onTest,
  isTestingConnection,
  testResult,
}: DatabaseConnectionFormProps) {
  const updateConfig = (key: string, value: any) => {
    onChange({ ...config, [key]: value });
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="host">Host</Label>
          <Input
            id="host"
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.hana.trial-us10.hanacloud.ondemand.com"
            value={config.hana_host || ""}
            onChange={(e) => updateConfig("hana_host", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="port">Port</Label>
          <Input
            id="port"
            type="number"
            placeholder="443"
            value={config.hana_port || 443}
            onChange={(e) => updateConfig("hana_port", parseInt(e.target.value) || 443)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="database">Database</Label>
          <Input
            id="database"
            placeholder="DATABASE_NAME"
            value={config.hana_database || ""}
            onChange={(e) => updateConfig("hana_database", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="user">User</Label>
          <Input
            id="user"
            placeholder="DB_USER"
            value={config.hana_user || ""}
            onChange={(e) => updateConfig("hana_user", e.target.value)}
          />
        </div>
      </div>

      {onTest && (
        <div className="pt-4 space-y-3">
          <Button
            variant="outline"
            onClick={onTest}
            disabled={isTestingConnection || !config.hana_host}
            className="w-full sm:w-auto"
          >
            {isTestingConnection && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
            Test Connection
          </Button>

          {testResult && (
            <Card className={testResult.success ? "border-green-200" : "border-red-200"}>
              <CardContent className="flex items-center gap-2 pt-4">
                {testResult.success ? (
                  <>
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <span className="text-sm text-green-700">{testResult.message}</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-red-600" />
                    <span className="text-sm text-red-700">{testResult.message}</span>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
