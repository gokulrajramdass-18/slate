/**
 * Compare Node Watch Columns Component
 *
 * Auto-populates table columns from connected HANA node
 * and allows selecting columns to watch for changes.
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { getCurrentGraphState } from './GraphEditor';

interface CompareNodeWatchColumnsProps {
  selectedNode: any;
  handleUpdate: (field: string, value: any) => void;
}

export function CompareNodeWatchColumns({ selectedNode, handleUpdate }: CompareNodeWatchColumnsProps) {
  const [sourceHanaNode, setSourceHanaNode] = useState<any>(null);
  const [watchColumns, setWatchColumns] = useState<Array<{ column: string; watch_value: string }>>(
    selectedNode.data.config.watch_columns || []
  );

  // Detect connected HANA node
  useEffect(() => {
    const detectSourceNode = () => {
      const { nodes, edges } = getCurrentGraphState();

      // Find edge pointing to this compare node
      const incomingEdge = edges.find((e: any) => e.target === selectedNode.id);
      if (!incomingEdge) {
        console.log('[CompareNodeWatchColumns] No incoming edge found');
        setSourceHanaNode(null);
        return;
      }

      // Find source node
      const sourceNode = nodes.find((n: any) => n.id === incomingEdge.source);
      if (!sourceNode) {
        console.log('[CompareNodeWatchColumns] Source node not found');
        setSourceHanaNode(null);
        return;
      }

      // Check if source has snapshots enabled (any node type)
      if ((sourceNode.data.config as any)?.enable_snapshots) {
        console.log('[CompareNodeWatchColumns] Found source with snapshots:', sourceNode.id, sourceNode.data.type);
        setSourceHanaNode(sourceNode);
      } else {
        console.log('[CompareNodeWatchColumns] Source does not have snapshots enabled:', sourceNode.data.type);
        setSourceHanaNode(null);
      }
    };

    detectSourceNode();
  }, [selectedNode.id]);

  // Fetch table columns from source node
  const { data: columns, isLoading, error } = useQuery({
    queryKey: ['source-node-columns', sourceHanaNode?.id, sourceHanaNode?.data.type, sourceHanaNode?.data.config.hana_connection_id, sourceHanaNode?.data.config.hana_table_name],
    queryFn: async () => {
      // For HANA nodes, fetch columns from connection
      if (sourceHanaNode.data.type === 'hana_table') {
        const connectionId = sourceHanaNode.data.config.hana_connection_id;
        const tableName = sourceHanaNode.data.config.hana_table_name;

        if (!connectionId || !tableName) {
          throw new Error('Connection ID or table name not configured');
        }

        // Parse schema and table
        const parts = tableName.split('.');
        const schema = parts.length > 1 ? parts[0] : undefined;
        const table = parts.length > 1 ? parts[1] : parts[0];

        const { data } = await apiClient.get(
          `/hana-connections/${connectionId}/tables/${table}/columns`,
          { params: schema ? { schema } : {} }
        );

        return data as string[];
      } else if (sourceHanaNode.data.type === 'api') {
        // For API nodes, return empty array (columns will be detected at runtime)
        // User can manually add columns
        return [] as string[];
      }

      return [] as string[];
    },
    enabled: !!sourceHanaNode && (
      (sourceHanaNode.data.type === 'hana_table' && !!sourceHanaNode.data.config.hana_connection_id && !!sourceHanaNode.data.config.hana_table_name) ||
      (sourceHanaNode.data.type === 'api')
    ),
  });

  // Update parent when watchColumns changes
  useEffect(() => {
    handleUpdate('watch_columns', watchColumns);
  }, [watchColumns]);

  const handleToggleColumn = (columnName: string) => {
    setWatchColumns((prev) => {
      const exists = prev.find((wc) => wc.column === columnName);
      if (exists) {
        // Remove column
        return prev.filter((wc) => wc.column !== columnName);
      } else {
        // Add column with empty watch_value
        return [...prev, { column: columnName, watch_value: '' }];
      }
    });
  };

  const handleUpdateWatchValue = (columnName: string, value: string) => {
    setWatchColumns((prev) =>
      prev.map((wc) =>
        wc.column === columnName ? { ...wc, watch_value: value } : wc
      )
    );
  };

  const isColumnWatched = (columnName: string) => {
    return watchColumns.some((wc) => wc.column === columnName);
  };

  const getWatchValue = (columnName: string) => {
    return watchColumns.find((wc) => wc.column === columnName)?.watch_value || '';
  };

  if (!sourceHanaNode) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Watch Columns</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-2 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <p>
              Connect this node to a HANA Table or API node with "Enable Snapshots" checked
              to configure which columns to watch for changes.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Watch Columns</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <p>Loading columns from HANA table...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Watch Columns</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <p>Failed to load columns: {(error as Error).message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!columns || columns.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Watch Columns</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-2 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            {sourceHanaNode.data.type === 'api' ? (
              <p>
                For API nodes, columns are detected at runtime. You can manually add watch columns after the first execution.
              </p>
            ) : (
              <p>No columns found in the selected table.</p>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm">Watch Columns</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Select columns to monitor for changes. Leave value empty to watch any change,
              or specify a value to watch for specific changes.
            </p>
          </div>
          <Badge variant="outline" className="text-xs">
            {watchColumns.length} watching
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-xs bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 p-2 rounded">
          <strong>Source:</strong> {sourceHanaNode.data.label || sourceHanaNode.id}
          <br />
          {sourceHanaNode.data.type === 'hana_table' && (
            <>
              <strong>Table:</strong> {sourceHanaNode.data.config.hana_table_name}
            </>
          )}
          {sourceHanaNode.data.type === 'api' && (
            <>
              <strong>Endpoint:</strong> {sourceHanaNode.data.config.api_endpoint}
            </>
          )}
        </div>

        <div className="space-y-2 max-h-96 overflow-y-auto">
          {columns.map((columnName) => {
            const isWatched = isColumnWatched(columnName);
            const watchValue = getWatchValue(columnName);

            return (
              <div
                key={columnName}
                className="flex items-start gap-2 p-2 rounded border hover:bg-muted/50 transition-colors"
              >
                <Checkbox
                  id={`watch-${columnName}`}
                  checked={isWatched}
                  onCheckedChange={() => handleToggleColumn(columnName)}
                  className="mt-1"
                />
                <div className="flex-1 space-y-1.5">
                  <Label
                    htmlFor={`watch-${columnName}`}
                    className="text-sm font-mono cursor-pointer flex items-center gap-2"
                  >
                    {isWatched ? (
                      <Eye className="h-3 w-3 text-green-500" />
                    ) : (
                      <EyeOff className="h-3 w-3 text-muted-foreground" />
                    )}
                    {columnName}
                  </Label>
                  {isWatched && (
                    <Input
                      placeholder="Watch for specific value (optional)"
                      value={watchValue}
                      onChange={(e) => handleUpdateWatchValue(columnName, e.target.value)}
                      className="text-xs h-7"
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {watchColumns.length > 0 && (
          <div className="pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWatchColumns([])}
              className="w-full text-xs"
            >
              Clear All
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
