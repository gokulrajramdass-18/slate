'use client';

/**
 * NodeDetailsPanel
 *
 * Slide-out panel showing full source metadata, connected nodes, and quick actions
 * when a node is selected in the source graph.
 */

import React, { useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileText,
  Globe,
  Video,
  Database,
  Plug,
  ExternalLink,
  Plus,
  Trash2,
  Calendar,
  Tag,
  Link2,
  BookOpen,
  X,
} from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { formatDate, formatRelativeTime } from '@/lib/utils';
import { useSourceGraphStore, useSelectedGraphNode } from '@/lib/stores/source-graph-store';
import type { SourceType } from '@/lib/types';
import type { EdgeType } from '@/lib/api/graph';

// ============================================================================
// Types
// ============================================================================

interface NodeDetailsPanelProps {
  onOpenSource?: (sourceId: string) => void;
  onAddToNotebook?: (sourceId: string) => void;
  onDelete?: (sourceId: string) => void;
}

// ============================================================================
// Source type configuration
// ============================================================================

const SOURCE_TYPE_CONFIG: Record<string, {
  icon: React.ElementType;
  color: string;
  label: string;
}> = {
  file:       { icon: FileText, color: '#3B82F6', label: 'File' },
  url:        { icon: Globe,    color: '#10B981', label: 'URL' },
  text:       { icon: FileText, color: '#6B7280', label: 'Text' },
  youtube:    { icon: Video,    color: '#EF4444', label: 'YouTube' },
  hana_table: { icon: Database, color: '#8B5CF6', label: 'HANA Table' },
  api:        { icon: Plug,     color: '#F59E0B', label: 'API' },
};

const EDGE_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  semantic:     { label: 'Semantic Similarity', color: '#8b5cf6' },
  notebook:     { label: 'Shared Notebook',     color: '#3b82f6' },
  topic:        { label: 'Common Topic',        color: '#f59e0b' },
  note_link:    { label: 'Note Link',           color: '#10b981' },
  hana_schema:  { label: 'HANA Schema',         color: '#06b6d4' },
  api_relation: { label: 'API Relation',        color: '#f97316' },
};

// ============================================================================
// Connected node grouping
// ============================================================================

interface ConnectedNode {
  id: string;
  label: string;
  sourceType: string;
}

interface ConnectedGroup {
  edgeType: string;
  label: string;
  color: string;
  nodes: ConnectedNode[];
}

// ============================================================================
// Component
// ============================================================================

