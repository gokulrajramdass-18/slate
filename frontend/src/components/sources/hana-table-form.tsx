"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Database, Table as TableIcon, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { TagInput } from "@/components/ui/tag-input";
import { SyncSettings } from "./sync-settings";
import { sourcesApi } from "@/lib/api/sources";
import { hanaConnectionsApi } from "@/lib/api/hana-connections";
import { toast } from "sonner";
import type { SyncConfig } from "@/lib/types";
import Link from "next/link";

interface HanaTableFormProps {
  onSubmit: (data: {
    name: string;
    notebook_id?: string;
    description?: string;
    tags?: string[];
    config: {
      connection_id: string;
      table_name: string;
      content_columns: string[];
      key_column?: string;
    };
    sync_frequency: string;
  }) => Promise<void>;
  isLoading?: boolean;
  notebookId?: string;
}

interface FormData {
  title: string;
  table: string;
}

interface TableInfo {
  schema_name: string;
  table_name: string;
  table_type: string;
  record_count?: number;
  columns?: string[];
}

export function HanaTableForm({ onSubmit, isLoading = false, notebookId }: HanaTableFormProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [loadingTables, setLoadingTables] = useState(false);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [selectedTable, setSelectedTable] = useState<TableInfo | null>(null);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [syncConfig, setSyncConfig] = useState<SyncConfig>({
    enabled: false,
    frequency: "manual",
    status: "idle",
  });

  // Fetch saved HANA connections
  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: ["hana-connections"],
    queryFn: hanaConnectionsApi.list,
  });

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormData>();

  const watchedTable = watch("table");

  // Load tables when connection is selected
  const handleConnectionSelect = async (connectionId: string) => {
    setSelectedConnectionId(connectionId);
    setTables([]);
    setSelectedTable(null);
    setSelectedColumns([]);
    setValue("table", "");

    if (!connectionId) return;

    setLoadingTables(true);
    try {
      const tableList = await hanaConnectionsApi.listTables(connectionId);

      if (tableList && tableList.length > 0) {
        setTables(tableList);
        toast.success(`Found ${tableList.length} tables`);
      } else {
        setTables([]);
        toast.warning("No tables found in this connection");
      }
    } catch (error: any) {
      console.error("Error fetching tables:", error);
      toast.error(`Failed to load tables: ${error.message || "Unknown error"}`);
      setTables([]);
    } finally {
      setLoadingTables(false);
    }
  };

  const handleTableSelect = async (fullTableName: string) => {
    setValue("table", fullTableName);
    const table = tables.find(t => `${t.schema_name}.${t.table_name}` === fullTableName);

    if (table && selectedConnectionId) {
      setSelectedTable(table);
      setSelectedColumns([]);

      // Fetch columns for the selected table
      try {
        const columns = await hanaConnectionsApi.listColumns(
          selectedConnectionId,
          table.table_name,
          table.schema_name
        );

        if (columns && columns.length > 0) {
          // Update table with columns
          const updatedTable = { ...table, columns };
          setSelectedTable(updatedTable);
          // Auto-select all columns by default
          setSelectedColumns(columns);
          toast.success(`Loaded ${columns.length} columns`);
        } else {
          toast.warning("No columns found for this table");
        }
      } catch (error: any) {
        console.error("Error fetching columns:", error);
        toast.error(`Failed to load columns: ${error.message || "Unknown error"}`);
      }
    }
  };

  const handleFormSubmit = async (data: FormData) => {
    if (!selectedConnectionId) {
      toast.error("Please select a connection");
      return;
    }

    if (!data.table) {
      toast.error("Please select a table");
      return;
    }

    if (selectedColumns.length === 0) {
      toast.error("Please select at least one column");
      return;
    }

    await onSubmit({
      name: data.title || data.table,
      notebook_id: notebookId,
      description: `HANA table: ${data.table}`,
      tags: tags,
      config: {
        connection_id: selectedConnectionId,
        table_name: data.table,
        content_columns: selectedColumns,
        key_column: "id",
      },
      sync_frequency: syncConfig.enabled ? syncConfig.frequency : "manual",
    });
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
      {/* Connection Selection */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                HANA Connection
              </CardTitle>
              <CardDescription>Select a saved HANA database connection</CardDescription>
            </div>
            <Link href="/settings/hana-connections">
              <Button type="button" variant="outline" size="sm">
                <Settings className="h-4 w-4 mr-2" />
                Manage Connections
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="connection">
              Connection <span className="text-red-500">*</span>
            </Label>
            {connectionsLoading ? (
              <div className="flex items-center gap-2 p-3 border rounded-md">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm text-gray-500">Loading connections...</span>
              </div>
            ) : connections && connections.length > 0 ? (
              <Select
                value={selectedConnectionId}
                onValueChange={handleConnectionSelect}
                disabled={isLoading || loadingTables}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a connection" />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                  {connections.map((conn) => (
                    <SelectItem key={conn.id} value={conn.id}>
                      <div className="flex flex-col">
                        <span className="font-medium">{conn.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {conn.host}:{conn.port} · {conn.database}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <div className="p-4 border border-dashed rounded-md text-center">
                <p className="text-sm text-gray-500 mb-3">No HANA connections configured</p>
                <Link href="/settings/hana-connections">
                  <Button type="button" variant="outline" size="sm">
                    <Settings className="h-4 w-4 mr-2" />
                    Create Connection
                  </Button>
                </Link>
              </div>
            )}
          </div>

          {loadingTables && (
            <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-md">
              <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
              <span className="text-sm text-blue-900 dark:text-blue-100">Loading tables...</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Table Selection */}
      {tables.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TableIcon className="h-5 w-5" />
              Table Selection
            </CardTitle>
            <CardDescription>Choose a table and columns to import ({tables.length} tables available)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="table">
                Table <span className="text-red-500">*</span>
              </Label>
              <Select
                value={watchedTable}
                onValueChange={handleTableSelect}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a table" />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 max-h-[300px]">
                  {tables.map((table) => {
                    const fullName = `${table.schema_name}.${table.table_name}`;
                    return (
                      <SelectItem key={fullName} value={fullName}>
                        <div className="flex flex-col">
                          <span className="font-medium">{table.table_name}</span>
                          <span className="text-xs text-muted-foreground">
                            {table.schema_name} · {table.table_type}
                            {table.record_count != null && ` · ${table.record_count.toLocaleString()} rows`}
                          </span>
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            {selectedTable && selectedTable.columns && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Columns ({selectedColumns.length} of {selectedTable.columns.length} selected)</Label>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedColumns(selectedTable.columns || [])}
                    >
                      Select All
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedColumns([])}
                    >
                      Clear All
                    </Button>
                  </div>
                </div>
                <div className="border rounded-md p-4 max-h-64 overflow-y-auto space-y-2">
                  {selectedTable.columns.map((column: string) => (
                    <div key={column} className="flex items-center space-x-2">
                      <Checkbox
                        id={column}
                        checked={selectedColumns.includes(column)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedColumns([...selectedColumns, column]);
                          } else {
                            setSelectedColumns(selectedColumns.filter((c) => c !== column));
                          }
                        }}
                      />
                      <label htmlFor={column} className="text-sm flex-1 cursor-pointer font-mono">
                        {column}
                      </label>
                    </div>
                  ))}
                </div>

                {/* Chat Integration Help */}
                {selectedColumns.length > 0 && (
                  <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md space-y-2">
                    <div className="flex items-start gap-2">
                      <div className="mt-0.5">
                        <svg
                          className="h-5 w-5 text-blue-600 dark:text-blue-400"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                      </div>
                      <div className="flex-1 space-y-1">
                        <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                          💬 Chat Integration with Live Data
                        </p>
                        <p className="text-sm text-blue-700 dark:text-blue-300">
                          When you chat with this notebook, the AI can query this HANA table directly using the selected columns.
                          No sync or embeddings required — always live, up-to-date data!
                        </p>
                        <p className="text-xs text-blue-600 dark:text-blue-400 mt-2 font-mono bg-blue-100/50 dark:bg-blue-950/50 p-2 rounded">
                          Available columns: {selectedColumns.join(", ")}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Debug Info - Remove in production */}
      {process.env.NODE_ENV === 'development' && (
        <Card className="bg-gray-50 dark:bg-gray-900">
          <CardHeader>
            <CardTitle className="text-sm">Debug Info</CardTitle>
          </CardHeader>
          <CardContent className="text-xs space-y-1">
            <div>Selected Connection: <span className="font-mono">{selectedConnectionId || "none"}</span></div>
            <div>Tables Count: <span className="font-mono">{tables.length}</span></div>
            <div>Selected Table: <span className="font-mono">{selectedTable?.table_name || "none"}</span></div>
          </CardContent>
        </Card>
      )}

      {/* Source Details */}
      <Card>
        <CardHeader>
          <CardTitle>Source Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title (optional)</Label>
            <Input
              id="title"
              placeholder="Auto-generated from table name"
              {...register("title")}
              disabled={isLoading}
            />
          </div>

          <TagInput
            label="Tags (optional)"
            value={tags}
            onChange={setTags}
            placeholder="Type and press Enter to add tags"
            disabled={isLoading}
          />
        </CardContent>
      </Card>

      {/* Sync Settings */}
      <SyncSettings config={syncConfig} onChange={setSyncConfig} />

      {/* Submit */}
      <div className="flex justify-end gap-3">
        <Button type="submit" disabled={!selectedConnectionId || !watchedTable || isLoading || loadingTables}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Add HANA Table Source
        </Button>
      </div>
    </form>
  );
}
