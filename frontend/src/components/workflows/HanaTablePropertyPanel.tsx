"use client";

import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface Condition {
  column: string;
  operator: string;
  value: string;
}

interface HanaTablePropertyPanelProps {
  selectedNode: any;
  handleUpdate: (key: string, value: any) => void;
}

const OPERATORS = [
  { value: "=", label: "Equals (=)" },
  { value: "!=", label: "Not Equals (!=)" },
  { value: ">", label: "Greater Than (>)" },
  { value: "<", label: "Less Than (<)" },
  { value: ">=", label: "Greater or Equal (>=)" },
  { value: "<=", label: "Less or Equal (<=)" },
  { value: "LIKE", label: "Like (LIKE)" },
  { value: "IN", label: "In (IN)" },
  { value: "IS NULL", label: "Is Null" },
  { value: "IS NOT NULL", label: "Is Not Null" },
];

export function HanaTablePropertyPanel({ selectedNode, handleUpdate }: HanaTablePropertyPanelProps) {
  const [selectedConnection, setSelectedConnection] = useState(selectedNode.data.config.hana_connection_id || "");
  const [selectedTable, setSelectedTable] = useState(selectedNode.data.config.hana_table_name || "");
  const [conditions, setConditions] = useState<Condition[]>(selectedNode.data.config.conditions || []);

  // Sync local state with node config when node changes (e.g., after workflow load)
  useEffect(() => {
    console.log('[HanaTablePropertyPanel] Syncing from node config');
    console.log('[HanaTablePropertyPanel] Node ID:', selectedNode.id);
    console.log('[HanaTablePropertyPanel] Node config:', selectedNode.data.config);
    console.log('[HanaTablePropertyPanel] Conditions from config:', selectedNode.data.config.conditions);

    setSelectedConnection(selectedNode.data.config.hana_connection_id || "");
    setSelectedTable(selectedNode.data.config.hana_table_name || "");
    setConditions(selectedNode.data.config.conditions || []);
  }, [selectedNode.id]); // Re-sync when node ID changes (different node selected)

  // Fetch HANA connections
  const { data: connections = [], isLoading: connectionsLoading } = useQuery({
    queryKey: ["hana-connections"],
    queryFn: async () => {
      const response = await apiClient.get("/hana-connections");
      return response.data;
    },
  });

  // Fetch tables for selected connection
  const { data: tablesResponse, isLoading: tablesLoading } = useQuery({
    queryKey: ["hana-tables", selectedConnection],
    queryFn: async () => {
      if (!selectedConnection) return { tables: [], message: null };
      const response = await apiClient.get(`/hana-connections/${selectedConnection}/tables`);
      // Handle both array response (old format) and object response (new format)
      if (Array.isArray(response.data)) {
        return { tables: response.data, message: null };
      }
      return response.data;
    },
    enabled: !!selectedConnection,
  });

  const tables = tablesResponse?.tables || [];
  const tablesMessage = tablesResponse?.message;

  // Fetch columns for selected table
  const { data: columns = [], isLoading: columnsLoading } = useQuery({
    queryKey: ["hana-columns", selectedConnection, selectedTable],
    queryFn: async () => {
      if (!selectedConnection || !selectedTable) return [];
      const response = await apiClient.get(
        `/hana-connections/${selectedConnection}/tables/${selectedTable}/columns`
      );
      return response.data;
    },
    enabled: !!selectedConnection && !!selectedTable,
  });

  // Update node configuration when connection changes
  useEffect(() => {
    const nodeConnection = selectedNode.data.config.hana_connection_id || "";
    // Only update if there's an actual change and selectedConnection is not empty
    if (selectedConnection && selectedConnection !== nodeConnection) {
      handleUpdate("hana_connection_id", selectedConnection);
      // Reset table and conditions when connection changes
      setSelectedTable("");
      setConditions([]);
      handleUpdate("hana_table_name", "");
      handleUpdate("conditions", []);
    }
  }, [selectedConnection]);

  // Update node configuration when table changes
  useEffect(() => {
    const nodeTable = selectedNode.data.config.hana_table_name || "";
    // Only update if there's an actual change and selectedTable is not empty
    if (selectedTable && selectedTable !== nodeTable) {
      handleUpdate("hana_table_name", selectedTable);
      // Only reset conditions if this is a real table change, not initialization
      if (nodeTable !== "") {
        setConditions([]);
        handleUpdate("conditions", []);
      }
    }
  }, [selectedTable]);

  // Update node configuration when conditions change
  useEffect(() => {
    const currentConditions = selectedNode.data.config.conditions || [];
    const conditionsChanged = JSON.stringify(conditions) !== JSON.stringify(currentConditions);
    console.log('[HanaTablePropertyPanel] Conditions changed:', conditionsChanged);
    console.log('[HanaTablePropertyPanel] Current conditions:', conditions);
    console.log('[HanaTablePropertyPanel] Node conditions:', currentConditions);

    if (conditionsChanged) {
      console.log('[HanaTablePropertyPanel] Calling handleUpdate with conditions:', conditions);
      handleUpdate("conditions", conditions);
    }
  }, [conditions]);

  const addCondition = () => {
    setConditions([...conditions, { column: "", operator: "=", value: "" }]);
  };

  const removeCondition = (index: number) => {
    setConditions(conditions.filter((_, i) => i !== index));
  };

  const updateCondition = (index: number, field: keyof Condition, value: string) => {
    const updatedConditions = [...conditions];
    updatedConditions[index] = { ...updatedConditions[index], [field]: value };
    setConditions(updatedConditions);
  };

  return (
    <>
      {/* Connection Selection */}
      <div className="space-y-2">
        <Label htmlFor="hana-connection">HANA Connection</Label>
        {connectionsLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading connections...
          </div>
        ) : connections.length === 0 ? (
          <div className="text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-3 rounded">
            No HANA connections found. Please create one in Settings → HANA Connections.
          </div>
        ) : (
          <Select value={selectedConnection} onValueChange={setSelectedConnection}>
            <SelectTrigger id="hana-connection">
              <SelectValue placeholder="Select a connection" />
            </SelectTrigger>
            <SelectContent>
              {connections.map((conn: any) => (
                <SelectItem key={conn.id} value={conn.id}>
                  {conn.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Table Selection */}
      {selectedConnection && (
        <div className="space-y-2">
          <Label htmlFor="hana-table">Table</Label>
          {tablesLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading tables...
            </div>
          ) : tables.length === 0 ? (
            <div className="text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-3 rounded space-y-2">
              <p className="font-medium">No tables found for this connection.</p>
              {tablesMessage && (
                <p className="text-xs opacity-90">{tablesMessage}</p>
              )}
            </div>
          ) : (
            <Select value={selectedTable} onValueChange={setSelectedTable}>
              <SelectTrigger id="hana-table">
                <SelectValue placeholder="Select a table" />
              </SelectTrigger>
              <SelectContent>
                {tables.map((table: any, idx: number) => {
                  const tableName = table.TABLE_NAME || table.table_name || table.name || `table-${idx}`;
                  return (
                    <SelectItem key={`table-${idx}-${tableName}`} value={tableName}>
                      {tableName}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          )}
        </div>
      )}

      {/* Conditions */}
      {selectedTable && columns.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label>Conditions</Label>
            <Button size="sm" variant="outline" onClick={addCondition} className="h-7">
              <Plus className="h-3 w-3 mr-1" />
              Add Condition
            </Button>
          </div>

          {columnsLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading columns...
            </div>
          ) : (
            <>
              {conditions.length === 0 ? (
                <div className="text-sm text-muted-foreground bg-muted p-3 rounded text-center">
                  No conditions. Click "Add Condition" to filter data.
                </div>
              ) : (
                <div className="space-y-3">
                  {conditions.map((condition, index) => (
                    <div key={index} className="bg-muted/50 p-3 rounded-lg space-y-2">
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant="outline" className="text-xs">
                          Condition {index + 1}
                        </Badge>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => removeCondition(index)}
                          className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>

                      {/* Column */}
                      <div className="space-y-1">
                        <Label htmlFor={`condition-column-${index}`} className="text-xs">
                          Column
                        </Label>
                        <Select
                          value={condition.column}
                          onValueChange={(value) => updateCondition(index, "column", value)}
                        >
                          <SelectTrigger id={`condition-column-${index}`} className="h-8 text-xs">
                            <SelectValue placeholder="Select column" />
                          </SelectTrigger>
                          <SelectContent>
                            {columns.map((col: string, colIdx: number) => (
                              <SelectItem key={`col-${index}-${colIdx}-${col}`} value={col}>
                                {col}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Operator */}
                      <div className="space-y-1">
                        <Label htmlFor={`condition-operator-${index}`} className="text-xs">
                          Operator
                        </Label>
                        <Select
                          value={condition.operator}
                          onValueChange={(value) => updateCondition(index, "operator", value)}
                        >
                          <SelectTrigger id={`condition-operator-${index}`} className="h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {OPERATORS.map((op) => (
                              <SelectItem key={op.value} value={op.value}>
                                {op.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Value (only if operator is not IS NULL or IS NOT NULL) */}
                      {condition.operator !== "IS NULL" && condition.operator !== "IS NOT NULL" && (
                        <div className="space-y-1">
                          <Label htmlFor={`condition-value-${index}`} className="text-xs">
                            Value
                          </Label>
                          <input
                            id={`condition-value-${index}`}
                            type="text"
                            value={condition.value}
                            onChange={(e) => updateCondition(index, "value", e.target.value)}
                            placeholder="Enter value"
                            className="flex h-8 w-full rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Enable Snapshots */}
      {selectedTable && (
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-start gap-2">
            <input
              type="checkbox"
              id="enable-snapshots"
              checked={selectedNode.data.config.enable_snapshots || false}
              onChange={(e) => handleUpdate('enable_snapshots', e.target.checked)}
              className="mt-1"
            />
            <div className="flex-1">
              <Label htmlFor="enable-snapshots" className="cursor-pointer">
                Enable Automatic Snapshots
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                Automatically store query results. First run creates baseline, subsequent runs store current data.
                Connect a Compare node to detect changes.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Query Preview */}
      {selectedTable && (
        <div className="space-y-2 pt-2 border-t">
          <Label className="text-xs text-muted-foreground">Query Preview</Label>
          <div className="bg-muted p-3 rounded font-mono text-xs">
            <div>SELECT * FROM {selectedTable}</div>
            {conditions.length > 0 && (
              <div className="mt-1">
                WHERE{" "}
                {conditions.map((cond, idx) => (
                  <span key={idx}>
                    {idx > 0 && " AND "}
                    {cond.column} {cond.operator}
                    {cond.operator !== "IS NULL" && cond.operator !== "IS NOT NULL" && ` '${cond.value}'`}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
