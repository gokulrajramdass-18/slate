"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Database, Loader2, AlertTriangle } from "lucide-react";
import type { DatabaseConfig } from "@/lib/types";

interface DatabaseSwitcherProps {
  currentType: "sqlite" | "hana";
  onSwitch: (targetType: "sqlite" | "hana", config?: DatabaseConfig) => Promise<void>;
  hanaConfig?: Partial<DatabaseConfig>;
  isSwitching?: boolean;
}

export function DatabaseSwitcher({
  currentType,
  onSwitch,
  hanaConfig,
  isSwitching,
}: DatabaseSwitcherProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  const [targetType, setTargetType] = useState<"sqlite" | "hana">("sqlite");

  const handleSwitchRequest = (type: "sqlite" | "hana") => {
    setTargetType(type);
    setShowConfirm(true);
  };

  const handleConfirmSwitch = async () => {
    try {
      if (targetType === "hana" && hanaConfig) {
        await onSwitch(targetType, {
          type: "hana",
          hana_host: hanaConfig.hana_host,
          hana_port: hanaConfig.hana_port,
          hana_database: hanaConfig.hana_database,
          hana_user: hanaConfig.hana_user,
          hana_encrypt: true,
        });
      } else {
        await onSwitch(targetType);
      }
      setShowConfirm(false);
    } catch (error) {
      // Error handling done in parent component
    }
  };

  const canSwitchToHana =
    hanaConfig?.hana_host && hanaConfig?.hana_database && hanaConfig?.hana_user;

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* SQLite Card */}
        <Card
          className={
            currentType === "sqlite" ? "border-primary-600 bg-primary-50 dark:bg-primary-950" : ""
          }
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5" />
              SQLite
            </CardTitle>
            <CardDescription>Local file-based database for development</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="text-sm space-y-1">
                <p className="text-gray-600 dark:text-gray-400">Fast and simple</p>
                <p className="text-gray-600 dark:text-gray-400">No configuration needed</p>
                <p className="text-gray-600 dark:text-gray-400">Ideal for testing</p>
              </div>
              <Button
                onClick={() => handleSwitchRequest("sqlite")}
                disabled={currentType === "sqlite" || isSwitching}
                variant={currentType === "sqlite" ? "secondary" : "default"}
                className="w-full"
              >
                {currentType === "sqlite" ? "Active" : "Switch to SQLite"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* HANA Cloud Card */}
        <Card
          className={
            currentType === "hana" ? "border-primary-600 bg-primary-50 dark:bg-primary-950" : ""
          }
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5" />
              HANA Cloud
            </CardTitle>
            <CardDescription>Enterprise database with native vector search</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="text-sm space-y-1">
                <p className="text-gray-600 dark:text-gray-400">Production-grade performance</p>
                <p className="text-gray-600 dark:text-gray-400">Native vector engine</p>
                <p className="text-gray-600 dark:text-gray-400">Scales to millions of records</p>
              </div>
              <Button
                onClick={() => handleSwitchRequest("hana")}
                disabled={currentType === "hana" || isSwitching || !canSwitchToHana}
                variant={currentType === "hana" ? "secondary" : "default"}
                className="w-full"
              >
                {isSwitching && targetType === "hana" && (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                )}
                {currentType === "hana" ? "Active" : "Switch to HANA"}
              </Button>
              {!canSwitchToHana && currentType !== "hana" && (
                <p className="text-xs text-amber-600">Configure HANA settings first</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Confirmation Dialog */}
      <AlertDialog open={showConfirm} onOpenChange={setShowConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              Switch Database?
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>
                You are about to switch to <strong>{targetType.toUpperCase()}</strong>.
              </p>
              <p>The application will reconnect to the new database.</p>
              <p className="text-amber-600 font-medium">
                Make sure you have backed up any important data before switching.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmSwitch} disabled={isSwitching}>
              {isSwitching && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              Switch Database
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
