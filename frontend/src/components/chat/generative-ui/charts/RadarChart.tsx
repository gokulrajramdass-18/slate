"use client";

import {
  RadarChart as RechartsRadar,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
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

interface RadarChartProps extends Omit<ChartConfig, "type"> {
  execution_time_ms?: number;
}

export function RadarChart({
  data,
  xKey,
  yKeys,
  title,
  description,
  colors,
  legend = true,
}: RadarChartProps) {
  return (
    <div className="w-full clear-both my-12">
      <Card className="w-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 shadow-md">
        <CardHeader className="pb-4 border-b border-gray-100 dark:border-gray-800">
          {title && <CardTitle className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</CardTitle>}
          {description && <CardDescription className="text-sm mt-2 text-gray-600 dark:text-gray-400">{description}</CardDescription>}
        </CardHeader>
        <CardContent className="pt-6 pb-6">
          <ResponsiveContainer width="100%" height={450}>
          <RechartsRadar data={data} margin={{ top: 10, right: 50, bottom: 20, left: 50 }}>
            <PolarGrid stroke="#e5e7eb" className="dark:stroke-gray-700" />
            <PolarAngleAxis
              dataKey={xKey}
              tick={{ fill: '#6b7280', fontSize: 12 }}
              stroke="#9ca3af"
            />
            <PolarRadiusAxis
              tick={{ fill: '#6b7280', fontSize: 11 }}
              stroke="#9ca3af"
            />
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
            {yKeys.map((key, idx) => (
              <Radar
                key={key}
                name={key}
                dataKey={key}
                stroke={colors?.[idx] || `hsl(${idx * 60}, 70%, 50%)`}
                fill={colors?.[idx] || `hsl(${idx * 60}, 70%, 50%)`}
                fillOpacity={0.3}
                strokeWidth={2}
              />
            ))}
          </RechartsRadar>
        </ResponsiveContainer>
      </CardContent>
    </Card>
    </div>
  );
}
