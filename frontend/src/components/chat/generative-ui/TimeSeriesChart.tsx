"use client";

import { useState, useMemo } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface TimeSeriesDataPoint {
  /** Timestamp or label for the x-axis */
  timestamp: string;
  /** Numeric value */
  value: number;
  /** Optional label for this data point */
  label?: string;
}

export interface TimeSeriesChartProps {
  /** Chart title */
  title?: string;
  /** Description */
  description?: string;
  /** Data series */
  data: TimeSeriesDataPoint[];
  /** Y-axis label */
  y_label?: string;
  /** X-axis label */
  x_label?: string;
  /** Line color */
  color?: string;
  /** Chart height in pixels */
  height?: number;
  /** Show area fill under line */
  showArea?: boolean;
  /** Show data point dots */
  showDots?: boolean;
}

const CHART_PADDING = { top: 20, right: 20, bottom: 40, left: 60 };

export function TimeSeriesChart({
  title,
  description,
  data,
  y_label,
  x_label,
  color = "#3b82f6",
  height = 240,
  showArea = true,
  showDots = true,
}: TimeSeriesChartProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const chartWidth = 600;
  const innerWidth = chartWidth - CHART_PADDING.left - CHART_PADDING.right;
  const innerHeight = height - CHART_PADDING.top - CHART_PADDING.bottom;

  const { minVal, maxVal, yTicks, points } = useMemo(() => {
    if (data.length === 0)
      return { minVal: 0, maxVal: 1, yTicks: [0], points: [] };

    const values = data.map((d) => d.value);
    let min = Math.min(...values);
    let max = Math.max(...values);

    // Add 10% padding to y range
    const range = max - min || 1;
    min = min - range * 0.05;
    max = max + range * 0.05;

    // Generate y-axis ticks (5 ticks)
    const tickCount = 5;
    const tickStep = (max - min) / (tickCount - 1);
    const ticks = Array.from({ length: tickCount }, (_, i) =>
      min + tickStep * i
    );

    // Map data to SVG coordinates
    const pts = data.map((d, i) => ({
      x: CHART_PADDING.left + (i / Math.max(data.length - 1, 1)) * innerWidth,
      y:
        CHART_PADDING.top +
        innerHeight -
        ((d.value - min) / (max - min)) * innerHeight,
      data: d,
    }));

    return { minVal: min, maxVal: max, yTicks: ticks, points: pts };
  }, [data, innerWidth, innerHeight]);

  if (data.length === 0) {
    return (
      <Card className="w-full">
        <CardContent className="flex items-center justify-center py-12 text-gray-500 dark:text-gray-400">
          No data available for chart.
        </CardContent>
      </Card>
    );
  }

  // Build SVG path for the line
  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
    .join(" ");

  // Build area path (line + close to bottom)
  const areaPath =
    linePath +
    ` L ${points[points.length - 1].x} ${CHART_PADDING.top + innerHeight}` +
    ` L ${points[0].x} ${CHART_PADDING.top + innerHeight} Z`;

  // X-axis label selection (show ~6 labels max)
  const xLabelStep = Math.max(1, Math.floor(data.length / 6));

  const formatTick = (val: number): string => {
    if (Math.abs(val) >= 1_000_000) return (val / 1_000_000).toFixed(1) + "M";
    if (Math.abs(val) >= 1_000) return (val / 1_000).toFixed(1) + "K";
    return val.toFixed(val % 1 === 0 ? 0 : 1);
  };

  const formatXLabel = (timestamp: string): string => {
    // Try to parse as date, otherwise use as-is
    const d = new Date(timestamp);
    if (!isNaN(d.getTime())) {
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
      }).format(d);
    }
    return timestamp.length > 10 ? timestamp.slice(0, 10) : timestamp;
  };

  return (
    <Card className="w-full overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            {title && (
              <CardTitle className="text-base">{title}</CardTitle>
            )}
            {description && (
              <CardDescription>{description}</CardDescription>
            )}
          </div>
          <Badge variant="secondary" className="text-xs">
            {data.length} points
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {/* Tooltip */}
        {hoveredIdx != null && points[hoveredIdx] && (
          <div className="text-xs text-gray-600 dark:text-gray-300 mb-1 font-mono">
            {formatXLabel(points[hoveredIdx].data.timestamp)}:{" "}
            <span className="font-bold" style={{ color }}>
              {points[hoveredIdx].data.value.toLocaleString()}
            </span>
            {points[hoveredIdx].data.label && (
              <span className="ml-2 text-gray-400">
                ({points[hoveredIdx].data.label})
              </span>
            )}
          </div>
        )}

        <svg
          viewBox={`0 0 ${chartWidth} ${height}`}
          className="w-full"
          style={{ maxHeight: height }}
          onMouseLeave={() => setHoveredIdx(null)}
        >
          {/* Grid lines */}
          {yTicks.map((tick, i) => {
            const y =
              CHART_PADDING.top +
              innerHeight -
              ((tick - minVal) / (maxVal - minVal)) * innerHeight;
            return (
              <g key={i}>
                <line
                  x1={CHART_PADDING.left}
                  x2={chartWidth - CHART_PADDING.right}
                  y1={y}
                  y2={y}
                  className="stroke-gray-200 dark:stroke-gray-700"
                  strokeWidth={1}
                  strokeDasharray="4 2"
                />
                <text
                  x={CHART_PADDING.left - 8}
                  y={y + 4}
                  textAnchor="end"
                  className="fill-gray-400 dark:fill-gray-500"
                  fontSize={10}
                >
                  {formatTick(tick)}
                </text>
              </g>
            );
          })}

          {/* X-axis labels */}
          {points.map(
            (p, i) =>
              i % xLabelStep === 0 && (
                <text
                  key={i}
                  x={p.x}
                  y={height - 8}
                  textAnchor="middle"
                  className="fill-gray-400 dark:fill-gray-500"
                  fontSize={10}
                >
                  {formatXLabel(p.data.timestamp)}
                </text>
              )
          )}

          {/* Area fill */}
          {showArea && (
            <path d={areaPath} fill={color} opacity={0.1} />
          )}

          {/* Line */}
          <path
            d={linePath}
            fill="none"
            stroke={color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {/* Dots & hover targets */}
          {points.map((p, i) => (
            <g key={i}>
              {/* Larger invisible hit area */}
              <circle
                cx={p.x}
                cy={p.y}
                r={12}
                fill="transparent"
                onMouseEnter={() => setHoveredIdx(i)}
              />
              {/* Visible dot */}
              {(showDots || hoveredIdx === i) && (
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={hoveredIdx === i ? 4 : 2.5}
                  fill={color}
                  stroke="white"
                  strokeWidth={hoveredIdx === i ? 2 : 1}
                  className="transition-all"
                />
              )}
            </g>
          ))}

          {/* Axis labels */}
          {y_label && (
            <text
              x={14}
              y={CHART_PADDING.top + innerHeight / 2}
              textAnchor="middle"
              transform={`rotate(-90, 14, ${CHART_PADDING.top + innerHeight / 2})`}
              className="fill-gray-500 dark:fill-gray-400"
              fontSize={11}
            >
              {y_label}
            </text>
          )}
          {x_label && (
            <text
              x={CHART_PADDING.left + innerWidth / 2}
              y={height - 0}
              textAnchor="middle"
              className="fill-gray-500 dark:fill-gray-400"
              fontSize={11}
            >
              {x_label}
            </text>
          )}
        </svg>
      </CardContent>
    </Card>
  );
}
