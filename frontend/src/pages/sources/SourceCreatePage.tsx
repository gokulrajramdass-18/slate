
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useCreateSource, useUploadFile } from "@/lib/hooks/use-api";
import { sourcesApi } from "@/lib/api/sources";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SourceTypeSelector } from "@/components/sources/source-type-selector";
import { FileUploadForm } from "@/components/sources/file-upload-form";
import { UrlForm } from "@/components/sources/url-form";
import { TextForm } from "@/components/sources/text-form";
import { YoutubeForm } from "@/components/sources/youtube-form";
import { HanaTableForm } from "@/components/sources/hana-table-form";
import { ApiForm } from "@/components/sources/api-form";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import type { SourceType } from "@/lib/types";

export default function SourceCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const notebookId = searchParams?.get("notebook_id") || undefined;

  const [sourceType, setSourceType] = useState<SourceType>("file");

  const createMutation = useCreateSource();
  const uploadMutation = useUploadFile();

  const handleFileUpload = async (data: { file: File; title?: string; tags?: string[] }) => {
    try {
      await uploadMutation.mutateAsync({
        ...data,
        notebookId,
      });
      toast.success("File uploaded successfully");
      navigate("/sources");
    } catch (error: any) {
      toast.error(error.message || "Failed to upload file");
      throw error;
    }
  };

  const handleUrlSubmit = async (data: { url: string; title?: string; tags?: string[] }) => {
    try {
      await createMutation.mutateAsync({
        title: data.title || data.url,
        source_type: "url",
        url: data.url,
        tags: data.tags || [],
      });
      toast.success("URL source added successfully");
      navigate("/sources");
    } catch (error: any) {
      toast.error(error.message || "Failed to add URL source");
      throw error;
    }
  };

  const handleTextSubmit = async (data: { title: string; content: string; tags?: string[] }) => {
    try {
      await createMutation.mutateAsync({
        title: data.title,
        source_type: "text",
        full_text: data.content,
        tags: data.tags || [],
      });
      toast.success("Text source added successfully");
      navigate("/sources");
    } catch (error: any) {
      toast.error(error.message || "Failed to add text source");
      throw error;
    }
  };

  const handleYoutubeSubmit = async (data: { url: string; title?: string; tags?: string[] }) => {
    try {
      await createMutation.mutateAsync({
        title: data.title || data.url,
        source_type: "youtube",
        url: data.url,
        tags: data.tags || [],
      });
      toast.success("YouTube source added successfully");
      navigate("/sources");
    } catch (error: any) {
      toast.error(error.message || "Failed to add YouTube source");
      throw error;
    }
  };

  const handleHanaTableSubmit = async (data: any) => {
    try {
      await sourcesApi.hanaTable.create(data);
      toast.success("HANA table source added successfully");
      navigate("/sources");
    } catch (error: any) {
      toast.error(error.message || "Failed to add HANA table source");
      throw error;
    }
  };

  const handleApiSubmit = async (data: any) => {
    try {
      await sourcesApi.api.create({
        title: data.title,
        connection_config: {
          connection_id: data.connection_id,
        },
        sync_config: data.sync_config,
      });
      toast.success("API source added successfully");
      navigate("/sources");
    } catch (error: any) {
      toast.error(error.message || "Failed to add API source");
      throw error;
    }
  };

  const isLoading =
    createMutation.isPending || uploadMutation.isPending;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/sources")}
          className="mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Sources
        </Button>
        <h1 className="text-3xl font-bold tracking-tight">Add New Source</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          Choose a source type and configure its settings
        </p>
      </div>

      {/* Source Type Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Source Type</CardTitle>
          <CardDescription>
            Select the type of source you want to add to your research library
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SourceTypeSelector selected={sourceType} onSelect={setSourceType} />
        </CardContent>
      </Card>

      <Separator />

      {/* Source Configuration Forms */}
      <Card>
        <CardHeader>
          <CardTitle>Configure Source</CardTitle>
          <CardDescription>
            Provide the necessary details for your {sourceType} source
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sourceType === "file" && (
            <FileUploadForm onSubmit={handleFileUpload} isLoading={isLoading} />
          )}
          {sourceType === "url" && (
            <UrlForm onSubmit={handleUrlSubmit} isLoading={isLoading} />
          )}
          {sourceType === "text" && (
            <TextForm onSubmit={handleTextSubmit} isLoading={isLoading} />
          )}
          {sourceType === "youtube" && (
            <YoutubeForm onSubmit={handleYoutubeSubmit} isLoading={isLoading} />
          )}
          {sourceType === "hana_table" && (
            <HanaTableForm onSubmit={handleHanaTableSubmit} isLoading={isLoading} notebookId={notebookId} />
          )}
          {sourceType === "api" && (
            <ApiForm onSubmit={handleApiSubmit} isLoading={isLoading} notebookId={notebookId} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
