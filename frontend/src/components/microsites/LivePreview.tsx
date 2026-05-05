"use client";

import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import {
  Monitor,
  Tablet,
  Smartphone,
  RefreshCw,
  ExternalLink,
  ZoomIn,
  Loader2,
} from "lucide-react";

const DEVICES = {
  desktop: { width: "100%", label: "Desktop", icon: Monitor },
  tablet: { width: "768px", label: "Tablet", icon: Tablet },
  mobile: { width: "375px", label: "Mobile", icon: Smartphone },
} as const;

type DeviceType = keyof typeof DEVICES;

interface LivePreviewProps {
  html?: string;
  previewUrl?: string;
  micrositeId?: string;
  isLoading?: boolean;
}

export function LivePreview({ html, previewUrl, micrositeId, isLoading }: LivePreviewProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [device, setDevice] = useState<DeviceType>("desktop");
  const [zoom, setZoom] = useState(100);

  // Build preview URL from micrositeId if provided
  const effectivePreviewUrl = useMemo(() => {
    if (previewUrl) return previewUrl;
    if (micrositeId) return `/api/microsites/${micrositeId}/preview?t=${Date.now()}`;
    return undefined;
  }, [previewUrl, micrositeId]);

  const refreshPreview = useCallback(() => {
    if (iframeRef.current) {
      if (effectivePreviewUrl) {
        iframeRef.current.src = effectivePreviewUrl + `&refresh=${Date.now()}`;
      } else if (html) {
        const doc = iframeRef.current.contentDocument;
        if (doc) {
          doc.open();
          doc.write(html);
          doc.close();
        }
      }
    }
  }, [html, effectivePreviewUrl]);

  useEffect(() => {
    refreshPreview();
  }, [refreshPreview]);

  const deviceConfig = DEVICES[device];

  return (
    <div className="flex flex-col h-full border rounded-lg overflow-hidden">
      {/* Controls */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          {(Object.entries(DEVICES) as [DeviceType, typeof DEVICES[DeviceType]][]).map(
            ([key, config]) => {
              const Icon = config.icon;
              return (
                <Button
                  key={key}
                  variant={device === key ? "secondary" : "ghost"}
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setDevice(key)}
                  title={config.label}
                >
                  <Icon className="w-4 h-4" />
                </Button>
              );
            }
          )}
          <Badge variant="outline" className="text-xs ml-2">
            {deviceConfig.label}
          </Badge>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <ZoomIn className="w-3 h-3 text-muted-foreground" />
            <Slider
              value={[zoom]}
              onValueChange={([v]) => setZoom(v)}
              min={50}
              max={150}
              step={25}
              className="w-24"
            />
            <span className="text-xs text-muted-foreground w-8">{zoom}%</span>
          </div>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={refreshPreview}>
            <RefreshCw className="w-4 h-4" />
          </Button>
          {effectivePreviewUrl && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => window.open(effectivePreviewUrl, "_blank")}
              title="Open in new tab"
            >
              <ExternalLink className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Preview Area */}
      <div className="flex-1 bg-gray-100 dark:bg-gray-900 overflow-auto flex justify-center p-4">
        {isLoading ? (
          <div className="flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div
            className="bg-white shadow-lg transition-all duration-300"
            style={{
              width: deviceConfig.width,
              maxWidth: "100%",
              height: "100%",
              transform: `scale(${zoom / 100})`,
              transformOrigin: "top center",
            }}
          >
            <iframe
              ref={iframeRef}
              className="w-full h-full border-0"
              sandbox="allow-scripts allow-same-origin"
              title="Microsite Preview"
            />
          </div>
        )}
      </div>
    </div>
  );
}
