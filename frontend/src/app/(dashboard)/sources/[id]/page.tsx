"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSource, useDeleteSource, useUpdateSource } from "@/lib/hooks/use-api";
import { sourcesApi } from "@/lib/api/sources";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TagInput } from "@/components/ui/tag-input";
import {
  ArrowLeft,
  FileText,
  Link as LinkIcon,
  Type,
  Youtube,
  Database,
  Plug,
  Sparkles,
  RefreshCw,
  Trash2,
  Eye,
  Network,
  Edit,
  Check,
  X,
} from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { formatRelativeTime, cn } from "@/lib/utils";
import { getTagColorStyle } from "@/lib/utils/tag-colors";
import { toast } from "sonner";
import type { SourceType } from "@/lib/types";
import { FullContentModal } from "@/components/sources/full-content-modal";
import { AssetMetadataCard } from "@/components/sources/asset-metadata-card";

const sourceTypeConfig = {
  file: { icon: FileText, color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300", label: "File Upload" },
  url: { icon: LinkIcon, color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300", label: "Web URL" },
  text: { icon: Type, color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300", label: "Text" },
  youtube: { icon: Youtube, color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300", label: "YouTube" },
  hana_table: { icon: Database, color: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300", label: "HANA Table" },
  api: { icon: Plug, color: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300", label: "API" },
};

const syncStatusConfig: Record<string, { label: string; color: string }> = {
  idle: { label: "Idle", color: "bg-gray-100 text-gray-700" },
  scheduled: { label: "Scheduled", color: "bg-blue-100 text-blue-700" },
  syncing: { label: "Syncing...", color: "bg-yellow-100 text-yellow-700" },
  embedding: { label: "Embedding...", color: "bg-purple-100 text-purple-700" },
  completed: { label: "Ready", color: "bg-green-100 text-green-700" },
  success: { label: "Success", color: "bg-green-100 text-green-700" },
  error: { label: "Error", color: "bg-red-100 text-red-700" },
  failed: { label: "Failed", color: "bg-red-100 text-red-700" },
};

export default function SourceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sourceId = params.id as string;

  const { data: source, isLoading, error, refetch } = useSource(sourceId);
  const deleteMutation = useDeleteSource();
  const updateMutation = useUpdateSource();

  const [isEditingTags, setIsEditingTags] = useState(false);
  const [editedTags, setEditedTags] = useState<string[]>([]);

  const handleRegenerateEmbeddings = async () => {
    try {
      toast.loading("Starting embedding generation...");
      const result = await sourcesApi.regenerateEmbeddings(sourceId);
      toast.dismiss();
      toast.success(result.message || "Embedding generation started");

      // Refetch after a short delay to show updated status
      setTimeout(() => refetch(), 1000);
    } catch (error: any) {
      toast.dismiss();
      toast.error(error.message || "Failed to start embedding generation");
    }
  };

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(sourceId);
      toast.success("Source deleted successfully");
      router.push("/sources");
    } catch (error: any) {
      toast.error(error.message || "Failed to delete source");
    }
  };

  const handleEditTags = () => {
    setEditedTags(source?.tags || []);
    setIsEditingTags(true);
  };

  const handleSaveTags = async () => {
    try {
      await updateMutation.mutateAsync({
        id: sourceId,
        data: { tags: editedTags },
      });
      toast.success("Tags updated successfully");
      setIsEditingTags(false);
      refetch();
    } catch (error: any) {
      toast.error(error.message || "Failed to update tags");
    }
  };

  const handleCancelEditTags = () => {
    setIsEditingTags(false);
    setEditedTags([]);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-48" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !source) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh]">
        <FileText className="w-16 h-16 text-gray-400 mb-4" />
        <h3 className="text-lg font-semibold mb-2">Source not found</h3>
        <p className="text-gray-500 mb-4">The source you're looking for doesn't exist.</p>
        <Button onClick={() => router.push("/sources")}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Sources
        </Button>
      </div>
    );
  }

  const config = sourceTypeConfig[source.source_type];
  const Icon = config.icon;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.push("/sources")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <div className={cn("p-3 rounded-lg", config.color)}>
            <Icon className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">{source.title}</h1>
            <p className="text-gray-500">{config.label}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => router.push(`/graph?focus=${sourceId}`)}>
            <Network className="w-4 h-4 mr-2" />
            View in Graph
          </Button>
          <Button variant="outline" onClick={handleRegenerateEmbeddings}>
            <Sparkles className="w-4 h-4 mr-2" />
            Regenerate Embeddings
          </Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline">
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Source</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete this source? This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete}>Delete</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Status Card */}
      <Card>
        <CardHeader>
          <CardTitle>Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-500 mb-1">Type</p>
              <Badge className={config.color}>{config.label}</Badge>
            </div>

            <div>
              <p className="text-sm text-gray-500 mb-1">Embedding Status</p>
              {source.sync_status && syncStatusConfig[source.sync_status] ? (
                <Badge className={syncStatusConfig[source.sync_status].color}>
                  {syncStatusConfig[source.sync_status].label}
                </Badge>
              ) : (
                <Badge variant="outline" className="text-gray-500">
                  No embeddings
                </Badge>
              )}
            </div>

            <div>
              <p className="text-sm text-gray-500 mb-1">Chunks</p>
              {source.chunk_count && source.chunk_count > 0 ? (
                <Badge variant="outline">
                  <Sparkles className="w-3 h-3 mr-1" />
                  {source.chunk_count} chunks
                </Badge>
              ) : (
                <span className="text-sm text-gray-600">None</span>
              )}
            </div>

            <div>
              <p className="text-sm text-gray-500 mb-1">Last Updated</p>
              <p className="text-sm font-medium">{formatRelativeTime(source.updated)}</p>
            </div>
          </div>

          {source.last_synced && (
            <div>
              <p className="text-sm text-gray-500 mb-1">Last Synced</p>
              <p className="text-sm font-medium">{formatRelativeTime(source.last_synced)}</p>
            </div>
          )}

          {source.error_message && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600">{source.error_message}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Content Card */}
      {source.full_text && source.full_text.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Content Preview</CardTitle>
            <FullContentModal
              source={source}
              trigger={
                <Button variant="outline" size="sm">
                  <Eye className="w-4 h-4 mr-2" />
                  View Full Content
                </Button>
              }
            />
          </CardHeader>
          <CardContent>
            <div className="prose dark:prose-invert max-w-none">
              <pre className="whitespace-pre-wrap text-sm bg-gray-50 dark:bg-gray-900 p-4 rounded-md max-h-96 overflow-auto">
                {source.full_text.slice(0, 2000)}
                {source.full_text.length > 2000 && (
                  <span className="text-gray-500 dark:text-gray-400">
                    {"\n\n"}... ({(source.full_text.length - 2000).toLocaleString()} more characters - click 'View Full Content' above)
                  </span>
                )}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Asset Metadata */}
      <AssetMetadataCard source={source} />

      {/* Tags */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Tags</CardTitle>
            {!isEditingTags ? (
              <Button variant="outline" size="sm" onClick={handleEditTags}>
                <Edit className="w-4 h-4 mr-2" />
                Edit Tags
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleCancelEditTags}>
                  <X className="w-4 h-4 mr-2" />
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSaveTags} disabled={updateMutation.isPending}>
                  <Check className="w-4 h-4 mr-2" />
                  Save
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isEditingTags ? (
            <TagInput
              value={editedTags}
              onChange={setEditedTags}
              placeholder="Type and press Enter to add tags"
              disabled={updateMutation.isPending}
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              {source.tags && source.tags.length > 0 ? (
                source.tags.map((tag, idx) => {
                  const colorStyle = getTagColorStyle(tag);
                  return (
                    <Badge
                      key={idx}
                      className="border font-medium"
                      style={{
                        backgroundColor: colorStyle.backgroundColor,
                        color: colorStyle.color,
                        borderColor: colorStyle.borderColor,
                      }}
                    >
                      {tag}
                    </Badge>
                  );
                })
              ) : (
                <p className="text-sm text-gray-500">No tags yet. Click "Edit Tags" to add some.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Metadata */}
      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">ID:</span>
              <span className="ml-2 font-mono text-xs">{source.id}</span>
            </div>
            <div>
              <span className="text-gray-500">Created:</span>
              <span className="ml-2">{formatRelativeTime(source.created)}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
