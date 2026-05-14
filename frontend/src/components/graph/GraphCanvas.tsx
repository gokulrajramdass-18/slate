'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Node,
  type Edge,
  type NodeMouseHandler,
  type EdgeMouseHandler,
  type OnNodesChange,
  type OnEdgesChange,
  BackgroundVariant,
  type ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useRouter, useSearchParams } from '@/lib/routing/navigation';
import {
  AlertCircle,
  Network,
  RefreshCw,
  Search,
  X,
  Expand,
  Route,
  ExternalLink,
  Loader2,
  RotateCcw,
} from 'lucide-react';

import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useSourceGraphStore, type LayoutAlgorithm } from '@/lib/stores/source-graph-store';
import { allNodeTypes } from '@/components/graph/SourceNode';
import { relationshipEdgeTypes } from '@/components/graph/RelationshipEdge';
import {
  applyForceLayout,
  applyHierarchicalLayout,
  applyCircularLayoutWithEdges,
} from '@/lib/graph-layouts';
import {
  useGraphSearch,
  useContextMenu,
  useNeighborhoodExpansion,
  usePathFinding,
} from './useGraphInteractions';
import { useGraphExport } from './useGraphExport';

// ============================================================================
// Types
// ============================================================================

/** Props for the GraphCanvas component */
export interface GraphCanvasProps {
  /** Optional notebook ID to scope the graph */
  notebookId?: string;
  /** Whether nodes are draggable (defaults to true when layout is 'manual') */
  draggable?: boolean;
  /** Callback when a source node is selected */
  onSourceSelect?: (sourceId: string) => void;
  /** Callback when a source node is double-clicked */
  onSourceOpen?: (sourceId: string) => void;
  /** Callback when an edge is clicked */
  onEdgeSelect?: (edge: Edge) => void;
  /** Receives export functions once the canvas is ready (must be inside ReactFlowProvider) */
  onExportReady?: (exports: { exportPNG: () => void; exportSVG: () => void; exportJSON: () => void }) => void;
  /** Custom class name for the container */
  className?: string;
}

// ============================================================================
// MiniMap node color by source type
// ============================================================================

const MINIMAP_COLORS: Record<string, string> = {
  file:       '#3b82f6',
  url:        '#10b981',
  text:       '#6b7280',
  youtube:    '#ef4444',
  hana_table: '#8b5cf6',
  api:        '#f59e0b',
};

function getMiniMapNodeColor(node: Node): string {
  const sourceType = (node.data as Record<string, unknown>)?.source_type as string | undefined;
  return MINIMAP_COLORS[sourceType ?? ''] ?? '#64748b';
}

// ============================================================================
// Layout computation
// ============================================================================

function computeLayout(algorithm: LayoutAlgorithm, nodes: Node[], edges: Edge[]): Node[] {
  switch (algorithm) {
    case 'force':
      return applyForceLayout(nodes, edges, {
        strength: 0.4,
        distance: 150,
        charge: -400,
        gravity: 0.08,
      });
    case 'hierarchical':
      return applyHierarchicalLayout(nodes, edges, {
        direction: 'TB',
        nodeSpacing: 120,
        rankSpacing: 180,
      });
    case 'circular':
      return applyCircularLayoutWithEdges(nodes, edges, {
        radius: 600,
        ordering: 'connections',
      });
    case 'manual':
      return nodes;
    default:
      return nodes;
  }
}

// ============================================================================
// Constants
// ============================================================================

const DIM_OPACITY = 0.15;
const PATH_COLOR = '#f43f5e'; // rose-500
const PATH_STROKE_WIDTH = 4;

// ============================================================================
// Loading Skeleton
// ============================================================================

