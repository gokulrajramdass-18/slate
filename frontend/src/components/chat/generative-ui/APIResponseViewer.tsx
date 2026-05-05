"use client";

import { useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ChevronRight,
  ChevronDown,
  Globe,
  Clock,
  Copy,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface APIResponseViewerProps {
  /** Display title */
  title?: string;
  /** Description / subtitle */
  description?: string;
  /** The JSON response data */
  data: unknown;
  /** HTTP status code */
  status_code?: number;
  /** Endpoint URL */
  endpoint?: string;
  /** HTTP method */
  method?: string;
  /** Response time in ms */
  execution_time_ms?: number;
  /** Initial expansion depth (default 1) */
  defaultExpandDepth?: number;
}

function JsonNode({
  keyName,
  value,
  depth,
  defaultExpandDepth,
}: {
  keyName?: string;
  value: unknown;
  depth: number;
  defaultExpandDepth: number;
}) {
  const [expanded, setExpanded] = useState(depth < defaultExpandDepth);

  if (value === null) {
    return (
      <span>
        {keyName != null && (
          <span className="text-purple-600 dark:text-purple-400">
            &quot;{keyName}&quot;
          </span>
        )}
        {keyName != null && ": "}
        <span className="text-gray-500 italic">null</span>
      </span>
    );
  }

  if (typeof value === "boolean") {
    return (
      <span>
        {keyName != null && (
          <span className="text-purple-600 dark:text-purple-400">
            &quot;{keyName}&quot;
          </span>
        )}
        {keyName != null && ": "}
        <span className="text-orange-600 dark:text-orange-400">
          {value ? "true" : "false"}
        </span>
      </span>
    );
  }

  if (typeof value === "number") {
    return (
      <span>
        {keyName != null && (
          <span className="text-purple-600 dark:text-purple-400">
            &quot;{keyName}&quot;
          </span>
        )}
        {keyName != null && ": "}
        <span className="text-blue-600 dark:text-blue-400">{value}</span>
      </span>
    );
  }

  if (typeof value === "string") {
    const truncated = value.length > 120;
    return (
      <span>
        {keyName != null && (
          <span className="text-purple-600 dark:text-purple-400">
            &quot;{keyName}&quot;
          </span>
        )}
        {keyName != null && ": "}
        <span className="text-green-600 dark:text-green-400">
          &quot;{truncated ? value.slice(0, 120) + "..." : value}&quot;
        </span>
      </span>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <span>
          {keyName != null && (
            <span className="text-purple-600 dark:text-purple-400">
              &quot;{keyName}&quot;
            </span>
          )}
          {keyName != null && ": "}
          <span className="text-gray-500">[]</span>
        </span>
      );
    }

    return (
      <div>
        <span
          className="cursor-pointer select-none inline-flex items-center"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronDown className="w-3 h-3 mr-0.5" />
          ) : (
            <ChevronRight className="w-3 h-3 mr-0.5" />
          )}
          {keyName != null && (
            <span className="text-purple-600 dark:text-purple-400">
              &quot;{keyName}&quot;
            </span>
          )}
          {keyName != null && ": "}
          <span className="text-gray-500">
            [{!expanded && `${value.length} items`}
          </span>
        </span>
        {expanded && (
          <div className="ml-4 border-l border-gray-200 dark:border-gray-700 pl-2">
            {value.map((item, idx) => (
              <div key={idx} className="py-0.5">
                <JsonNode
                  value={item}
                  depth={depth + 1}
                  defaultExpandDepth={defaultExpandDepth}
                />
                {idx < value.length - 1 && (
                  <span className="text-gray-400">,</span>
                )}
              </div>
            ))}
          </div>
        )}
        {expanded && <span className="text-gray-500">]</span>}
        {!expanded && <span className="text-gray-500">]</span>}
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return (
        <span>
          {keyName != null && (
            <span className="text-purple-600 dark:text-purple-400">
              &quot;{keyName}&quot;
            </span>
          )}
          {keyName != null && ": "}
          <span className="text-gray-500">{"{}"}</span>
        </span>
      );
    }

    return (
      <div>
        <span
          className="cursor-pointer select-none inline-flex items-center"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronDown className="w-3 h-3 mr-0.5" />
          ) : (
            <ChevronRight className="w-3 h-3 mr-0.5" />
          )}
          {keyName != null && (
            <span className="text-purple-600 dark:text-purple-400">
              &quot;{keyName}&quot;
            </span>
          )}
          {keyName != null && ": "}
          <span className="text-gray-500">
            {"{"}{!expanded && `${entries.length} keys`}
          </span>
        </span>
        {expanded && (
          <div className="ml-4 border-l border-gray-200 dark:border-gray-700 pl-2">
            {entries.map(([k, v], idx) => (
              <div key={k} className="py-0.5">
                <JsonNode
                  keyName={k}
                  value={v}
                  depth={depth + 1}
                  defaultExpandDepth={defaultExpandDepth}
                />
                {idx < entries.length - 1 && (
                  <span className="text-gray-400">,</span>
                )}
              </div>
            ))}
          </div>
        )}
        {expanded && <span className="text-gray-500">{"}"}</span>}
        {!expanded && <span className="text-gray-500">{"}"}</span>}
      </div>
    );
  }

  return <span className="text-gray-500">{String(value)}</span>;
}

export function APIResponseViewer({
  title,
  description,
  data,
  status_code,
  endpoint,
  method,
  execution_time_ms,
  defaultExpandDepth = 1,
}: APIResponseViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusColor =
    status_code != null
      ? status_code < 300
        ? "text-green-600 dark:text-green-400"
        : status_code < 400
          ? "text-yellow-600 dark:text-yellow-400"
          : "text-red-600 dark:text-red-400"
      : "";

  return (
    <Card className="w-full overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-base">
              <Globe className="w-4 h-4 text-primary-600" />
              {title ?? "API Response"}
            </CardTitle>
            {description && (
              <CardDescription>{description}</CardDescription>
            )}
          </div>
          <div className="flex items-center gap-2">
            {status_code != null && (
              <Badge
                variant="secondary"
                className={cn("text-xs", statusColor)}
              >
                {status_code}
              </Badge>
            )}
            {execution_time_ms != null && (
              <Badge variant="secondary" className="text-xs">
                <Clock className="w-3 h-3 mr-1" />
                {execution_time_ms}ms
              </Badge>
            )}
          </div>
        </div>

        {endpoint && (
          <div className="flex items-center gap-2 mt-2 text-xs text-gray-500 dark:text-gray-400 font-mono">
            {method && (
              <Badge variant="outline" className="text-xs uppercase">
                {method}
              </Badge>
            )}
            <span className="truncate">{endpoint}</span>
          </div>
        )}
      </CardHeader>

      <CardContent className="pt-0">
        <div className="relative">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className="absolute top-2 right-2 h-7 text-xs z-10"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 mr-1" /> Copied
              </>
            ) : (
              <>
                <Copy className="w-3 h-3 mr-1" /> Copy
              </>
            )}
          </Button>
          <div className="bg-gray-50 dark:bg-gray-900/50 rounded-md p-3 overflow-x-auto text-xs font-mono leading-relaxed max-h-96 overflow-y-auto">
            <JsonNode
              value={data}
              depth={0}
              defaultExpandDepth={defaultExpandDepth}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