export const NodeDetailsPanel = React.memo(function NodeDetailsPanel({
  onOpenSource,
  onAddToNotebook,
  onDelete,
}: NodeDetailsPanelProps) {
  const router = useRouter();
  const selectedNodeId = useSourceGraphStore((s) => s.selectedNodeId);
  const selectNode = useSourceGraphStore((s) => s.selectNode);
  const nodes = useSourceGraphStore((s) => s.nodes);
  const edges = useSourceGraphStore((s) => s.edges);
  const selectedNode = useSelectedGraphNode();

  const isOpen = selectedNodeId !== null && selectedNode !== undefined;

  // Close on Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && isOpen) {
        selectNode(null);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectNode]);

  // Compute connected nodes grouped by edge type
  const connectedGroups = useMemo<ConnectedGroup[]>(() => {
    if (!selectedNodeId) return [];

    const groups = new Map<string, ConnectedNode[]>();

    for (const edge of edges) {
      const sourceId = typeof edge.source === 'string' ? edge.source : (edge.source as any)?.id;
      const targetId = typeof edge.target === 'string' ? edge.target : (edge.target as any)?.id;

      let neighborId: string | null = null;
      if (sourceId === selectedNodeId) neighborId = targetId;
      else if (targetId === selectedNodeId) neighborId = sourceId;
      if (!neighborId) continue;

      const edgeType = (edge.data as any)?.edgeType || (edge.data as any)?.relation_type || 'unknown';
      const neighborNode = nodes.find((n) => n.id === neighborId);
      if (!neighborNode) continue;

      const nodeData = neighborNode.data as any;

      if (!groups.has(edgeType)) {
        groups.set(edgeType, []);
      }
      groups.get(edgeType)!.push({
        id: neighborId,
        label: nodeData?.title || nodeData?.label || neighborId,
        sourceType: nodeData?.source_type || neighborNode.type || 'text',
      });
    }

    return Array.from(groups.entries()).map(([edgeType, groupNodes]) => {
      const config = EDGE_TYPE_CONFIG[edgeType] || { label: edgeType, color: '#94a3b8' };
      return {
        edgeType,
        label: config.label,
        color: config.color,
        nodes: groupNodes,
      };
    });
  }, [selectedNodeId, edges, nodes]);

  // Extract node data
  const nodeData = selectedNode?.data as any;
  const sourceType: string = nodeData?.source_type || selectedNode?.type || 'text';
  const typeConfig = SOURCE_TYPE_CONFIG[sourceType] || SOURCE_TYPE_CONFIG.text;
  const Icon = typeConfig.icon;

  const title = nodeData?.title || nodeData?.label || 'Untitled';
  const description = nodeData?.description || '';
  const topics: string[] = nodeData?.topics || [];
  const notebooks: Array<{ id: string; name: string }> = nodeData?.notebooks || [];
  const created = nodeData?.created;
  const updated = nodeData?.updated;
  const chunkCount = nodeData?.chunk_count;
  const connectionCount = nodeData?.connection_count || 0;

  function handleOpenSource() {
    if (!selectedNodeId) return;
    if (onOpenSource) {
      onOpenSource(selectedNodeId);
    } else {
      router.push(`/sources/${selectedNodeId}`);
    }
  }

  function handleAddToNotebook() {
    if (!selectedNodeId) return;
    onAddToNotebook?.(selectedNodeId);
  }

  function handleDelete() {
    if (!selectedNodeId) return;
    onDelete?.(selectedNodeId);
  }

  function handleClose() {
    selectNode(null);
  }

  function handleNavigateToNode(nodeId: string) {
    selectNode(nodeId);
  }

  return (
    <Sheet open={isOpen} onOpenChange={(open) => { if (!open) handleClose(); }}>
      <SheetContent side="right" className="w-[400px] sm:max-w-[400px] p-0 flex flex-col">
        {/* Header */}
        <div className="p-6 pb-4">
          <SheetHeader>
            <div className="flex items-start gap-3">
              <div
                className="p-2 rounded-lg text-white shadow-sm shrink-0"
                style={{ backgroundColor: typeConfig.color }}
              >
                <Icon className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <SheetTitle className="text-base truncate pr-6">{title}</SheetTitle>
                <div className="mt-1 flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className="text-xs"
                    style={{ borderColor: typeConfig.color, color: typeConfig.color }}
                  >
                    {typeConfig.label}
                  </Badge>
                  {connectionCount > 0 && (
                    <span className="text-xs text-muted-foreground">
                      {connectionCount} connection{connectionCount !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </SheetHeader>
        </div>

        <Separator />

        {/* Scrollable content */}
        <ScrollArea className="flex-1">
          <div className="p-6 space-y-6">
            {/* Description */}
            {description && (
              <div>
                <h4 className="text-sm font-medium mb-1.5">Description</h4>
                <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
              </div>
            )}

            {/* Metadata */}
            <div>
              <h4 className="text-sm font-medium mb-2">Details</h4>
              <div className="space-y-2">
                {created && (
                  <div className="flex items-center gap-2 text-sm">
                    <Calendar className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">Created</span>
                    <span className="ml-auto" title={formatDate(created)}>
                      {formatRelativeTime(created)}
                    </span>
                  </div>
                )}
                {updated && (
                  <div className="flex items-center gap-2 text-sm">
                    <Calendar className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">Updated</span>
                    <span className="ml-auto" title={formatDate(updated)}>
                      {formatRelativeTime(updated)}
                    </span>
                  </div>
                )}
                {chunkCount !== undefined && chunkCount !== null && (
                  <div className="flex items-center gap-2 text-sm">
                    <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">Chunks</span>
                    <span className="ml-auto">{chunkCount}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Source-type specific metadata */}
            {sourceType === 'hana_table' && nodeData?.hana_metadata && (
              <div>
                <h4 className="text-sm font-medium mb-2">HANA Table</h4>
                <div className="space-y-1.5 text-sm">
                  {nodeData.hana_metadata.schema_name && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Schema</span>
                      <span className="font-mono text-xs">{nodeData.hana_metadata.schema_name}</span>
                    </div>
                  )}
                  {nodeData.hana_metadata.table_name && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Table</span>
                      <span className="font-mono text-xs">{nodeData.hana_metadata.table_name}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {sourceType === 'api' && nodeData?.api_metadata && (
              <div>
                <h4 className="text-sm font-medium mb-2">API Endpoint</h4>
                <div className="space-y-1.5 text-sm">
                  {nodeData.api_metadata.endpoint && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Endpoint</span>
                      <span className="font-mono text-xs truncate ml-4">
                        {nodeData.api_metadata.endpoint}
                      </span>
                    </div>
                  )}
                  {nodeData.api_metadata.method && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Method</span>
                      <Badge variant="outline" className="text-xs font-mono">
                        {nodeData.api_metadata.method}
                      </Badge>
                    </div>
                  )}
                </div>
              </div>
            )}

            {sourceType === 'youtube' && nodeData?.youtube_metadata && (
              <div>
                <h4 className="text-sm font-medium mb-2">YouTube</h4>
                <div className="space-y-1.5 text-sm">
                  {nodeData.youtube_metadata.channel_name && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Channel</span>
                      <span>{nodeData.youtube_metadata.channel_name}</span>
                    </div>
                  )}
                  {nodeData.youtube_metadata.duration_seconds && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Duration</span>
                      <span>
                        {Math.floor(nodeData.youtube_metadata.duration_seconds / 60)}m{' '}
                        {nodeData.youtube_metadata.duration_seconds % 60}s
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Topics */}
            {topics.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                  <Tag className="h-3.5 w-3.5" />
                  Topics
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {topics.map((topic) => (
                    <Badge key={topic} variant="secondary" className="text-xs">
                      {topic}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Notebooks */}
            {notebooks.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                  <BookOpen className="h-3.5 w-3.5" />
                  Notebooks
                </h4>
                <div className="space-y-1.5">
                  {notebooks.map((nb) => (
                    <button
                      key={nb.id}
                      onClick={() => router.push(`/workspaces/${nb.id}`)}
                      className="flex items-center gap-2 w-full text-left text-sm hover:bg-muted/50 rounded-md px-2 py-1.5 transition-colors"
                    >
                      <BookOpen className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      <span className="truncate">{nb.name}</span>
                      <ExternalLink className="h-3 w-3 text-muted-foreground shrink-0 ml-auto" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Connected Nodes */}
            {connectedGroups.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                  <Link2 className="h-3.5 w-3.5" />
                  Connected Sources
                </h4>
                <div className="space-y-3">
                  {connectedGroups.map((group) => (
                    <div key={group.edgeType}>
                      <div className="flex items-center gap-2 mb-1.5">
                        <div
                          className="w-3 h-0.5 rounded"
                          style={{ backgroundColor: group.color }}
                        />
                        <span className="text-xs font-medium text-muted-foreground">
                          {group.label} ({group.nodes.length})
                        </span>
                      </div>
                      <div className="space-y-0.5 pl-5">
                        {group.nodes.slice(0, 10).map((node) => {
                          const nConfig = SOURCE_TYPE_CONFIG[node.sourceType] || SOURCE_TYPE_CONFIG.text;
                          const NIcon = nConfig.icon;
                          return (
                            <button
                              key={node.id}
                              onClick={() => handleNavigateToNode(node.id)}
                              className="flex items-center gap-2 w-full text-left text-sm hover:bg-muted/50 rounded-md px-2 py-1 transition-colors"
                            >
                              <NIcon
                                className="h-3 w-3 shrink-0"
                                style={{ color: nConfig.color }}
                              />
                              <span className="truncate">{node.label}</span>
                            </button>
                          );
                        })}
                        {group.nodes.length > 10 && (
                          <span className="text-xs text-muted-foreground pl-2">
                            +{group.nodes.length - 10} more
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <Separator />

        {/* Quick Actions */}
        <div className="p-4 flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            onClick={handleOpenSource}
          >
            <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
            Open Source
          </Button>
          {onAddToNotebook && (
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              onClick={handleAddToNotebook}
            >
              <Plus className="h-3.5 w-3.5 mr-1.5" />
              Add to Notebook
            </Button>
          )}
          {onDelete && (
            <Button
              variant="outline"
              size="sm"
              className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
              onClick={handleDelete}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
});
