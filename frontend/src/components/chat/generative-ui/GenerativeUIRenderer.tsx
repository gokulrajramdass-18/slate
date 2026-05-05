"use client";

// Trigger auto-registration of all built-in generative UI components
import "@/lib/copilot/register-components";

import { useMemo } from "react";
import { componentRegistry } from "@/lib/copilot/component-registry";
import type { UIComponentData, ToolResultData } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AlertTriangle } from "lucide-react";

export interface GenerativeUIRendererProps {
  /** Parsed UI component definitions from the message */
  components?: UIComponentData[];
  /** Parsed tool results from the message */
  toolResults?: ToolResultData[];
  /** Layout direction for multiple components */
  layout?: "vertical" | "horizontal" | "grid";
  /** CSS class name override */
  className?: string;
}

/**
 * Renders generative UI components by resolving them from the component
 * registry. Handles both explicit UIComponentData (from the backend's
 * component generator) and implicit ToolResultData (matched via registry).
 */
export function GenerativeUIRenderer({
  components,
  toolResults,
  layout = "vertical",
  className,
}: GenerativeUIRendererProps) {
  const renderedElements = useMemo(() => {
    const elements: Array<{
      key: string;
      element: React.ReactNode;
    }> = [];

    // 1. Render explicit UI components
    if (components && components.length > 0) {
      console.log("[GenerativeUIRenderer] Rendering explicit UI components:", components.length);
      for (let i = 0; i < components.length; i++) {
        const comp = components[i];
        const element = renderUIComponent(comp, `ui-${i}`);
        if (element) {
          elements.push({ key: `ui-${i}`, element });
        }
      }

      // If we have explicit UI components, DON'T also render tool results
      // The backend has already converted tool results to UI components
      return elements;
    }

    // 2. Only render tool results if no explicit UI components were provided
    // This is a fallback for when the backend doesn't generate UI components
    if (toolResults && toolResults.length > 0) {
      console.log("[GenerativeUIRenderer] Rendering tool results as fallback:", toolResults.length);
      for (let i = 0; i < toolResults.length; i++) {
        const result = toolResults[i];
        const element = renderToolResult(result, `tool-${i}`);
        if (element) {
          elements.push({ key: `tool-${result.tool_call_id || i}`, element });
        }
      }
    }

    return elements;
  }, [components, toolResults]);

  if (renderedElements.length === 0) return null;

  const layoutClass =
    layout === "horizontal"
      ? "flex flex-row gap-8 overflow-x-auto pb-2"
      : layout === "grid"
        ? "grid grid-cols-1 lg:grid-cols-2 gap-8"
        : "flex flex-col gap-8";

  return (
    <div className={cn(layoutClass, className, "max-w-full")}>
      {renderedElements.map(({ key, element }) => (
        <div
          key={key}
          className={cn(
            layout === "horizontal" ? "flex-shrink-0 min-w-[400px] max-w-[600px]" : "w-full max-w-full",
            "relative" // Add relative positioning context
          )}
        >
          {element}
        </div>
      ))}
    </div>
  );
}

/**
 * Render a UIComponentData by looking up the component type in the registry
 * and passing the props through.
 */