function GraphSkeleton() {
  return (
    <div className="h-full w-full flex items-center justify-center bg-muted/30">
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <Skeleton className="h-16 w-16 rounded-full" />
          <Skeleton className="absolute -top-4 -right-8 h-10 w-10 rounded-full" />
          <Skeleton className="absolute -bottom-4 -left-6 h-12 w-12 rounded-full" />
          <Skeleton className="absolute top-8 right-[-3rem] h-8 w-8 rounded-full" />
        </div>
        <Skeleton className="h-4 w-32 mt-4" />
        <Skeleton className="h-3 w-48" />
      </div>
    </div>
  );
}

// ============================================================================
// Empty State
// ============================================================================

function EmptyState({ notebookId }: { notebookId?: string }) {
  return (
    <div className="h-full w-full flex items-center justify-center bg-muted/20">
      <div className="text-center max-w-sm">
        <div className="p-4 rounded-full bg-muted inline-block mb-4">
          <Network className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold mb-2">No sources to display</h3>
        <p className="text-sm text-muted-foreground">
          {notebookId
            ? 'Add sources to this notebook to see the knowledge graph.'
            : 'Add sources to your notebooks to explore the relationship graph.'}
          {' '}Sources are connected by shared topics, notebooks, and semantic similarity.
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Error State
// ============================================================================

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="h-full w-full flex items-center justify-center p-8">
      <Alert variant="destructive" className="max-w-md">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Failed to load graph</AlertTitle>
        <AlertDescription className="mt-2">
          <p className="mb-3">{message}</p>
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RefreshCw className="h-3 w-3 mr-2" />
              Try again
            </Button>
          )}
        </AlertDescription>
      </Alert>
    </div>
  );
}

// ============================================================================
// Context Menu
// ============================================================================

interface ContextMenuProps {
  x: number;
  y: number;
  nodeId: string;
  onClose: () => void;
  onExpandNeighbors: (nodeId: string) => void;
  onFindPathFrom: (nodeId: string) => void;
  onOpenSource: (nodeId: string) => void;
  isExpanding: boolean;
  pathModeActive: boolean;
}

function NodeContextMenu({
  x,
  y,
  nodeId,
  onClose,
  onExpandNeighbors,
  onFindPathFrom,
  onOpenSource,
  isExpanding,
  pathModeActive,
}: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as HTMLElement)) {
        onClose();
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  const style: React.CSSProperties = {
    position: 'fixed',
    left: x,
    top: y,
    zIndex: 1000,
  };

  const itemClass =
    'flex items-center gap-2.5 w-full px-3 py-2 text-sm text-left rounded-md hover:bg-accent transition-colors disabled:opacity-40 disabled:pointer-events-none';

  return (
    <div
      ref={menuRef}
      style={style}
      className="min-w-[200px] rounded-lg border bg-popover p-1.5 shadow-xl animate-in fade-in-0 zoom-in-95"
    >
      <button
        className={itemClass}
        onClick={() => {
          onExpandNeighbors(nodeId);
          onClose();
        }}
        disabled={isExpanding}
      >
        {isExpanding ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Expand className="h-4 w-4" />
        )}
        <span>Expand Neighbors</span>
      </button>
      <button
        className={itemClass}
        onClick={() => {
          onFindPathFrom(nodeId);
          onClose();
        }}
        disabled={pathModeActive}
      >
        <Route className="h-4 w-4" />
        <span>Find Path From Here</span>
      </button>
      <div className="my-1 h-px bg-border" />
      <button
        className={itemClass}
        onClick={() => {
          onOpenSource(nodeId);
          onClose();
        }}
      >
        <ExternalLink className="h-4 w-4" />
        <span>Open Source Detail</span>
      </button>
    </div>
  );
}

// ============================================================================
// Search Bar (Panel overlay)
// ============================================================================

