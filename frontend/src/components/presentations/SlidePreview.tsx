/**
 * Slide Preview Component
 *
 * Interactive iframe-based preview with navigation and download.
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Edit,
  ZoomIn,
  ZoomOut,
  Maximize,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { presentationApi, type SlideContent } from "@/lib/api/presentations";
import { SlideEditor } from "./SlideEditor";
import { cn } from "@/lib/utils";

interface SlidePreviewProps {
  presentationId: string;
  onEdit?: (slideNumber: number) => void;
  onClose?: () => void;
}

export function SlidePreview({
  presentationId,
  onEdit,
  onClose,
}: SlidePreviewProps) {
  const [currentSlide, setCurrentSlide] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch slides
  const { data: slides, isLoading: slidesLoading } = useQuery({
    queryKey: ["presentation-slides", presentationId],
    queryFn: () => presentationApi.getSlides(presentationId),
  });

  // Fetch presentation metadata
  const { data: presentation } = useQuery({
    queryKey: ["presentation", presentationId],
    queryFn: () => presentationApi.get(presentationId),
  });

  const totalSlides = slides?.length || 0;

  // Navigate to specific slide
  const navigateToSlide = (slideNumber: number) => {
    if (slideNumber < 1 || slideNumber > totalSlides) return;

    setCurrentSlide(slideNumber);

    // Send message to iframe
    iframeRef.current?.contentWindow?.postMessage(
      { action: "navigateToSlide", slideNumber },
      "*"
    );
  };

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" && currentSlide < totalSlides) {
        navigateToSlide(currentSlide + 1);
      } else if (e.key === "ArrowLeft" && currentSlide > 1) {
        navigateToSlide(currentSlide - 1);
      } else if (e.key === "Escape" && isFullscreen) {
        setIsFullscreen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentSlide, totalSlides, isFullscreen]);

  // Download PPTX
  const handleDownload = async () => {
    try {
      await presentationApi.download(
        presentationId,
        presentation?.title || "presentation"
      );
      toast.success("Downloaded presentation");
    } catch (error) {
      console.error("Download failed:", error);
      toast.error("Failed to download presentation");
    }
  };

  // Zoom controls
  const handleZoomIn = () => setZoom(Math.min(150, zoom + 10));
  const handleZoomOut = () => setZoom(Math.max(50, zoom - 10));

  if (slidesLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!slides || slides.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 text-muted-foreground">
        No slides found
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "flex flex-col bg-background",
        isFullscreen ? "fixed inset-0 z-50" : "h-full"
      )}
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 p-4 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          {/* Navigation */}
          <Button
            variant="outline"
            size="icon"
            onClick={() => navigateToSlide(currentSlide - 1)}
            disabled={currentSlide === 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          <span className="text-sm font-medium min-w-[80px] text-center">
            {currentSlide} / {totalSlides}
          </span>

          <Button
            variant="outline"
            size="icon"
            onClick={() => navigateToSlide(currentSlide + 1)}
            disabled={currentSlide === totalSlides}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>

          {/* Zoom */}
          <div className="flex items-center gap-1 ml-4">
            <Button
              variant="outline"
              size="icon"
              onClick={handleZoomOut}
              disabled={zoom <= 50}
            >
              <ZoomOut className="h-4 w-4" />
            </Button>

            <span className="text-sm font-medium min-w-[60px] text-center">
              {zoom}%
            </span>

            <Button
              variant="outline"
              size="icon"
              onClick={handleZoomIn}
              disabled={zoom >= 150}
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Edit */}
          {onEdit && (
            <Button
              variant="outline"
              onClick={() => {
                setEditingSlide(currentSlide);
                onEdit?.(currentSlide);
              }}
              className="gap-2"
            >
              <Edit className="h-4 w-4" />
              Edit Slide
            </Button>
          )}

          {/* Download */}
          <Button onClick={handleDownload} className="gap-2">
            <Download className="h-4 w-4" />
            Download PPTX
          </Button>

          {/* Fullscreen */}
          <Button
            variant="outline"
            size="icon"
            onClick={() => setIsFullscreen(!isFullscreen)}
          >
            {isFullscreen ? (
              <X className="h-4 w-4" />
            ) : (
              <Maximize className="h-4 w-4" />
            )}
          </Button>

          {/* Close */}
          {onClose && !isFullscreen && (
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Preview Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main Preview */}
        <div className="flex-1 flex items-center justify-center bg-slate-900 p-8 overflow-auto">
          <div
            className="bg-white shadow-2xl transition-transform duration-200"
            style={{
              transform: `scale(${zoom / 100})`,
              transformOrigin: "center center",
            }}
          >
            <iframe
              ref={iframeRef}
              src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5055'}/api/presentations/${presentationId}/preview`}
              className="w-[960px] h-[540px] border-0"
              sandbox="allow-scripts allow-same-origin"
              title="Presentation Preview"
            />
          </div>
        </div>

        {/* Slide Thumbnails */}
        <div className="w-64 border-l bg-muted/20 overflow-y-auto">
          <div className="p-4 space-y-2">
            {slides.map((slide, idx) => {
              const slideNumber = idx + 1;
              const isActive = currentSlide === slideNumber;

              // Parse content_json if it's a string
              const contentJson =
                typeof slide.content_json === "string"
                  ? JSON.parse(slide.content_json)
                  : slide.content_json;

              return (
                <button
                  key={slide.id}
                  onClick={() => navigateToSlide(slideNumber)}
                  className={cn(
                    "w-full text-left p-3 rounded-lg border transition-colors",
                    isActive
                      ? "bg-primary/10 border-primary"
                      : "bg-background hover:bg-muted border-border"
                  )}
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={cn(
                        "text-xs font-medium flex-shrink-0 mt-0.5",
                        isActive ? "text-primary" : "text-muted-foreground"
                      )}
                    >
                      {slideNumber}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {contentJson.title || `Slide ${slideNumber}`}
                      </p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {slide.slide_type.replace("_", " ")}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Keyboard Shortcuts Hint */}
      {!isFullscreen && (
        <div className="border-t bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
          Use <kbd className="px-1.5 py-0.5 bg-muted rounded border">←</kbd>{" "}
          <kbd className="px-1.5 py-0.5 bg-muted rounded border">→</kbd> to
          navigate •{" "}
          <kbd className="px-1.5 py-0.5 bg-muted rounded border">Esc</kbd> to
          exit fullscreen
        </div>
      )}

      {/* Slide Editor Dialog */}
      {editingSlide && (
        <SlideEditor
          presentationId={presentationId}
          slideNumber={editingSlide}
          open={editingSlide !== null}
          onOpenChange={(open) => {
            if (!open) setEditingSlide(null);
          }}
        />
      )}
    </div>
  );
}
