
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Globe,
  Eye,
  Pencil,
  Trash2,
  ExternalLink,
  Plus,
  Search,
} from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { micrositesApi } from "@/lib/api/microsites";
import { apiClient } from "@/lib/api/client";
import { Link } from "react-router-dom";
import type { Microsite, MicrositeStatus } from "@/lib/types";
import { StatusBadge } from "@/components/microsites/StatusBadge";

export default function MicrositesPage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<MicrositeStatus | "all">("all");

  const { data: microsites = [], isLoading, refetch } = useQuery({
    queryKey: ["microsites"],
    queryFn: () => micrositesApi.list(),
  });

  const handleDelete = async (micrositeId: string) => {
    if (!confirm("Are you sure you want to delete this microsite?")) {
      return;
    }

    try {
      await apiClient.delete(`/microsites/${micrositeId}`);
      toast.success("Microsite deleted");
      refetch();
    } catch (error: any) {
      toast.error(error.message || "Failed to delete microsite");
    }
  };

  const filteredMicrosites = microsites
    .filter((microsite) => {
      if (statusFilter !== "all" && microsite.status !== statusFilter) {
        return false;
      }
      return (
        microsite.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (microsite.description && microsite.description.toLowerCase().includes(searchQuery.toLowerCase()))
      );
    });

  const statusCounts = microsites.reduce(
    (acc, m) => {
      acc[m.status] = (acc[m.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">Microsites</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            AI-generated websites from your workspace content
          </p>
        </div>
      </div>

      {/* Search and Status Filter */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 animate-fade-in-up animation-delay-200">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-3 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search microsites..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <Tabs value={statusFilter} onValueChange={(v) => setStatusFilter(v as MicrositeStatus | "all")}>
          <TabsList>
            <TabsTrigger value="all">
              All ({microsites.length})
            </TabsTrigger>
            <TabsTrigger value="draft">
              Drafts ({statusCounts.draft || 0})
            </TabsTrigger>
            <TabsTrigger value="published">
              Published ({statusCounts.published || 0})
            </TabsTrigger>
            <TabsTrigger value="blocked">
              Blocked ({statusCounts.blocked || 0})
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Microsites Grid */}
      {filteredMicrosites.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Globe className="w-16 h-16 text-gray-300 mb-4" />
            <h3 className="text-xl font-semibold mb-2">
              {statusFilter !== "all"
                ? `No ${statusFilter} microsites`
                : "No microsites yet"}
            </h3>
            <p className="text-gray-500 text-center mb-6 max-w-md">
              {statusFilter !== "all"
                ? `There are no microsites with "${statusFilter}" status.`
                : "Create your first AI-generated microsite from a workspace. Choose from multiple templates and customize with dual edit modes."}
            </p>
            {statusFilter === "all" && (
              <Button onClick={() => navigate("/workspaces")}>
                <Plus className="w-4 h-4 mr-2" />
                Go to Workspaces
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredMicrosites.map((microsite) => (
            <Card key={microsite.id} className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="text-xl mb-2">{microsite.title}</CardTitle>
                    {microsite.description && (
                      <CardDescription className="line-clamp-2">
                        {microsite.description}
                      </CardDescription>
                    )}
                  </div>
                  <StatusBadge status={microsite.status} />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{microsite.theme || "default"}</Badge>
                  {microsite.published_version && (
                    <Badge variant="outline">v{microsite.published_version}</Badge>
                  )}
                </div>

                <div className="text-sm text-gray-500">
                  <p>Created {formatRelativeTime(microsite.created)}</p>
                  <p>Updated {formatRelativeTime(microsite.updated)}</p>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => navigate(`/microsites/${microsite.id}`)}
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    View
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => navigate(`/microsites/${microsite.id}/edit`)}
                  >
                    <Pencil className="w-4 h-4 mr-2" />
                    Edit
                  </Button>
                  {microsite.status === "published" && microsite.access_url && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => window.open(`${window.location.origin}${microsite.access_url}`, "_blank")}
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(microsite.id)}
                  >
                    <Trash2 className="w-4 h-4 text-red-600" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}
