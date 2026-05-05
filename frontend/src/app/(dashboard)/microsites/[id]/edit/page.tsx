"use client";

import { useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { micrositesApi } from "@/lib/api/microsites";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Eye, Code, MessageSquare, Save, History } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { VisualEditor } from "@/components/microsites/VisualEditor";
import { MicrositeChat } from "@/components/microsites/MicrositeChat";
import { CodeEditorPanel } from "@/components/microsites/CodeEditorPanel";
import { PublishControls } from "@/components/microsites/PublishControls";
import { VersionTimeline } from "@/components/microsites/VersionTimeline";
import type { MicrositeContent, MicrositeVersion } from "@/lib/types";

export default function MicrositeEditPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const micrositeId = params.id as string;
  const initialMode = searchParams.get("mode") || "visual";

  const [editMode, setEditMode] = useState<"visual" | "code" | "chat">(
    initialMode as "visual" | "code" | "chat"
  );
  const [previewKey, setPreviewKey] = useState(0);
  const [showVersions, setShowVersions] = useState(false);
  const [previewVersion, setPreviewVersion] = useState<number | undefined>();

  // Fetch microsite details (for status, active_version_id)
  const { data: microsite } = useQuery({
    queryKey: ["microsite", micrositeId],
    queryFn: () => micrositesApi.get(micrositeId),
  });

  // Fetch microsite content
  const { data: content, isLoading } = useQuery({
    queryKey: ["microsite-content", micrositeId],
    queryFn: () => micrositesApi.getContent(micrositeId),
  });

  // Publish mutation
  const publishMutation = useMutation({
    mutationFn: (message?: string) =>
      micrositesApi.publish(micrositeId, { version_message: message }),
    onSuccess: () => {
      toast.success("Microsite published successfully");
      queryClient.invalidateQueries({ queryKey: ["microsite", micrositeId] });
      queryClient.invalidateQueries({ queryKey: ["microsite-versions", micrositeId] });
      queryClient.invalidateQueries({ queryKey: ["microsites"] });
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Failed to publish");
    },
  });

  // Unpublish mutation
  const unpublishMutation = useMutation({
    mutationFn: () => micrositesApi.unpublish(micrositeId),
    onSuccess: () => {
      toast.success("Microsite unpublished");
      queryClient.invalidateQueries({ queryKey: ["microsite", micrositeId] });
      queryClient.invalidateQueries({ queryKey: ["microsites"] });
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Failed to unpublish");
    },
  });

  // Block mutation
  const blockMutation = useMutation({
    mutationFn: (reason: string) => micrositesApi.block(micrositeId, reason),
    onSuccess: () => {
      toast.success("Microsite blocked");
      queryClient.invalidateQueries({ queryKey: ["microsite", micrositeId] });
      queryClient.invalidateQueries({ queryKey: ["microsites"] });
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Failed to block");
    },
  });

  // Rollback mutation
  const rollbackMutation = useMutation({
    mutationFn: (versionNumber: number) =>
      micrositesApi.rollback(micrositeId, versionNumber),
    onSuccess: (_, versionNumber) => {
      toast.success(`Restored version ${versionNumber}`);
      queryClient.invalidateQueries({ queryKey: ["microsite", micrositeId] });
      queryClient.invalidateQueries({ queryKey: ["microsite-content", micrositeId] });
      queryClient.invalidateQueries({ queryKey: ["microsite-versions", micrositeId] });
      setPreviewKey((prev) => prev + 1);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Failed to restore version");
    },
  });

  // Callback to refresh preview when chat makes changes
  const handleChatChanges = () => {
    setPreviewKey((prev) => prev + 1);
  };

  // Update content mutation
  const updateMutation = useMutation({
    mutationFn: async (sections: MicrositeContent[]) => {
      return micrositesApi.updateContent(micrositeId, {
        sections: sections.map((s) => ({
          section_id: s.id,  // Backend expects database ID here
          content_html: s.content_html,
          content_json: s.content_json,
        })),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["microsite-content", micrositeId] });
    },
  });

  const handleSave = async (sections: MicrositeContent[]) => {
    await updateMutation.mutateAsync(sections);
  };

  const handlePreviewVersion = (version: MicrositeVersion) => {
    setPreviewVersion(version.version_number);
    setPreviewKey((prev) => prev + 1);
  };

  const handleRestoreVersion = (version: MicrositeVersion) => {
    rollbackMutation.mutate(version.version_number);
  };

  // Determine preview URL based on whether viewing a specific version
  const previewUrl = previewVersion
    ? `/api/microsites/${micrositeId}/preview?version=${previewVersion}&t=${previewKey}`
    : `/api/microsites/${micrositeId}/preview?t=${previewKey}`;

  // TODO: Implement proper unpublished changes detection by comparing
  // current content with active version snapshot. For now, assume true
  // if the microsite has been published (has an active version).
  const hasUnpublishedChanges = !!microsite?.active_version_id;

  if (isLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 dark:bg-gray-800 rounded w-1/4 mb-4" />
          <div className="h-64 bg-gray-200 dark:bg-gray-800 rounded" />
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center">
          <p className="text-muted-foreground">Content not found</p>
          <Link href={`/microsites/${micrositeId}`}>
            <Button className="mt-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Microsite
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Link href={`/microsites/${micrositeId}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
          </Link>
          <h1 className="text-2xl font-bold">Edit Microsite</h1>
        </div>

        <div className="flex items-center gap-2">
          {/* Publish Controls */}
          {microsite && (
            <PublishControls
              micrositeId={micrositeId}
              status={microsite.status}
              hasUnpublishedChanges={hasUnpublishedChanges}
              onPublish={async (message) => {
                await publishMutation.mutateAsync(message);
              }}
              onUnpublish={async () => {
                await unpublishMutation.mutateAsync();
              }}
              onBlock={async (reason) => {
                await blockMutation.mutateAsync(reason);
              }}
              isOwner={true} // TODO: Check actual ownership via auth
            />
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setShowVersions(!showVersions);
              if (previewVersion) {
                setPreviewVersion(undefined);
                setPreviewKey((prev) => prev + 1);
              }
            }}
          >
            <History className="w-4 h-4 mr-2" />
            {showVersions ? "Hide Versions" : "Versions"}
          </Button>

          <Button variant="outline" size="sm" asChild>
            <Link href={`/api/microsites/${micrositeId}/preview`} target="_blank">
              <Eye className="w-4 h-4 mr-2" />
              Preview
            </Link>
          </Button>
          <Button size="sm" onClick={() => toast.success("Saved!")}>
            <Save className="w-4 h-4 mr-2" />
            Save
          </Button>
        </div>
      </div>

      <div className="flex gap-4">
        {/* Main Content Area */}
        <div className="flex-1 min-w-0">
          {/* Edit Mode Tabs */}
          <Tabs value={editMode} onValueChange={(v) => setEditMode(v as "visual" | "code" | "chat")}>
            <TabsList className="mb-4">
              <TabsTrigger value="chat">
                <MessageSquare className="w-4 h-4 mr-2" />
                AI Chat
              </TabsTrigger>
              <TabsTrigger value="visual">
                <Eye className="w-4 h-4 mr-2" />
                Visual Editor
              </TabsTrigger>
              <TabsTrigger value="code">
                <Code className="w-4 h-4 mr-2" />
                Code Editor
              </TabsTrigger>
            </TabsList>

            <TabsContent value="chat" className="mt-0">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* AI Chat Interface */}
                <div>
                  <MicrositeChat
                    micrositeId={micrositeId}
                    onChangesApplied={handleChatChanges}
                  />
                </div>

                {/* Live Preview */}
                <div className="border rounded-lg p-4 bg-white dark:bg-gray-950">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium">
                      {previewVersion ? `Preview (v${previewVersion})` : "Live Preview"}
                    </h3>
                    <div className="flex gap-2">
                      {previewVersion && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setPreviewVersion(undefined);
                            setPreviewKey((prev) => prev + 1);
                          }}
                        >
                          Back to Current
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setPreviewKey((prev) => prev + 1)}
                      >
                        Refresh
                      </Button>
                    </div>
                  </div>
                  <iframe
                    key={previewKey}
                    src={previewUrl}
                    className="w-full h-[600px] border rounded"
                    sandbox="allow-scripts allow-same-origin"
                    title="Microsite Preview"
                  />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="visual" className="mt-0">
              <div className="border rounded-lg p-6 bg-white dark:bg-gray-950">
                {content && content.sections && content.sections.length > 0 ? (
                  <VisualEditor
                    sections={content.sections}
                    micrositeId={micrositeId}
                    onSave={handleSave}
                    onSettingsUpdate={() => {
                      // Invalidate queries to refetch data
                      queryClient.invalidateQueries({ queryKey: ["microsite-content", micrositeId] });
                      setPreviewKey((prev) => prev + 1);
                    }}
                  />
                ) : (
                  <p className="text-muted-foreground text-center py-8">
                    No content sections found. Generate content first.
                  </p>
                )}
              </div>
            </TabsContent>

            <TabsContent value="code" className="mt-0">
              {content && content.sections && content.sections.length > 0 ? (
                <CodeEditorPanel
                  sections={content.sections}
                  micrositeId={micrositeId}
                  onSave={handleSave}
                />
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  No content to edit. Generate content first.
                </p>
              )}
            </TabsContent>
          </Tabs>
        </div>

        {/* Version Timeline Sidebar (collapsible) */}
        {showVersions && (
          <div className="w-[350px] flex-shrink-0">
            <VersionTimeline
              micrositeId={micrositeId}
              activeVersionId={microsite?.active_version_id}
              onPreview={handlePreviewVersion}
              onRestore={handleRestoreVersion}
            />
          </div>
        )}
      </div>
    </div>
  );
}