const SearchBar = React.memo(function SearchBar({
  query,
  matchCount,
  totalNodes,
  isActive,
  onSearch,
  onClear,
}: {
  query: string;
  matchCount: number;
  totalNodes: number;
  isActive: boolean;
  onSearch: (q: string) => void;
  onClear: () => void;
}) {
  return (
    <div className="flex items-center gap-2 bg-popover border rounded-lg shadow-lg px-3 py-1.5 min-w-[260px]">
      <Search className="h-4 w-4 text-muted-foreground shrink-0" />
      <Input
        data-graph-search-input
        value={query}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Search nodes..."
        className="border-0 shadow-none h-7 px-0 focus-visible:ring-0 text-sm"
      />
      {isActive && (
        <>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {matchCount}/{totalNodes}
          </span>
          <button
            onClick={onClear}
            className="p-0.5 rounded hover:bg-muted transition-colors"
          >
            <X className="h-3.5 w-3.5 text-muted-foreground" />
          </button>
        </>
      )}
    </div>
  );
});

// ============================================================================
// Path Info Panel
// ============================================================================

const PathInfoPanel = React.memo(function PathInfoPanel({
  pathState,
  nodes,
  onCancel,
  onReset,
}: {
  pathState: {
    isActive: boolean;
    startNodeId: string | null;
    endNodeId: string | null;
    pathNodeIds: string[];
    hops: number;
    error: string | null;
  };
  nodes: Node[];
  onCancel: () => void;
  onReset: () => void;
}) {
  const getNodeLabel = (id: string | null) => {
    if (!id) return '...';
    const node = nodes.find((n) => n.id === id);
    const data = node?.data as Record<string, unknown> | undefined;
    return (data?.title as string) || (data?.label as string) || id.slice(0, 8);
  };

  return (
    <div className="bg-popover border rounded-lg shadow-lg p-3 min-w-[260px] max-w-[320px]">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Route className="h-4 w-4 text-rose-500" />
          <span className="text-sm font-medium">Path Finding</span>
        </div>
        <button onClick={onCancel} className="p-0.5 rounded hover:bg-muted transition-colors">
          <X className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      </div>

      {!pathState.startNodeId && (
        <p className="text-xs text-muted-foreground">
          Click the <strong>start</strong> node.
        </p>
      )}

      {pathState.startNodeId && !pathState.endNodeId && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5">
            <Badge variant="outline" className="text-[10px] px-1.5 bg-rose-50 dark:bg-rose-950 border-rose-300 dark:border-rose-800">
              Start
            </Badge>
            <span className="text-xs truncate">{getNodeLabel(pathState.startNodeId)}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Now click the <strong>destination</strong> node.
          </p>
        </div>
      )}

      {pathState.startNodeId && pathState.endNodeId && (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <Badge variant="outline" className="text-[10px] px-1.5 bg-rose-50 dark:bg-rose-950 border-rose-300 dark:border-rose-800">
              Start
            </Badge>
            <span className="text-xs truncate">{getNodeLabel(pathState.startNodeId)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant="outline" className="text-[10px] px-1.5 bg-rose-50 dark:bg-rose-950 border-rose-300 dark:border-rose-800">
              End
            </Badge>
            <span className="text-xs truncate">{getNodeLabel(pathState.endNodeId)}</span>
          </div>

          {pathState.error ? (
            <p className="text-xs text-destructive">{pathState.error}</p>
          ) : (
            <div className="flex items-center gap-3 pt-1 border-t text-xs text-muted-foreground">
              <span><strong>{pathState.hops}</strong> hop{pathState.hops !== 1 ? 's' : ''}</span>
              <span><strong>{pathState.pathNodeIds.length}</strong> node{pathState.pathNodeIds.length !== 1 ? 's' : ''}</span>
            </div>
          )}

          <button
            onClick={onReset}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors pt-1"
          >
            <RotateCcw className="h-3 w-3" />
            Find another path
          </button>
        </div>
      )}
    </div>
  );
});

// ============================================================================
// Focus handler (centers on node from URL param ?focus=<id>)
// ============================================================================

