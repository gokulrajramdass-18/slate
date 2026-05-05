"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { GraphControls, type LayoutType } from "@/components/graph/GraphControls";
import { GraphSidebar } from "@/components/graph/GraphSidebar";
import { NodeDetailsPanel } from "@/components/graph/NodeDetailsPanel";
import { GraphLegend } from "@/components/graph/GraphLegend";
import { ClassificationApprovalPanel } from "@/components/graph/ClassificationApprovalPanel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertCircle, Tags } from "lucide-react";
import {
  useSourceGraphStore,
  useGraphMetadata,
} from "@/lib/stores/source-graph-store";
import { usePendingClassifications, useClassifySources } from "@/lib/api/graph";

export default function GraphPage() {
  const router = useRouter();
  const metadata = useGraphMetadata();
  const currentLayout = useSourceGraphStore((s) => s.currentLayout);
  const applyLayout = useSourceGraphStore((s) => s.applyLayout);
  const saveLayout = useSourceGraphStore((s) => s.saveLayout);
  const loadLayout = useSourceGraphStore((s) => s.loadLayout);
  const selectedNodeId = useSourceGraphStore((s) => s.selectedNodeId);

  const [legendOpen, setLegendOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [approvalPanelOpen, setApprovalPanelOpen] = useState(false);

  // Fetch pending classifications
  const { data: pendingData } = usePendingClassifications();
  const pendingCount = (pendingData as any)?.total || 0;

  // Classify all sources mutation
  const classifyMutation = useClassifySources();

  const handleSourceOpen = useCallback(
    (sourceId: string) => {
      router.push(`/sources/${sourceId}`);
    },
    [router]
  );

  const handleLayoutChange = useCallback(
    (layout: LayoutType) => {
      applyLayout(layout);
    },
    [applyLayout]
  );

  const handleSaveLayout = useCallback(
    (name: string) => {
      saveLayout(name, "");
    },
    [saveLayout]
  );

  const handleLoadLayout = useCallback(
    (id: string) => {
      loadLayout(id);
    },
    [loadLayout]
  );

  const totalConnections = Object.values(metadata.edge_type_counts).reduce(
    (a, b) => a + b,
    0
  );

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-3 flex-shrink-0 animate-fade-in-up">
        <div>
          <h1 className="text-lg font-semibold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">Knowledge Graph</h1>
          <p className="text-xs text-muted-foreground">
            {metadata.total_sources} source{metadata.total_sources !== 1 ? "s" : ""}
            {" -- "}
            {totalConnections} connection{totalConnections !== 1 ? "s" : ""}
          </p>
        </div>

        {/* Classification Controls */}
        <div className="flex items-center gap-2">
          {pendingCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setApprovalPanelOpen(true)}
              className="relative"
            >
              <AlertCircle className="w-4 h-4 mr-2" />
              Review Classifications
              <Badge
                variant="destructive"
                className="ml-2 bg-yellow-500 hover:bg-yellow-600"
              >
                {pendingCount}
              </Badge>
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              // TODO: Get all source IDs and classify
              alert("Classify All Sources - This will trigger background classification for all sources");
            }}
            disabled={classifyMutation.isPending}
          >
            <Tags className="w-4 h-4 mr-2" />
            {classifyMutation.isPending ? "Classifying..." : "Classify All"}
          </Button>
        </div>
      </div>

      {/* Main content: sidebar + canvas */}
      <div className="flex flex-1 overflow-hidden">
        {/* Filter sidebar */}
        <GraphSidebar
          className="shrink-0 border-r"
          onCollapsedChange={setSidebarCollapsed}
        />

        {/* Canvas area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Toolbar */}
          <GraphControls
            layout={currentLayout}
            onLayoutChange={handleLayoutChange}
            onZoomIn={() => {
              document
                .querySelector<HTMLButtonElement>(".react-flow__controls-zoomin")
                ?.click();
            }}
            onZoomOut={() => {
              document
                .querySelector<HTMLButtonElement>(".react-flow__controls-zoomout")
                ?.click();
            }}
            onFitView={() => {
              document
                .querySelector<HTMLButtonElement>(".react-flow__controls-fitview")
                ?.click();
            }}
            onSaveLayout={handleSaveLayout}
            onLoadLayout={handleLoadLayout}
            onShowLegend={() => setLegendOpen(true)}
          />

          {/* Graph canvas */}
          <div className="flex-1">
            <GraphCanvas onSourceOpen={handleSourceOpen} />
          </div>
        </div>
      </div>

      {/* Node details slide-out panel */}
      <NodeDetailsPanel onOpenSource={handleSourceOpen} />

      {/* Legend dialog */}
      <GraphLegend open={legendOpen} onOpenChange={setLegendOpen} />

      {/* Classification Approval Dialog */}
      <Dialog open={approvalPanelOpen} onOpenChange={setApprovalPanelOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle>Review Classifications</DialogTitle>
          </DialogHeader>
          <ClassificationApprovalPanel
            onApprovalComplete={() => {
              // Optionally close or keep open
            }}
            onClose={() => setApprovalPanelOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
