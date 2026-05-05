"use client";

import * as React from "react";
import {
  ZoomIn,
  ZoomOut,
  Maximize,
  Download,
  Save,
  FolderOpen,
  HelpCircle,
  Image,
  FileCode,
  FileJson,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LayoutType = "force" | "hierarchical" | "circular" | "manual";

export interface SavedLayout {
  id: string;
  name: string;
  createdAt: string;
}

interface GraphControlsProps {
  layout: LayoutType;
  onLayoutChange: (layout: LayoutType) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitView: () => void;
  onExportPNG?: () => void;
  onExportSVG?: () => void;
  onExportJSON?: () => void;
  onSaveLayout?: (name: string) => void;
  onLoadLayout?: (id: string) => void;
  onShowLegend?: () => void;
  savedLayouts?: SavedLayout[];
  className?: string;
}

// ---------------------------------------------------------------------------
// Layout options
// ---------------------------------------------------------------------------

const LAYOUT_OPTIONS: { value: LayoutType; label: string }[] = [
  { value: "force", label: "Force" },
  { value: "hierarchical", label: "Hierarchical" },
  { value: "circular", label: "Circular" },
  { value: "manual", label: "Manual" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const GraphControls = React.memo(function GraphControls({
  layout,
  onLayoutChange,
  onZoomIn,
  onZoomOut,
  onFitView,
  onExportPNG,
  onExportSVG,
  onExportJSON,
  onSaveLayout,
  onLoadLayout,
  onShowLegend,
  savedLayouts = [],
  className,
}: GraphControlsProps) {
  const [saveDialogOpen, setSaveDialogOpen] = React.useState(false);
  const [layoutName, setLayoutName] = React.useState("");

  const handleSave = () => {
    if (layoutName.trim() && onSaveLayout) {
      onSaveLayout(layoutName.trim());
      setLayoutName("");
      setSaveDialogOpen(false);
    }
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div
        className={cn(
          "flex items-center gap-1 px-2 py-1.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950",
          className
        )}
      >
        {/* Zoom controls */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onZoomIn}>
              <ZoomIn className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Zoom in</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onZoomOut}>
              <ZoomOut className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Zoom out</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onFitView}>
              <Maximize className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Fit view</TooltipContent>
        </Tooltip>

        <Separator orientation="vertical" className="mx-1 h-6" />

        {/* Layout selector */}
        <Select value={layout} onValueChange={(val) => onLayoutChange(val as LayoutType)}>
          <SelectTrigger className="h-8 w-[130px] text-sm">
            <SelectValue placeholder="Layout" />
          </SelectTrigger>
          <SelectContent>
            {LAYOUT_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Separator orientation="vertical" className="mx-1 h-6" />

        {/* Export */}
        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-sm">
                  <Download className="h-4 w-4" />
                  Export
                </Button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent>Export graph</TooltipContent>
          </Tooltip>
          <DropdownMenuContent align="start">
            <DropdownMenuItem onClick={onExportPNG} disabled={!onExportPNG}>
              <Image className="h-4 w-4 mr-2" />
              PNG Image
            </DropdownMenuItem>
            <DropdownMenuItem onClick={onExportSVG} disabled={!onExportSVG}>
              <FileCode className="h-4 w-4 mr-2" />
              SVG Vector
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onExportJSON} disabled={!onExportJSON}>
              <FileJson className="h-4 w-4 mr-2" />
              JSON Data
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Save layout */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setSaveDialogOpen(true)}
            >
              <Save className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Save layout</TooltipContent>
        </Tooltip>

        {/* Load layout */}
        {savedLayouts.length > 0 && (
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <FolderOpen className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent>Load saved layout</TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="start">
              <DropdownMenuLabel>Saved Layouts</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {savedLayouts.map((sl) => (
                <DropdownMenuItem
                  key={sl.id}
                  onClick={() => onLoadLayout?.(sl.id)}
                >
                  {sl.name}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        <div className="flex-1" />

        {/* Help */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onShowLegend}
            >
              <HelpCircle className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Show legend</TooltipContent>
        </Tooltip>
      </div>

      {/* Save Layout Dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Save Layout</DialogTitle>
            <DialogDescription>
              Save the current graph layout for quick access later.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="layout-name">Layout name</Label>
            <Input
              id="layout-name"
              placeholder="My layout..."
              value={layoutName}
              onChange={(e) => setLayoutName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleSave();
                }
              }}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSaveDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!layoutName.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  );
});
