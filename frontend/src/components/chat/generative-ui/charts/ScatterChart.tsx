"use client";

import {
  ScatterChart as RechartsScatter,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ZAxis,
} from "recharts";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import type { ChartConfig } from "@/lib/types";

interface ScatterChartProps extends Omit<ChartConfig, "type"> {
  execution_time_ms?: number;
}

export function ScatterChart({
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
}: ScatterChartProps) {
  return (
    <Card className="w-full">
      <CardHeader>
        {title && <CardTitle className="text-base">{title}</CardTitle>}
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <RechartsScatter>
            {grid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis
              type="number"
              dataKey={xKey}
              name={xLabel || xKey}
              label={
                xLabel
                  ? { value: xLabel, position: "insideBottom", offset: -5 }
                  : undefined
              }
            />
            <YAxis
              type="number"
              dataKey={yKeys[0]}
              name={yLabel || yKeys[0]}
              label={
                yLabel
                  ? { value: yLabel, angle: -90, position: "insideLeft" }
                  : undefined
              }
            />
            <ZAxis range={[60, 400]} />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} />
            {legend && <Legend />}
            <Scatter
              name={yKeys[0]}
              data={data}
              fill={colors?.[0] || "#3b82f6"}
            />
          </RechartsScatter>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
