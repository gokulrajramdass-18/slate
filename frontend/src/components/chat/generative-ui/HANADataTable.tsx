"use client";

import { useState, useMemo } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Database,
  Download,
  Search,
  Clock,
  Table2,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface HANADataTableProps {
  /** Display title for the table */
  title?: string;
  /** Optional description / subtitle */
  description?: string;
  /** Column definitions */
  columns: Array<{
    key: string;
    label: string;
    type?: "string" | "number" | "date" | "boolean";
    sortable?: boolean;
    width?: string;
  }>;
  /** Row data - array of objects keyed by column key */
  rows: Array<Record<string, unknown>>;
  /** Total row count (may exceed rows.length if paginated) */
  total_count?: number;
  /** SQL query that produced the data */
  query?: string;
  /** Query execution time in ms */
  execution_time_ms?: number;
  /** Source schema.table */
  source_table?: string;
  /** Maximum rows to display before truncation */
  maxDisplayRows?: number;
}

type SortDirection = "asc" | "desc" | null;

interface SortState {
  key: string;
  direction: SortDirection;
}

export function HANADataTable({
  title,
  description,
  columns,
  rows,
  total_count,
  query,
  execution_time_ms,
  source_table,
  maxDisplayRows = 100,
}: HANADataTableProps) {
  console.log("[HANADataTable] Received props:", {
    title,
    description,
    columnsLength: columns?.length,
    rowsLength: rows?.length,
    columns: columns,
    firstRow: rows?.[0],
    total_count,
    query,
    execution_time_ms,
    source_table,
    allProps: arguments[0]
  });

  // Validate and normalize columns
  const normalizedColumns = useMemo(() => {
    if (!Array.isArray(columns) || columns.length === 0) {
      console.error("[HANADataTable] No valid columns array:", columns);
      return [];
    }

    // Ensure each column has a unique key
    const seen = new Set<string>();
    return columns.map((col, index) => {
      let uniqueKey = col.key || `col-${index}`;

      // If key is duplicate, append index
      if (seen.has(uniqueKey)) {
        uniqueKey = `${uniqueKey}-${index}`;
      }
      seen.add(uniqueKey);

      return {
        ...col,
        key: uniqueKey,
      };
    });
  }, [columns]);

  console.log("[HANADataTable] Normalized columns:", normalizedColumns);

  // Validate inputs
  if (normalizedColumns.length === 0) {
    return (
      <Card className="w-full">
        <CardContent className="p-4">
          <p className="text-sm text-gray-500">No columns defined for table</p>
        </CardContent>
      </Card>
    );
  }

  if (!Array.isArray(rows)) {
    return (
      <Card className="w-full">
        <CardContent className="p-4">
          <p className="text-sm text-gray-500">Invalid row data</p>
        </CardContent>
      </Card>
    );
  }

  const [sort, setSort] = useState<SortState | null>(null);
  const [filter, setFilter] = useState("");
  const [showQuery, setShowQuery] = useState(false);

  // Filter rows by search term across all columns
  const filteredRows = useMemo(() => {
    if (!filter) return rows;
    const term = filter.toLowerCase();
    return rows.filter((row) =>
      normalizedColumns.some((col) => {
        const val = row[col.key];
        return val != null && String(val).toLowerCase().includes(term);
      })
    );
  }, [rows, normalizedColumns, filter]);

  // Sort filtered rows
  const sortedRows = useMemo(() => {
    if (!sort || !sort.direction) return filteredRows;
    const col = normalizedColumns.find((c) => c.key === sort.key);
    return [...filteredRows].sort((a, b) => {
      const aVal = a[sort.key];
      const bVal = b[sort.key];
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      let cmp: number;
      if (col?.type === "number") {
        cmp = Number(aVal) - Number(bVal);
      } else if (col?.type === "date") {
        cmp = new Date(String(aVal)).getTime() - new Date(String(bVal)).getTime();
      } else {
        cmp = String(aVal).localeCompare(String(bVal));
      }
      return sort.direction === "desc" ? -cmp : cmp;
    });
  }, [filteredRows, sort, normalizedColumns]);

  const displayRows = sortedRows.slice(0, maxDisplayRows);
  const truncated = sortedRows.length > maxDisplayRows;
  const displayTotal = total_count ?? rows.length;

  const handleSort = (key: string) => {
    const col = normalizedColumns.find((c) => c.key === key);
    if (col?.sortable === false) return;
    setSort((prev) => {
      if (prev?.key !== key) return { key, direction: "asc" };
      if (prev.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  };

  const handleExportCSV = () => {
    const header = normalizedColumns.map((c) => c.label).join(",");
    const csvRows = sortedRows.map((row) =>
      normalizedColumns
        .map((c) => {
          const val = row[c.key];
          const str = val == null ? "" : String(val);
          return str.includes(",") || str.includes('"')
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        })
        .join(",")
    );
    const csv = [header, ...csvRows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${source_table ?? "hana-data"}-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const SortIcon = ({ colKey }: { colKey: string }) => {
    if (sort?.key !== colKey || !sort?.direction) {
      return <ArrowUpDown className="w-3 h-3 ml-1 opacity-40" />;
    }
    return sort.direction === "asc" ? (
      <ArrowUp className="w-3 h-3 ml-1" />
    ) : (
      <ArrowDown className="w-3 h-3 ml-1" />
    );
  };

  const formatCell = (value: unknown, type?: string): string => {
    if (value == null) return "--";

    // Handle objects that shouldn't be rendered directly
    if (typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }

    if (type === "boolean") return value ? "Yes" : "No";
    if (type === "number" && typeof value === "number") {
      return value.toLocaleString();
    }
    return String(value);
  };

  return (
    <Card className="w-full overflow-x-auto">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-base">
              <Database className="w-4 h-4 text-primary-600" />
              {title ?? source_table ?? "HANA Query Results"}
            </CardTitle>
            {description && (
              <CardDescription>{description}</CardDescription>
            )}
          </div>
          <div className="flex items-center gap-2">
            {execution_time_ms != null && (
              <Badge variant="secondary" className="text-xs">
                <Clock className="w-3 h-3 mr-1" />
                {execution_time_ms}ms
              </Badge>
            )}
            <Badge variant="secondary" className="text-xs">
              <Table2 className="w-3 h-3 mr-1" />
              {displayTotal.toLocaleString()} rows
            </Badge>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 mt-3">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-gray-400" />
            <Input
              placeholder="Filter results..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="pl-8 h-8 text-sm"
            />
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleExportCSV}
            className="h-8 text-xs"
          >
            <Download className="w-3.5 h-3.5 mr-1" />
            CSV
          </Button>
          {query && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowQuery((v) => !v)}
              className="h-8 text-xs"
            >
              SQL
            </Button>
          )}
        </div>

        {/* Query display */}
        {showQuery && query && (
          <pre className="mt-2 p-3 bg-gray-900 text-gray-100 rounded-md text-xs overflow-x-auto font-mono">
            {query}
          </pre>
        )}
      </CardHeader>

      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-max">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50">
                {normalizedColumns.map((col) => (
                  <th
                    key={col.key}
                    className={cn(
                      "px-4 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider",
                      col.sortable !== false && "cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200"
                    )}
                    style={col.width ? { width: col.width } : undefined}
                    onClick={() => handleSort(col.key)}
                  >
                    <span className="flex items-center">
                      {col.label}
                      {col.sortable !== false && <SortIcon colKey={col.key} />}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {displayRows.length === 0 ? (
                <tr>
                  <td
                    colSpan={normalizedColumns.length}
                    className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
                  >
                    {filter ? "No rows match the filter." : "No data available."}
                  </td>
                </tr>
              ) : (
                displayRows.map((row, idx) => (
                  <tr
                    key={idx}
                    className="hover:bg-gray-50 dark:hover:bg-gray-900/30 transition-colors"
                  >
                    {normalizedColumns.map((col) => (
                      <td
                        key={col.key}
                        className={cn(
                          "px-4 py-2 text-gray-900 dark:text-gray-100",
                          col.type === "number" && "text-right font-mono"
                        )}
                      >
                        {formatCell(row[col.key], col.type)}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CardContent>

      {(truncated || filter) && (
        <CardFooter className="text-xs text-gray-500 dark:text-gray-400 py-2 px-4">
          {filter
            ? `Showing ${displayRows.length} of ${filteredRows.length} filtered results`
            : `Showing ${displayRows.length} of ${sortedRows.length} rows`}
          {truncated && ` (limited to ${maxDisplayRows})`}
        </CardFooter>
      )}
    </Card>
  );
}