function renderUIComponent(
  comp: UIComponentData,
  key: string
): React.ReactNode {
  try {
    console.log("[GenerativeUIRenderer] ===== RENDERING UI COMPONENT =====");
    console.log("[GenerativeUIRenderer] Component type:", comp.component_type);
    console.log("[GenerativeUIRenderer] Full component object:", JSON.stringify(comp, null, 2));
    console.log("[GenerativeUIRenderer] Props object:", comp.props);
    console.log("[GenerativeUIRenderer] Props.columns:", comp.props?.columns);
    console.log("[GenerativeUIRenderer] Props.rows:", comp.props?.rows);

    // Create a mock ToolResultData to match against registered components
    // Use component_type as the tool_name for direct matching
    const mockResult: ToolResultData = {
      tool_name: comp.component_type,
      tool_call_id: "",
      execution_time_ms: 0,
      result_type: "table" as any, // Dummy value
      data: null,
    };

    const Comp = componentRegistry.getComponent(mockResult);

    if (!Comp) {
      return <ComponentError key={key} type={comp.component_type} />;
    }

    const style: React.CSSProperties = {};
    if (comp.layout?.width) style.width = comp.layout.width;
    if (comp.layout?.height) style.height = comp.layout.height;

    // Pass props directly - components expect them unwrapped
    const props = comp.props || {};

    console.log("[GenerativeUIRenderer] Raw props before sanitization:", props);
    console.log("[GenerativeUIRenderer] Raw props keys:", Object.keys(props));

    // Sanitize props: ensure we only pass expected props for the component type
    // For hana_data_table, we expect: columns, rows, title, description, total_count, query, execution_time_ms, source_table
    const sanitizedProps: Record<string, any> = {};

    // Define allowed props per component type
    const allowedPropsMap: Record<string, string[]> = {
      'hana_data_table': ['columns', 'rows', 'title', 'description', 'total_count', 'query', 'execution_time_ms', 'source_table', 'maxDisplayRows'],
      'metric_card': ['title', 'value', 'description', 'unit', 'trend', 'change'],
      'time_series_chart': ['data', 'title', 'xKey', 'yKey', 'description'],
      'bar_chart': ['data', 'title', 'xKey', 'yKey', 'description'],
    };

    const allowedProps = allowedPropsMap[comp.component_type] || Object.keys(props);

    // Only copy allowed props
    for (const key of allowedProps) {
      if (key in props) {
        const value = props[key];

        // Skip problematic values
        if (value === undefined) continue;

        // For objects, check if they have the problematic keys
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          const objKeys = Object.keys(value);
          // Skip if it looks like a raw tool result (has success, data, count, duration_ms)
          if (objKeys.includes('success') && objKeys.includes('data') && objKeys.includes('count')) {
            console.warn(`[GenerativeUIRenderer] Skipping raw tool result in prop: ${key}`, value);
            continue;
          }
        }

        sanitizedProps[key] = value;
      }
    }

    console.log("[GenerativeUIRenderer] Sanitized props:", sanitizedProps);
    console.log("[GenerativeUIRenderer] Sanitized props keys:", Object.keys(sanitizedProps));
    console.log("[GenerativeUIRenderer] Columns in props:", sanitizedProps.columns);
    console.log("[GenerativeUIRenderer] Rows in props:", sanitizedProps.rows?.length);

    return (
      <div key={key} style={Object.keys(style).length > 0 ? style : undefined}>
        <Comp {...sanitizedProps} />
        {comp.children?.map((child, idx) =>
          renderUIComponent(child, `${key}-child-${idx}`)
        )}
      </div>
    );
  } catch (error) {
    console.error("[GenerativeUIRenderer] Error rendering component:", error);
    console.error("[GenerativeUIRenderer] Component type:", comp.component_type);
    console.error("[GenerativeUIRenderer] Component props:", comp.props);
    console.error("[GenerativeUIRenderer] Full component data:", JSON.stringify(comp, null, 2));
    return (
      <ComponentError
        key={key}
        type={`${comp.component_type} (render error)`}
      />
    );
  }
}

/**
 * Render a tool result by finding the best matching component in the registry.
 */