function useFocusNode(reactFlowInstance: ReactFlowInstance | null) {
  const searchParams = useSearchParams();
  const focusId = searchParams.get('focus');
  const hasFocused = useRef(false);

  const nodes = useSourceGraphStore((s) => s.nodes);

  useEffect(() => {
    if (!focusId || !reactFlowInstance || hasFocused.current) return;

    const targetNode = nodes.find((n) => n.id === focusId);
    if (!targetNode) return;

    reactFlowInstance.setCenter(
      targetNode.position.x + 75,
      targetNode.position.y + 30,
      { zoom: 1.5, duration: 600 }
    );

    useSourceGraphStore.getState().selectNode(focusId);
    hasFocused.current = true;
  }, [focusId, reactFlowInstance, nodes]);
}

// ============================================================================
// Inner canvas (must be inside ReactFlowProvider)
// ============================================================================

function GraphCanvasInner({
  notebookId,
  draggable,
  onSourceSelect,
  onSourceOpen,
  onEdgeSelect,
  onExportReady,
}: Omit<GraphCanvasProps, 'className'>) {
  const router = useRouter();
  const { fitView } = useReactFlow();
  const reactFlowInstance = useRef<ReactFlowInstance | null>(null);

  // Responsive: track viewport width for conditional rendering
  const [isSmallScreen, setIsSmallScreen] = useState(false);
  useEffect(() => {
    const mql = window.matchMedia('(max-width: 768px)');
    setIsSmallScreen(mql.matches);
    const handler = (e: MediaQueryListEvent) => setIsSmallScreen(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  // Store state
  const storeNodes = useSourceGraphStore((s) => s.nodes);
  const storeEdges = useSourceGraphStore((s) => s.edges);
  const isLoading = useSourceGraphStore((s) => s.isLoading);
  const error = useSourceGraphStore((s) => s.error);
  const selectedNodeId = useSourceGraphStore((s) => s.selectedNodeId);
  const currentLayout = useSourceGraphStore((s) => s.currentLayout);
  const selectNode = useSourceGraphStore((s) => s.selectNode);
  const hoverNode = useSourceGraphStore((s) => s.hoverNode);
  const loadGraph = useSourceGraphStore((s) => s.loadGraph);
  const setStoreNodes = useSourceGraphStore((s) => s.setNodes);

  // React Flow local state
  const [nodes, setNodes, onNodesChangeBase] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChangeBase] = useEdgesState<Edge>([]);

  // Track layout changes
  const prevLayoutRef = useRef<LayoutAlgorithm>(currentLayout);
  const hasInitialLayout = useRef(false);
  const prevNodeCountRef = useRef(0);

  // Focus on node from URL ?focus=<id>
  useFocusNode(reactFlowInstance.current);

  // --- Advanced interactions ---
  const { search, updateSearch, clearSearch } = useGraphSearch(nodes);
  const { contextMenu, showContextMenu, hideContextMenu } = useContextMenu();
  const { expandState, expandNeighbors } = useNeighborhoodExpansion();
  const { pathState, startPathFinding, selectPathNode, cancelPathFinding, resetPath } =
    usePathFinding(nodes, edges);

  // --- Export ---
  const { exportPNG, exportSVG, exportJSON } = useGraphExport();

  // Expose export functions to parent
  useEffect(() => {
    onExportReady?.({ exportPNG, exportSVG, exportJSON });
  }, [onExportReady, exportPNG, exportSVG, exportJSON]);

  // Fetch graph data on mount / scope change
  useEffect(() => {
    const scope = notebookId ? 'notebook' : 'global';
    loadGraph(scope, notebookId);
    // Reset layout flag when loading new data
    hasInitialLayout.current = false;
  }, [loadGraph, notebookId]);

  // Apply layout when store data or layout algorithm changes
  useEffect(() => {
    if (storeNodes.length === 0) {
      setNodes([]);
      setEdges([]);
      prevNodeCountRef.current = 0;
      return;
    }

    // Reset layout flag if node count changed (new data loaded)
    if (storeNodes.length !== prevNodeCountRef.current) {
      hasInitialLayout.current = false;
      prevNodeCountRef.current = storeNodes.length;
    }

    const layoutChanged = prevLayoutRef.current !== currentLayout;
    const needsLayout = !hasInitialLayout.current || layoutChanged;
    prevLayoutRef.current = currentLayout;

    let positionedNodes: Node[];

    // Check if nodes have valid positions (not null and not all at origin)
    const hasPositions = storeNodes.every(n =>
      n.position &&
      typeof n.position.x === 'number' &&
      typeof n.position.y === 'number'
    );

    // Also check if all nodes are at (0,0) which indicates no layout has been applied
    const allAtOrigin = hasPositions && storeNodes.every(n =>
      n.position.x === 0 && n.position.y === 0
    );

    if ((needsLayout || !hasPositions || allAtOrigin) && currentLayout !== 'manual') {
      positionedNodes = computeLayout(currentLayout, storeNodes, storeEdges);
      hasInitialLayout.current = true;
      // Don't call setStoreNodes here - it causes infinite loop
      // The positioned nodes will be set to local state only
    } else {
      positionedNodes = storeNodes;
    }

    setNodes(positionedNodes);
    setEdges(storeEdges);

    requestAnimationFrame(() => {
      fitView({ padding: 0.15, duration: 300, maxZoom: 1.5 });
    });
  }, [storeNodes, storeEdges, currentLayout, setNodes, setEdges, fitView]);

  // -----------------------------------------------------------------------
  // Combined visual highlighting: selection + search + path
  // -----------------------------------------------------------------------

  const highlightedEdges = useMemo(() => {
    const pathEdgeSet = new Set(pathState.pathEdgeIds);
    const hasSearch = search.isActive;
    const hasPath = pathState.pathNodeIds.length > 0;
    const hasSelection = !!selectedNodeId && !hasSearch && !hasPath;

    return edges.map((edge) => {
      // Path highlighting takes top priority
      if (pathEdgeSet.has(edge.id)) {
        return {
          ...edge,
          style: {
            ...edge.style,
            strokeWidth: PATH_STROKE_WIDTH,
            stroke: PATH_COLOR,
            opacity: 1,
            transition: 'all 0.3s ease',
          },
          animated: true,
          zIndex: 10,
        };
      }

      // Search: dim edges not connecting two matched nodes
      if (hasSearch) {
        const bothMatch =
          search.matchedNodeIds.has(edge.source) &&
          search.matchedNodeIds.has(edge.target);
        return {
          ...edge,
          style: {
            ...edge.style,
            opacity: bothMatch ? 1 : DIM_OPACITY,
            transition: 'opacity 0.3s ease',
          },
          animated: bothMatch ? (edge.animated ?? false) : false,
        };
      }

      // Path mode active but no result yet -- dim everything
      if (hasPath) {
        return {
          ...edge,
          style: {
            ...edge.style,
            opacity: DIM_OPACITY,
            transition: 'opacity 0.3s ease',
          },
          animated: false,
        };
      }

      // Selection: dim non-connected edges
      if (hasSelection) {
        const isConnected =
          edge.source === selectedNodeId || edge.target === selectedNodeId;
        return {
          ...edge,
          style: {
            ...edge.style,
            opacity: isConnected ? 1 : 0.2,
            transition: 'opacity 200ms ease',
          },
          animated: isConnected ? true : (edge.animated ?? false),
        };
      }

      return edge;
    });
  }, [edges, selectedNodeId, search, pathState]);

  const highlightedNodes = useMemo(() => {
    const pathNodeSet = new Set(pathState.pathNodeIds);
    const hasSearch = search.isActive;
    const hasPath = pathState.pathNodeIds.length > 0;
    const hasSelection = !!selectedNodeId && !hasSearch && !hasPath;

    if (!hasSearch && !hasPath && !hasSelection) return nodes;

    // For selection mode: build connected-node set
    let connectedIds: Set<string> | null = null;
    if (hasSelection) {
      connectedIds = new Set<string>([selectedNodeId!]);
      for (const edge of edges) {
        if (edge.source === selectedNodeId) connectedIds.add(edge.target);
        if (edge.target === selectedNodeId) connectedIds.add(edge.source);
      }
    }

    return nodes.map((node) => {
      let dimmed = false;

      if (hasSearch && !search.matchedNodeIds.has(node.id)) {
        dimmed = true;
      }
      if (hasPath && !pathNodeSet.has(node.id)) {
        dimmed = true;
      }
      if (hasSelection && connectedIds && !connectedIds.has(node.id)) {
        dimmed = true;
      }

      if (!dimmed) return node;

      return {
        ...node,
        style: {
          ...node.style,
          opacity: hasSelection ? 0.25 : DIM_OPACITY,
          transition: 'opacity 0.3s ease',
        },
      };
    });
  }, [nodes, edges, selectedNodeId, search, pathState]);

  // Draggable: allow drag in manual mode or when explicitly enabled
  const isDraggable = draggable ?? (currentLayout === 'manual');

  // Sync manual drag positions back to store
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      onNodesChangeBase(changes);

      const hasDragEnd = changes.some(
        (c) => c.type === 'position' && c.dragging === false && c.position
      );
      if (hasDragEnd) {
        requestAnimationFrame(() => {
          setNodes((currentNodes) => {
            setStoreNodes(currentNodes);
            return currentNodes;
          });
        });
      }
    },
    [onNodesChangeBase, setNodes, setStoreNodes]
  );

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      onEdgesChangeBase(changes);
    },
    [onEdgesChangeBase]
  );

  // --- Event handlers ---

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      // Path finding mode intercepts clicks
      if (pathState.isActive) {
        selectPathNode(node.id);
        return;
      }
      selectNode(node.id);
      onSourceSelect?.(node.id);
    },
    [selectNode, onSourceSelect, pathState.isActive, selectPathNode]
  );

  const onNodeDoubleClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      if (onSourceOpen) {
        onSourceOpen(node.id);
      } else {
        router.push(`/sources/${node.id}`);
      }
    },
    [onSourceOpen, router]
  );

  const onNodeContextMenu: NodeMouseHandler = useCallback(
    (event, node) => {
      showContextMenu(event as unknown as React.MouseEvent, node.id);
    },
    [showContextMenu]
  );

  const onEdgeClick: EdgeMouseHandler = useCallback(
    (_event, edge) => {
      onEdgeSelect?.(edge);
    },
    [onEdgeSelect]
  );

  const onNodeMouseEnter: NodeMouseHandler = useCallback(
    (_event, node) => {
      hoverNode(node.id);
    },
    [hoverNode]
  );

  const onNodeMouseLeave: NodeMouseHandler = useCallback(
    () => {
      hoverNode(null);
    },
    [hoverNode]
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
    hideContextMenu();
  }, [selectNode, hideContextMenu]);

  const onInit = useCallback((instance: ReactFlowInstance) => {
    reactFlowInstance.current = instance;
  }, []);

  // Context menu action handlers
  const handleExpandNeighbors = useCallback(
    (nodeId: string) => {
      expandNeighbors(nodeId);
    },
    [expandNeighbors]
  );

  const handleFindPathFrom = useCallback(
    (nodeId: string) => {
      startPathFinding();
      selectPathNode(nodeId);
    },
    [startPathFinding, selectPathNode]
  );

  const handleOpenSource = useCallback(
    (nodeId: string) => {
      if (onSourceOpen) {
        onSourceOpen(nodeId);
      } else {
        router.push(`/sources/${nodeId}`);
      }
    },
    [onSourceOpen, router]
  );

  // Node and edge type registrations
  const nodeTypes = useMemo(() => allNodeTypes as any, []);
  const edgeTypes = useMemo(() => relationshipEdgeTypes, []);

  // Keyboard shortcuts: Escape cancels path/search, Cmd+F focuses search
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        if (pathState.isActive) {
          cancelPathFinding();
        } else if (search.isActive) {
          clearSearch();
        }
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
        e.preventDefault();
        const input = document.querySelector<HTMLInputElement>(
          '[data-graph-search-input]'
        );
        input?.focus();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [pathState.isActive, search.isActive, cancelPathFinding, clearSearch]);

  // Loading state
  if (isLoading && nodes.length === 0) {
    return <GraphSkeleton />;
  }

  // Error state
  if (error && nodes.length === 0) {
    return (
      <ErrorState
        message={error}
        onRetry={() => loadGraph(notebookId ? 'notebook' : 'global', notebookId)}
      />
    );
  }

  // Empty state
  if (!isLoading && nodes.length === 0) {
    return <EmptyState notebookId={notebookId} />;
  }

  const canvasClassName = [
    'bg-muted/30',
    pathState.isActive ? 'cursor-crosshair' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <>
      <ReactFlow
        nodes={highlightedNodes}
        edges={highlightedEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        onNodeContextMenu={onNodeContextMenu}
        onEdgeClick={onEdgeClick}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        onPaneClick={onPaneClick}
        onInit={onInit}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={isDraggable}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.5 }}
        minZoom={0.1}
        maxZoom={4}
        zoomOnScroll
        panOnScroll={false}
        panOnDrag
        selectNodesOnDrag={false}
        className={canvasClassName}
        defaultEdgeOptions={{
          type: 'relationship',
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1.5}
          color="hsl(var(--muted-foreground) / 0.12)"
          className="bg-slate-50 dark:bg-slate-950"
        />
        <Controls
          showInteractive={false}
          className="!bg-background !border !shadow-sm"
        />
        {!isSmallScreen && (
          <MiniMap
            nodeColor={getMiniMapNodeColor}
            maskColor="hsl(var(--background) / 0.7)"
            className="!bg-background !border !shadow-sm"
            pannable
            zoomable
          />
        )}

        {/* Search bar */}
        <Panel position="top-left">
          <SearchBar
            query={search.query}
            matchCount={search.matchedNodeIds.size}
            totalNodes={nodes.length}
            isActive={search.isActive}
            onSearch={updateSearch}
            onClear={clearSearch}
          />
        </Panel>

        {/* Path info panel */}
        {pathState.isActive && (
          <Panel position="top-right">
            <PathInfoPanel
              pathState={pathState}
              nodes={nodes}
              onCancel={cancelPathFinding}
              onReset={resetPath}
            />
          </Panel>
        )}

        {/* Error overlay (non-blocking) */}
        {error && (
          <Panel position="bottom-center">
            <Alert variant="destructive" className="max-w-xs shadow-lg">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="text-xs">{error}</AlertDescription>
            </Alert>
          </Panel>
        )}

        {/* Expansion loading indicator */}
        {expandState.isExpanding && (
          <Panel position="bottom-left">
            <div className="flex items-center gap-2 bg-popover border rounded-lg shadow-lg px-3 py-2 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Expanding neighbors...</span>
            </div>
          </Panel>
        )}
      </ReactFlow>

      {/* Context menu (rendered outside ReactFlow to avoid clipping) */}
      {contextMenu.visible && contextMenu.nodeId && (
        <NodeContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          nodeId={contextMenu.nodeId}
          onClose={hideContextMenu}
          onExpandNeighbors={handleExpandNeighbors}
          onFindPathFrom={handleFindPathFrom}
          onOpenSource={handleOpenSource}
          isExpanding={expandState.isExpanding}
          pathModeActive={pathState.isActive}
        />
      )}
    </>
  );
}

// ============================================================================
// Main export (wraps in ReactFlowProvider)
// ============================================================================

export function GraphCanvas({
  className,
  ...props
}: GraphCanvasProps) {
  return (
    <div className={`h-full w-full ${className || ''}`}>
      <ReactFlowProvider>
        <GraphCanvasInner {...props} />
      </ReactFlowProvider>
    </div>
  );
}

export default GraphCanvas;
