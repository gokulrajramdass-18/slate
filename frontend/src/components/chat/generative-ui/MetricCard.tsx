"use client";

import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export interface MetricCardProps {
  /** Metric label / title */
  label: string;
  /** Current value */
  value: string | number;
  /** Optional unit (e.g., "%", "ms", "USD") */
  unit?: string;
  /** Change from previous period */
  change?: number;
  /** Change direction label (e.g., "vs last week") */
  change_label?: string;
  /** Optional icon name from lucide (rendered as text fallback) */
  icon?: string;
  /** Accent color for the metric */
  color?: "blue" | "green" | "red" | "yellow" | "purple" | "gray";
}

const colorMap: Record<string, string> = {
  blue: "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/30",
  green: "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30",
  red: "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30",
  yellow: "text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-950/30",
  purple: "text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/30",
  gray: "text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/30",
};

export function MetricCard({
  label,
  value,
  unit,
  change,
  change_label,
  color = "blue",
}: MetricCardProps) {
  // Defensive check for undefined props
  if (!label || value === undefined) {
    console.error("[MetricCard] Missing required props:", { label, value, unit, change, change_label, color });
    return (
      <Card className="overflow-hidden">
        <CardContent className="p-4">
          <p className="text-sm text-red-500">Invalid metric data</p>
        </CardContent>
      </Card>
    );
  }

  const formattedValue =
    typeof value === "number" ? value.toLocaleString() : value;

  const changeDirection =
    change != null ? (change > 0 ? "up" : change < 0 ? "down" : "neutral") : null;

  const changeColor =
    changeDirection === "up"
      ? "text-green-600 dark:text-green-400"
      : changeDirection === "down"
        ? "text-red-600 dark:text-red-400"
        : "text-gray-500 dark:text-gray-400";

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="space-y-2 flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
              {label}
            </p>
            <div className="flex items-baseline gap-1">
              <span className={cn("text-2xl font-bold", colorMap[color]?.split(" ").filter(c => c.startsWith("text-")).join(" ") || "text-gray-900 dark:text-gray-100")}>
                {formattedValue}
              </span>
              {unit && (
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {unit}
                </span>
              )}
            </div>
            {change != null && (
              <div className={cn("flex items-center gap-1 text-sm", changeColor)}>
                {changeDirection === "up" && <ArrowUp className="w-3.5 h-3.5" />}
                {changeDirection === "down" && <ArrowDown className="w-3.5 h-3.5" />}
                {changeDirection === "neutral" && <Minus className="w-3.5 h-3.5" />}
                <span className="font-medium">
                  {change > 0 ? "+" : ""}
                  {change}%
                </span>
                {change_label && (
                  <span className="text-gray-400 dark:text-gray-500 ml-0.5">
                    {change_label}
                  </span>
                )}
              </div>
            )}
          </div>
          <div
            className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
              colorMap[color] || colorMap.blue
            )}
          >
            <span className="text-lg font-bold">
              {label.charAt(0).toUpperCase()}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
