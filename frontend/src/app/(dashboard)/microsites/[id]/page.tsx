"use client";

import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  Eye,
  Pencil,
  ExternalLink,
  Copy,
  Settings,
  History,
  Shield,
} from "lucide-react";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { formatRelativeTime } from "@/lib/utils";
import { LivePreview } from "@/components/microsites/LivePreview";

export default function MicrositeDetailPage() {
  const params = useParams();
  const router = useRouter();
  const micrositeId = params.id as string;

  const { data: microsite, isLoading } = useQuery({
    queryKey: ["microsite", micrositeId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/microsites/${micrositeId}`);
      return data;
    },
  });

  const { data: content } = useQuery({
    queryKey: ["microsite-content", micrositeId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/microsites/${micrositeId}/content`);
      return data;
    },
  });

  const copyPublicUrl = () => {
    if (microsite) {
      const url = `${window.location.origin}${microsite.access_url}`;
      navigator.clipboard.writeText(url);
      toast.success("Public URL copied to clipboard");
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!microsite) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h3 className="text-lg font-semibold mb-2">Microsite not found</h3>
          <Button onClick={() => router.push("/microsites")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Microsites
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.push("/microsites")}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{microsite.title}</h1>
            {microsite.description && (
              <p className="text-gray-500 dark:text-gray-400 mt-1">
                {microsite.description}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => router.push(`/microsites/${micrositeId}/edit?mode=visual`)}
          >
            <Pencil className="w-4 h-4 mr-2" />
            Edit (WYSIWYG)
          </Button>
          <Button
            variant="outline"
            onClick={() => router.push(`/microsites/${micrositeId}/edit?mode=code`)}
          >
            <Pencil className="w-4 h-4 mr-2" />
            Edit (Code)
          </Button>
          <Button
            variant="outline"
            onClick={() => window.open(`${window.location.origin}${microsite.access_url}`, "_blank")}
          >
            <ExternalLink className="w-4 h-4 mr-2" />
            Open Public URL
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Status</CardTitle>
            <Eye className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Badge variant={microsite.is_active ? "default" : "secondary"}>
              {microsite.is_active ? "Active" : "Inactive"}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Version</CardTitle>
            <History className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">v{microsite.published_version || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Moderation</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Badge
              className={
                microsite.moderation_status === "passed"
                  ? "bg-green-100 text-green-700"
                  : microsite.moderation_status === "warning"
                  ? "bg-yellow-100 text-yellow-700"
                  : "bg-red-100 text-red-700"
              }
            >
              {microsite.moderation_status || "Not run"}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Last Updated</CardTitle>
            <Settings className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-sm">{formatRelativeTime(microsite.updated)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Public URL */}
      <Card>
        <CardHeader>
          <CardTitle>Public URL</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <div className="flex-1 p-3 bg-gray-50 dark:bg-gray-900 rounded-lg font-mono text-sm">
              {window.location.origin}{microsite.access_url}
            </div>
            <Button variant="outline" onClick={copyPublicUrl}>
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Content Sections */}
      {content && content.sections && content.sections.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Content Sections ({content.sections.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {content.sections.map((section: any) => (
                <div
                  key={section.section_id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div>
                    <p className="font-medium">{section.section_id}</p>
                    {section.section_type && (
                      <p className="text-sm text-gray-500">{section.section_type}</p>
                    )}
                  </div>
                  <Badge variant="outline">Order: {section.order_num}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Live Preview */}
      <Card>
        <CardHeader>
          <CardTitle>Live Preview</CardTitle>
        </CardHeader>
        <CardContent>
          <LivePreview micrositeId={micrositeId} />
        </CardContent>
      </Card>
    </div>
  );
}
