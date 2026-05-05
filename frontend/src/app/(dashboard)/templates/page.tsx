"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Plus, Search, Loader2 } from "lucide-react";
import { templatesApi } from "@/lib/api/templates";
import { TemplateCard } from "@/components/templates/TemplateCard";
import { TemplateCreator } from "@/components/templates/TemplateCreator";
import { TemplateExecutionDialog } from "@/components/templates/TemplateExecutionDialog";
import { toast } from "sonner";

const categories = [
  { value: "all", label: "All Categories" },
  { value: "data_pipeline", label: "Data Pipeline" },
  { value: "research", label: "Research" },
  { value: "reporting", label: "Reporting" },
  { value: "monitoring", label: "Monitoring" },
  { value: "analysis", label: "Analysis" },
  { value: "automation", label: "Automation" },
  { value: "other", label: "Other" },
];

export default function TemplatesPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [showPublic, setShowPublic] = useState(false);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [executeDialogOpen, setExecuteDialogOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<any>(null);
  const [executingTemplateId, setExecutingTemplateId] = useState<string | null>(null);

  // Fetch user's templates
  const { data: userTemplates, isLoading: isLoadingUser } = useQuery({
    queryKey: ["templates", "user", category !== "all" ? category : undefined],
    queryFn: () =>
      templatesApi.list({
        category: category !== "all" ? category : undefined,
        limit: 100,
      }),
    enabled: !showPublic,
  });

  // Fetch public templates
  const { data: publicTemplates, isLoading: isLoadingPublic } = useQuery({
    queryKey: ["templates", "public", category !== "all" ? category : undefined],
    queryFn: () =>
      templatesApi.listPublic({
        category: category !== "all" ? category : undefined,
        limit: 100,
      }),
    enabled: showPublic,
  });

  const templates = showPublic ? publicTemplates : userTemplates;
  const isLoading = showPublic ? isLoadingPublic : isLoadingUser;

  // Filter by search
  const filteredTemplates = templates?.filter((template) => {
    if (!search) return true;
    const searchLower = search.toLowerCase();
    return (
      template.name.toLowerCase().includes(searchLower) ||
      template.description?.toLowerCase().includes(searchLower) ||
      template.tags.some((tag) => tag.toLowerCase().includes(searchLower))
    );
  });

  const handleInstantiate = async (templateId: string) => {
    // Load template details first
    const template = await templatesApi.get(templateId);
    setSelectedTemplate(template);
    setExecutingTemplateId(templateId);
    setExecuteDialogOpen(true);
  };

  const handleExecuteDialogClose = (open: boolean) => {
    setExecuteDialogOpen(open);
    if (!open) {
      // Clear executing state after a delay to allow the execution to complete
      setTimeout(() => {
        setExecutingTemplateId(null);
      }, 3000);
    }
  };

  const handleSchedule = (templateId: string) => {
    toast.info("Schedule functionality coming soon!");
    // TODO: Open schedule dialog
  };

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
            Workspace Templates
          </h1>
          <p className="text-muted-foreground mt-2 text-base">
            Reusable workspace configurations for automated execution
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Template
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search templates by name, description, or tags..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {categories.map((cat) => (
              <SelectItem key={cat.value} value={cat.value}>
                {cat.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Tabs */}
      <Tabs value={showPublic ? "public" : "my"} onValueChange={(val) => setShowPublic(val === "public")}>
        <TabsList>
          <TabsTrigger value="my">My Templates</TabsTrigger>
          <TabsTrigger value="public">Public Templates</TabsTrigger>
        </TabsList>

        <TabsContent value="my" className="mt-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredTemplates && filteredTemplates.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredTemplates.map((template) => (
                <TemplateCard
                  key={template.id}
                  template={template}
                  onInstantiate={handleInstantiate}
                  onSchedule={handleSchedule}
                  isExecuting={executingTemplateId === template.id}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-muted-foreground">No templates found.</p>
              <p className="text-sm text-muted-foreground mt-1">
                Create your first template from an existing workspace.
              </p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="public" className="mt-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredTemplates && filteredTemplates.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredTemplates.map((template) => (
                <TemplateCard
                  key={template.id}
                  template={template}
                  onInstantiate={handleInstantiate}
                  onSchedule={handleSchedule}
                  isExecuting={executingTemplateId === template.id}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-muted-foreground">No public templates available.</p>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Create Template Dialog */}
      <TemplateCreator
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
      />

      {/* Execute Template Dialog */}
      {selectedTemplate && (
        <TemplateExecutionDialog
          open={executeDialogOpen}
          onOpenChange={handleExecuteDialogClose}
          templateId={selectedTemplate.id}
          templateName={selectedTemplate.name}
          sourceWorkspaceId={selectedTemplate.source_workspace_id}
          parameters={selectedTemplate.parameters || []}
        />
      )}
      </div>
    </div>
  );
}
