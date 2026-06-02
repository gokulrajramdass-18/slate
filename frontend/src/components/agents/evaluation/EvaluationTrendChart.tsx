"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { EvaluationRun } from "@/lib/api/evaluations";

interface EvaluationTrendChartProps {
  runs: EvaluationRun[];
  /** Optional title shown above the chart */
  title?: string;
  /** Height in px (default 220) */
  height?: number;
}

/**
 * Plots pass-rate (%) and avg score (0–10) over time for a series of evaluation
 * runs. Only runs with a `started_at` and meaningful totals are plotted; the
 * chart sorts oldest → newest so the line moves left-to-right with time.
 */
export function EvaluationTrendChart({ runs, title, height = 220 }: EvaluationTrendChartProps) {
  const data = useMemo(() => {
    return runs
      .filter((r) => r.started_at && r.status === "completed" && r.total_cases > 0)
      .map((r) => ({
        // Short label: HH:MM on date
        label: new Date(r.started_at!).toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }),
        passPct: Math.round((r.passed_cases / r.total_cases) * 100),
        // avg_score is stored 0–1, scale to 0–10 to match the per-run summary card
        score10: r.avg_score != null ? Number((r.avg_score * 10).toFixed(2)) : null,
        runName: r.run_name || r.dataset_name || "run",
      }))
      .reverse(); // listRuns returns newest-first; flip for time axis
  }, [runs]);

  if (data.length < 2) {
    return null;
  }

  return (
    <div className="w-full">
      {title && <div className="text-sm font-medium mb-2 text-muted-foreground">{title}</div>}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="opacity-10" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="pct" tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
          <YAxis yAxisId="score" orientation="right" tick={{ fontSize: 11 }} domain={[0, 10]} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 6 }}
            formatter={((value: any, name: any) =>
              name === "Pass rate" ? [`${value}%`, name] : [value, name]) as any}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            yAxisId="pct"
            type="monotone"
            dataKey="passPct"
            name="Pass rate"
            stroke="#10b981"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            yAxisId="score"
            type="monotone"
            dataKey="score10"
            name="Avg score (0–10)"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
