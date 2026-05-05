"use client";

import { BarChart } from "@/components/chat/generative-ui/charts/BarChart";
import { PieChart } from "@/components/chat/generative-ui/charts/PieChart";
import { LineChart } from "@/components/chat/generative-ui/charts/LineChart";
import { AreaChart } from "@/components/chat/generative-ui/charts/AreaChart";

interface ChartRendererProps {
  html: string;
}

export function ChartRenderer({ html }: ChartRendererProps) {
  // Parse HTML and extract chart tags
  const renderContent = () => {
    if (!html) return null;

    // Split by <chart> tags
    const parts: React.ReactElement[] = [];
    const chartRegex = /<chart\s+([^>]+)\s*\/>/gi;

    let lastIndex = 0;
    let match;
    let key = 0;

    while ((match = chartRegex.exec(html)) !== null) {
      // Add HTML before chart
      if (match.index > lastIndex) {
        const htmlBefore = html.substring(lastIndex, match.index);
        parts.push(
          <div
            key={`html-${key}`}
            dangerouslySetInnerHTML={{ __html: htmlBefore }}
            className="prose prose-sm dark:prose-invert max-w-none"
          />
        );
      }

      // Parse chart attributes
      const attrs = match[1];
      const typeMatch = attrs.match(/type="([^"]+)"/);
      const dataMatch = attrs.match(/data='([^']+)'/);
      const xKeyMatch = attrs.match(/xKey="([^"]+)"/);
      const yKeysMatch = attrs.match(/yKeys='(\[[^\]]+\])'/);
      const titleMatch = attrs.match(/title="([^"]+)"/);

      if (typeMatch && dataMatch) {
        const type = typeMatch[1];
        const dataStr = dataMatch[1];
        const xKey = xKeyMatch ? xKeyMatch[1] : "label";
        const yKeysStr = yKeysMatch ? yKeysMatch[1] : '["value"]';
        const title = titleMatch ? titleMatch[1] : "";

        try {
          const data = JSON.parse(dataStr);
          const yKeys = JSON.parse(yKeysStr);

          // Render appropriate chart
          switch (type) {
            case "bar":
              parts.push(
                <div key={`chart-${key}`} className="my-6">
                  <BarChart
                    data={data}
                    xKey={xKey}
                    yKeys={yKeys}
                    title={title}
                  />
                </div>
              );
              break;
            case "pie":
              parts.push(
                <div key={`chart-${key}`} className="my-6">
                  <PieChart
                    data={data}
                    xKey={xKey}
                    yKeys={yKeys}
                    title={title}
                  />
                </div>
              );
              break;
            case "line":
              parts.push(
                <div key={`chart-${key}`} className="my-6">
                  <LineChart
                    data={data}
                    xKey={xKey}
                    yKeys={yKeys}
                    title={title}
                  />
                </div>
              );
              break;
            case "area":
              parts.push(
                <div key={`chart-${key}`} className="my-6">
                  <AreaChart
                    data={data}
                    xKey={xKey}
                    yKeys={yKeys}
                    title={title}
                  />
                </div>
              );
              break;
            default:
              // Unknown chart type - show as text
              parts.push(
                <div key={`chart-${key}`} className="my-4 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    Unsupported chart type: {type}
                  </p>
                </div>
              );
          }
        } catch (e) {
          // Invalid JSON - show error
          parts.push(
            <div key={`chart-${key}`} className="my-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded">
              <p className="text-sm text-red-800 dark:text-red-200">
                Failed to parse chart data: {e instanceof Error ? e.message : "Unknown error"}
              </p>
            </div>
          );
        }
      }

      lastIndex = chartRegex.lastIndex;
      key++;
    }

    // Add remaining HTML after last chart
    if (lastIndex < html.length) {
      const htmlAfter = html.substring(lastIndex);
      parts.push(
        <div
          key={`html-${key}`}
          dangerouslySetInnerHTML={{ __html: htmlAfter }}
          className="prose prose-sm dark:prose-invert max-w-none"
        />
      );
    }

    return parts.length > 0 ? parts : (
      <div
        dangerouslySetInnerHTML={{ __html: html }}
        className="prose prose-sm dark:prose-invert max-w-none"
      />
    );
  };

  return <div className="space-y-4">{renderContent()}</div>;
}