function renderToolResult(
  result: ToolResultData,
  key: string
): React.ReactNode {
  const Comp = componentRegistry.getComponent(result);

  if (!Comp) {
    // No component registered for this tool result type - skip silently
    // (the markdown renderer will handle text-type results)
    if (result.result_type === "text") return null;
    return <ComponentError key={key} type={`${result.tool_name}:${result.result_type}`} />;
  }

  // Build props from the tool result data
  let props: Record<string, any>;

  if (typeof result.data === "object" && result.data !== null) {
    // Handle chart data
    if (result.result_type === "chart" || result.visualization_hint) {
      const data = result.data as any;

      // If data has chart config structure, use it directly
      if (data.type && data.data && data.yKeys) {
        props = {
          type: data.type,
          data: data.data,
          xKey: data.xKey,
          yKeys: data.yKeys,
          colors: data.colors,
          title: data.title,
          description: data.description,
          xLabel: data.xLabel,
          yLabel: data.yLabel,
          legend: data.legend ?? true,
          grid: data.grid ?? true,
          stacked: data.stacked ?? false,
          execution_time_ms: result.execution_time_ms,
        };
      } else {
        // Fallback: assume data is array of points, infer structure
        const chartData = Array.isArray(data) ? data : [];
        let xKey = "x";
        let yKeys = ["y"];

        // Try to infer keys from first data point
        if (chartData.length > 0) {
          const firstPoint = chartData[0];
          const keys = Object.keys(firstPoint);
          if (keys.length > 0) {
            xKey = keys[0]; // First key as x-axis
            yKeys = keys.slice(1); // Rest as y-axes
          }
        }

        props = {
          type: result.visualization_hint as any || "line",
          data: chartData,
          xKey,
          yKeys,
          execution_time_ms: result.execution_time_ms,
        };
      }
    }
    // Transform HANA query results to HANADataTable props
    else if (result.result_type === "table" && "rows" in result.data) {
      const data = result.data as any;
      const rows = Array.isArray(data.rows) ? data.rows : [];

      // Process columns - convert string array to column objects if needed
      let columns = data.columns;
      if (Array.isArray(columns) && columns.length > 0) {
        // If columns is an array of strings, convert to column objects
        if (typeof columns[0] === "string") {
          columns = columns.map((colName: string, index: number) => {
            // Infer type from first row value
            const firstValue = rows.length > 0 ? rows[0][colName] : null;
            let type: string | undefined;

            if (typeof firstValue === "number") {
              type = "number";
            } else if (typeof firstValue === "boolean") {
              type = "boolean";
            } else if (firstValue instanceof Date || (typeof firstValue === "string" && !isNaN(Date.parse(firstValue)))) {
              type = "date";
            } else {
              type = "string";
            }

            return {
              key: colName || `col-${index}`, // Fallback to index if colName is empty
              label: colName ? colName.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()) : `Column ${index + 1}`,
              type,
              sortable: true,
            };
          });
        } else if (typeof columns[0] === "object") {
          // Columns are already objects, ensure they have key property
          columns = columns.map((col: any, index: number) => ({
            key: col.key || col.name || `col-${index}`,
            label: col.label || col.name || col.key || `Column ${index + 1}`,
            type: col.type || "string",
            sortable: col.sortable !== false,
            width: col.width,
          }));
        }
      } else {
        // Infer columns from first row if not provided
        columns = inferColumnsFromRows(rows);
      }

      props = {
        rows,
        columns,
        total_count: data.count ?? data.total_count ?? rows.length,
        execution_time_ms: data.duration_ms ?? result.execution_time_ms,
        query: data.query,
        source_table: data.source_table,
      };
    } else {
      // For other types, wrap data in a container to prevent object rendering
      props = {
        data: result.data,
        execution_time_ms: result.execution_time_ms
      };
    }
  } else {
    props = { data: result.data, execution_time_ms: result.execution_time_ms };
  }

  console.log("[GenerativeUIRenderer] Rendering tool result:", result.tool_name);
  console.log("[GenerativeUIRenderer] Result type:", result.result_type);
  console.log("[GenerativeUIRenderer] Props:", props);

  return <Comp key={key} {...props} />;
}

/**
 * Infer column definitions from row data
 */
function inferColumnsFromRows(rows: Array<Record<string, unknown>>): Array<{
  key: string;
  label: string;
  type?: string;
  sortable?: boolean;
}> {
  if (!rows || rows.length === 0) return [];

  const firstRow = rows[0];
  return Object.keys(firstRow).map((key) => {
    const value = firstRow[key];
    let type: string | undefined;

    // Infer type from value
    if (typeof value === "number") {
      type = "number";
    } else if (typeof value === "boolean") {
      type = "boolean";
    } else if (value instanceof Date || (typeof value === "string" && !isNaN(Date.parse(value)))) {
      type = "date";
    } else {
      type = "string";
    }

    return {
      key,
      label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()), // Convert snake_case to Title Case
      type,
      sortable: true,
    };
  });
}

/**
 * Fallback UI shown when a component type cannot be resolved.
 */
function ComponentError({ type }: { type: string }) {
  return (
    <div className="flex items-center gap-2 p-3 rounded-md bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 text-yellow-700 dark:text-yellow-400 text-sm">
      <AlertTriangle className="w-4 h-4 flex-shrink-0" />
      <span>
        Unknown component type: <code className="font-mono text-xs">{type}</code>
      </span>
    </div>
  );
}
