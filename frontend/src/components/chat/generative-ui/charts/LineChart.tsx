"use client";

import {
  LineChart as RechartsLine,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
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

interface LineChartProps extends Omit<ChartConfig, "type"> {
  execution_time_ms?: number;
}

export function LineChart({
  data,
  xKey,
  yKeys,
  title,
  description,
  colors,
  xLabel,
  yLabel,
  legend = true,
  grid = true,
}: LineChartProps) {
  return (
    <div className="w-full clear-both my-4 mb-8">
      <Card className="w-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 shadow-md">
        <CardHeader className="pb-4 border-b border-gray-100 dark:border-gray-800">
          {title && <CardTitle className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</CardTitle>}
          {description && <CardDescription className="text-sm mt-2 text-gray-600 dark:text-gray-400">{description}</CardDescription>}
        </CardHeader>
        <CardContent className="pt-6 pb-6">
          <ResponsiveContainer width="100%" height={500}>
          <RechartsLine data={data} margin={{ top: 10, right: 30, left: 20, bottom: 90 }}>
            {grid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-gray-700" />}
            <XAxis
              dataKey={xKey}
              angle={-45}
              textAnchor="end"
              height={120}
              tick={{ fill: '#6b7280', fontSize: 12 }}
              stroke="#9ca3af"
              label={
                xLabel
                  ? { value: xLabel, position: "insideBottom", offset: -60, style: { fill: '#6b7280', fontSize: 13, fontWeight: 500 } }
                  : undefined
              }
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 12 }}
              stroke="#9ca3af"
              label={
                yLabel
                  ? { value: yLabel, angle: -90, position: "insideLeft", style: { fill: '#6b7280', fontSize: 13, fontWeight: 500 } }
                  : undefined
              }
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
            {legend && <Legend verticalAlign="top" height={36} wrapperStyle={{ paddingBottom: '20px' }} />}
            {yKeys.map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors?.[idx] || `hsl(${idx * 60}, 70%, 50%)`}
                strokeWidth={3}
                dot={{ r: 4, strokeWidth: 2 }}
                activeDot={{ r: 6 }}
              />
            ))}
          </RechartsLine>
        </ResponsiveContainer>
      </CardContent>
    </Card>
    </div>
  );
}
