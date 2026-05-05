"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { SyncConfig } from "@/lib/types";

interface SyncSettingsProps {
  config: SyncConfig;
  onChange: (config: SyncConfig) => void;
  disabled?: boolean;
}

export function SyncSettings({ config, onChange, disabled = false }: SyncSettingsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Sync Settings</CardTitle>
        <CardDescription>Configure automatic data synchronization</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="sync-enabled">Enable Automatic Sync</Label>
            <p className="text-sm text-gray-500">
              Periodically sync data from the source
            </p>
          </div>
          <Switch
            id="sync-enabled"
            checked={config.enabled}
            onCheckedChange={(enabled) => onChange({ ...config, enabled })}
            disabled={disabled}
          />
        </div>

        {config.enabled && (
          <div className="space-y-2">
            <Label>Sync Frequency</Label>
            <Select
              value={config.frequency}
              onValueChange={(frequency: SyncConfig["frequency"]) =>
                onChange({ ...config, frequency })
              }
              disabled={disabled}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                <SelectItem value="manual">Manual Only</SelectItem>
                <SelectItem value="hourly">Every Hour</SelectItem>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-sm text-gray-500">
              {config.frequency === "hourly" && "Data will sync every hour"}
              {config.frequency === "daily" && "Data will sync once per day"}
              {config.frequency === "weekly" && "Data will sync once per week"}
              {config.frequency === "manual" && "Sync only when manually triggered"}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
