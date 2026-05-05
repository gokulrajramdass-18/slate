"use client";

import {
  PieChart as RechartsPie,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import type { ChartConfig } from "@/lib/types";

interface PieChartProps extends Omit<ChartConfig, "type"> {
  execution_time_ms?: number;
}

export function PieChart({
  data,
  xKey,
  yKeys,
  title,
  description,
  colors,
  legend = true,
}: PieChartProps) {
  // For pie charts, we use the first yKey as the value
  const valueKey = yKeys[0];
  const nameKey = xKey || "name";

  // Default colors if not provided
  const defaultColors = [
    "#3b82f6",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#ec4899",
    "#14b8a6",
    "#f97316",
  ];
  const chartColors = colors || defaultColors;

  return (
    <div className="w-full clear-both my-12">
      <Card className="w-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 shadow-md">
        <CardHeader className="pb-4 border-b border-gray-100 dark:border-gray-800">
          {title && <CardTitle className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</CardTitle>}
          {description && <CardDescription className="text-sm mt-2 text-gray-600 dark:text-gray-400">{description}</CardDescription>}
        </CardHeader>
        <CardContent className="pt-6 pb-6">
          <ResponsiveContainer width="100%" height={450}>
          <RechartsPie margin={{ top: 10, right: 20, left: 20, bottom: 20 }}>
            <Pie
              data={data}
              dataKey={valueKey}
              nameKey={nameKey}
              cx="50%"
              cy="50%"
              outerRadius={120}
              label={(entry: any) => {
                const value = entry[valueKey];
                const formattedValue = typeof value === 'number' ? value.toLocaleString() : value;
                return `${entry[nameKey]}: ${formattedValue}`;
              }}
              labelLine={{ stroke: '#9ca3af' }}
              stroke="#fff"
              strokeWidth={2}
            >
              {data.map((_, idx) => (
                <Cell
                  key={`cell-${idx}`}
                  fill={chartColors[idx % chartColors.length]}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: 'white',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
              }}
              labelStyle={{ color: '#111827', fontWeight: 600 }}
            />
            {legend && <Legend wrapperStyle={{ paddingTop: '20px' }} />}
          </RechartsPie>
        </ResponsiveContainer>
      </CardContent>
    </Card>
    </div>
  );
}
