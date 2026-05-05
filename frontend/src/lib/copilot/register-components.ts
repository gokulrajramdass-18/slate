/**
 * Auto-registration of all generative UI components with the component registry.
 *
 * Import this module once (e.g., from GenerativeUIRenderer) to register all
 * built-in components. Components are matched to tool results by their
 * matcher functions and prioritized by the priority field.
 */
import { componentRegistry } from "./component-registry";
import { HANADataTable } from "@/components/chat/generative-ui/HANADataTable";
import { APIResponseViewer } from "@/components/chat/generative-ui/APIResponseViewer";
import { MetricCard } from "@/components/chat/generative-ui/MetricCard";
import { ChartRenderer } from "@/components/chat/generative-ui/ChartRenderer";

// Direct component type registrations (for backend-generated component specs)
componentRegistry.register({
  name: "hana_data_table",
  component: HANADataTable,
  matcher: (result) => result.tool_name === "hana_data_table",
  priority: 150,
});

componentRegistry.register({
  name: "metric_card",
  component: MetricCard,
  matcher: (result) => result.tool_name === "metric_card",
  priority: 150,
});

componentRegistry.register({
  name: "json_viewer",
  component: APIResponseViewer,
  matcher: (result) => result.tool_name === "json_viewer",
  priority: 150,
});

// Universal Chart Renderer - highest priority for chart results
componentRegistry.register({
  name: "chart_renderer",
  component: ChartRenderer,
  matcher: (result) =>
    result.result_type === "chart" ||
    result.tool_name === "chart" ||
    (result.result_type === "table" && result.visualization_hint !== undefined && result.visualization_hint !== "time_series"),
  priority: 150,
});

// HANA Data Table - matches query_hana tool with table result type
componentRegistry.register({
  name: "hana_data_table_tool",
  component: HANADataTable,
  matcher: (result) =>
    result.tool_name.includes("query_hana") &&
    result.result_type === "table" &&
    !result.visualization_hint,
  priority: 100,
});

// API Response Viewer - matches API tool calls with json result type
componentRegistry.register({
  name: "api_response_viewer",
  component: APIResponseViewer,
  matcher: (result) =>
    (result.tool_name.includes("api") ||
      result.tool_name.includes("fetch") ||
      result.tool_name.includes("request")) &&
    result.result_type === "json",
  priority: 90,
});

// Metric Card - matches metric result types
componentRegistry.register({
  name: "metric_card_tool",
  component: MetricCard,
  matcher: (result) => result.result_type === "metric",
  priority: 80,
});

// Generic table fallback - any table result type not handled above
componentRegistry.register({
  name: "generic_data_table",
  component: HANADataTable,
  matcher: (result) => result.result_type === "table",
  priority: 10,
});

// Generic JSON fallback - any json result type not handled above
componentRegistry.register({
  name: "generic_json_viewer",
  component: APIResponseViewer,
  matcher: (result) => result.result_type === "json",
  priority: 10,
});

