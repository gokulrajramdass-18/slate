"use client";

import { LineChart } from "./charts/LineChart";
import { BarChart } from "./charts/BarChart";
import { PieChart } from "./charts/PieChart";
import { ScatterChart } from "./charts/ScatterChart";
import { AreaChart } from "./charts/AreaChart";
import { RadarChart } from "./charts/RadarChart";
import type { ChartConfig } from "@/lib/types";
import { AlertTriangle } from "lucide-react";

interface ChartRendererProps extends ChartConfig {
  execution_time_ms?: number;
}

export function ChartRenderer({ type, ...props }: ChartRendererProps) {
  // Validate data
  if (!props.data || props.data.length === 0) {
    return (
      <div className="flex items-center gap-2 p-4 rounded-md bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 text-yellow-700 dark:text-yellow-400 text-sm">
        <AlertTriangle className="w-4 h-4" />
        <span>No data available to render chart</span>
      </div>
    );
  }

  // Select appropriate chart component
  switch (type) {
    case "line":
      return <LineChart {...props} />;
    case "bar":
      return <BarChart {...props} />;
    case "pie":
      return <PieChart {...props} />;
    case "scatter":
      return <ScatterChart {...props} />;
    case "area":
      return <AreaChart {...props} />;
    case "radar":
      return <RadarChart {...props} />;
    case "composed":
      // Advanced: multiple chart types in one (line + bar)
      // Fallback to line for now
      return <LineChart {...props} />;
    default:
      return (
        <div className="flex items-center gap-2 p-4 rounded-md bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4" />
          <span>Unsupported chart type: {type}</span>
        </div>
      );
  }
}
