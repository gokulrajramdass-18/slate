"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Clock, Eye, RotateCcw, CheckCircle2 } from "lucide-react";
import { micrositesApi } from "@/lib/api/microsites";
import type { MicrositeVersion } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";

interface VersionTimelineProps {
  micrositeId: string;
  activeVersionId?: string;
  onPreview: (version: MicrositeVersion) => void;
  onRestore: (version: MicrositeVersion) => void;
}

export function VersionTimeline({
  micrositeId,
  activeVersionId,
  onPreview,
  onRestore,
}: VersionTimelineProps) {
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);

  const { data: versions, isLoading } = useQuery({
    queryKey: ["microsite-versions", micrositeId],
    queryFn: () => micrositesApi.listVersions(micrositeId),
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-muted-foreground">
            Loading versions...
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!versions || versions.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-muted-foreground">
            No published versions yet. Publish your microsite to create the
            first version.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Clock className="h-5 w-5" />
          Version History
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          <div className="relative space-y-4">
            {versions.map((version, index) => {
              const isActive = version.id === activeVersionId;
              const isSelected = version.id === selectedVersion;

              return (
                <div
                  key={version.id}
                  className={`relative border rounded-lg p-4 cursor-pointer transition-all ${
                    isSelected ? "border-primary bg-primary/5" : "border-border"
                  } ${isActive ? "ring-2 ring-primary" : ""} hover:border-primary/50`}
                  onClick={() => setSelectedVersion(version.id)}
                  role="button"
                  tabIndex={0}
                  aria-label={`Version ${version.version_number}${isActive ? " (active)" : ""}`}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedVersion(version.id);
                    }
                  }}
                >
                  {/* Timeline connector */}
                  {index < versions.length - 1 && (
                    <div className="absolute left-[20px] top-[60px] w-[2px] h-[calc(100%+16px)] bg-border" />
                  )}

                  {/* Version marker */}
                  <div className="absolute left-[12px] top-[16px] z-10 flex h-[18px] w-[18px] items-center justify-center rounded-full border-2 border-primary bg-background">
                    {isActive && (
                      <CheckCircle2 className="h-full w-full text-primary" />
                    )}
                  </div>

                  <div className="ml-8">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold">
                          Version {version.version_number}
                        </h4>
                        {isActive && (
                          <Badge variant="default" className="text-xs">
                            Active
                          </Badge>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {formatDistanceToNow(
                          new Date(version.published_at || version.created),
                          { addSuffix: true }
                        )}
                      </span>
                    </div>

                    <p className="text-sm text-muted-foreground mb-3">
                      Published by {version.created_by}
                    </p>

                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation();
                          onPreview(version);
                        }}
                        aria-label={`Preview version ${version.version_number}`}
                      >
                        <Eye className="h-4 w-4 mr-1" />
                        Preview
                      </Button>

                      {!isActive && (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            onRestore(version);
                          }}
                          aria-label={`Restore version ${version.version_number}`}
                        >
                          <RotateCcw className="h-4 w-4 mr-1" />
                          Restore
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
