"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useNotebooks, useCreateNotebook, useUpdateNotebook, useDuplicateNotebook, useDraftSessions } from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Plus, Search, Archive, BookOpen, Star, Sparkles, ChevronDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { NotebookList } from "@/components/workspaces/notebook-list";
import { NotebookForm } from "@/components/workspaces/notebook-form";
import { DraftWorkspaceSessions } from "@/components/workspaces/DraftWorkspaceSessions";
import { TemplateCard } from "@/components/templates/TemplateCard";
import { TemplateCreator } from "@/components/templates/TemplateCreator";
import { TemplateExecutionDialog } from "@/components/templates/TemplateExecutionDialog";
import { templatesApi } from "@/lib/api/templates";
import type { Notebook, NotebookCreate } from "@/lib/types";

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

export function WorkspacesPageClient() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [showBookmarkedOnly, setShowBookmarkedOnly] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingNotebook, setEditingNotebook] = useState<Notebook | undefined>();
  const [activeTab, setActiveTab] = useState("workspaces");

  // Template states
  const [templateSearch, setTemplateSearch] = useState("");
  const [templateCategory, setTemplateCategory] = useState("all");
  const [templateView, setTemplateView] = useState<"my" | "public">("my");
  const [isCreateTemplateDialogOpen, setIsCreateTemplateDialogOpen] = useState(false);
  const [executeDialogOpen, setExecuteDialogOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<any>(null);
  const [executingTemplateId, setExecutingTemplateId] = useState<string | null>(null);

  const { data: notebooks = [], isLoading } = useNotebooks({ archived: showArchived });
  const { data: draftSessions = [], isLoading: isLoadingDrafts } = useDraftSessions();
  const createMutation = useCreateNotebook();
  const updateMutation = useUpdateNotebook();
  const duplicateMutation = useDuplicateNotebook();

  // Fetch templates
  const { data: userTemplates, isLoading: isLoadingUserTemplates } = useQuery({
    queryKey: ["templates", "user", templateCategory !== "all" ? templateCategory : undefined],
    queryFn: () =>
      templatesApi.list({
        category: templateCategory !== "all" ? templateCategory : undefined,
        limit: 100,
      }),
    enabled: activeTab === "templates" && templateView === "my",
  });

  const { data: publicTemplates, isLoading: isLoadingPublicTemplates } = useQuery({
    queryKey: ["templates", "public", templateCategory !== "all" ? templateCategory : undefined],
    queryFn: () =>
      templatesApi.listPublic({
        category: templateCategory !== "all" ? templateCategory : undefined,
        limit: 100,
      }),
    enabled: activeTab === "templates" && templateView === "public",
  });

  const templates = templateView === "public" ? publicTemplates : userTemplates;
  const isLoadingTemplates = templateView === "public" ? isLoadingPublicTemplates : isLoadingUserTemplates;

  const filteredNotebooks = notebooks.filter((nb) => {
    const query = searchQuery.toLowerCase();
    const matchesName = nb.name.toLowerCase().includes(query);
    const matchesDescription = nb.description?.toLowerCase().includes(query);
    const matchesTags = nb.tags?.some((tag) => tag.toLowerCase().includes(query));
    const matchesSearch = matchesName || matchesDescription || matchesTags;
    const matchesBookmark = !showBookmarkedOnly || nb.is_bookmarked;
    return matchesSearch && matchesBookmark;
  });

  const filteredTemplates = templates?.filter((template) => {
    if (!templateSearch) return true;
    const searchLower = templateSearch.toLowerCase();
    return (
      template.name.toLowerCase().includes(searchLower) ||
      template.description?.toLowerCase().includes(searchLower) ||
      template.tags.some((tag) => tag.toLowerCase().includes(searchLower))
    );
  });

  const handleCreate = async (data: NotebookCreate) => {
    try {
      await createMutation.mutateAsync(data);
      toast.success("Workspace created successfully");
      setShowForm(false);
    } catch (error) {
      toast.error("Failed to create workspace");
      throw error;
    }
  };

  const handleUpdate = async (data: NotebookCreate) => {
    if (!editingNotebook) return;

    try {
      await updateMutation.mutateAsync({ id: editingNotebook.id, data });
      toast.success("Workspace updated successfully");
      setEditingNotebook(undefined);
    } catch (error) {
      toast.error("Failed to update workspace");
      throw error;
    }
  };

  const handleEdit = (notebook: Notebook) => {
    setEditingNotebook(notebook);
  };

  const handleDuplicate = async (notebook: Notebook) => {
    try {
      await duplicateMutation.mutateAsync(notebook.id);
      toast.success(`Workspace "${notebook.name}" duplicated successfully`);
    } catch (error) {
      toast.error("Failed to duplicate workspace");
    }
  };

  const handleInstantiateTemplate = async (templateId: string) => {
    const template = await templatesApi.get(templateId);
    setSelectedTemplate(template);
    setExecutingTemplateId(templateId);
    setExecuteDialogOpen(true);
  };

  const handleExecuteDialogClose = (open: boolean) => {
    setExecuteDialogOpen(open);
    if (!open) {
      setTimeout(() => {
        setExecutingTemplateId(null);
      }, 3000);
    }
  };

  const handleScheduleTemplate = (templateId: string) => {
    toast.info("Schedule functionality coming soon!");
  };

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between animate-fade-in-up">
          <div>
            <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
              Workspaces
            </h1>
            <p className="text-muted-foreground mt-2 text-base">
              Organize your research with workspaces and reusable templates
            </p>
          </div>
          {activeTab === "workspaces" ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button className="transition-all hover:scale-105 hover:shadow-lg">
                  <Plus className="w-4 h-4 mr-2" />
                  New Workspace
                  <ChevronDown className="w-4 h-4 ml-2" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-[280px] animate-fade-in">
                <DropdownMenuItem
                  onClick={() => router.push('/workspaces/create/guided')}
                  className="transition-all hover:scale-[1.02]"
                >
                  <Sparkles className="w-4 h-4 mr-2 text-primary" />
                  <div className="flex flex-col items-start">
                    <span className="font-medium">Guided Setup (AI-Powered)</span>
                    <span className="text-xs text-muted-foreground">
                      Let AI help you set up your workspace
                    </span>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => setShowForm(true)}
                  className="transition-all hover:scale-[1.02]"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  <div className="flex flex-col items-start">
                    <span className="font-medium">Quick Setup</span>
                    <span className="text-xs text-muted-foreground">
                      Create workspace manually
                    </span>
                  </div>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button onClick={() => setIsCreateTemplateDialogOpen(true)} className="transition-all hover:scale-105 hover:shadow-lg">
              <Plus className="w-4 h-4 mr-2" />
              Create Template
            </Button>
          )}
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="workspaces">Workspaces</TabsTrigger>
            <TabsTrigger value="templates">Templates</TabsTrigger>
          </TabsList>

          {/* Workspaces Tab */}
          <TabsContent value="workspaces" className="space-y-6 mt-6">
            {/* Filters */}
            <Card className="p-4 shadow-sm border-2 animate-fade-in-up animation-delay-200 hover:shadow-lg transition-shadow">
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    placeholder="Search by name, description, or tags..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-11 h-11 text-base w-full"
                  />
                </div>
                <div className="flex gap-3 shrink-0">
                  <Button
                    variant={showArchived ? "default" : "outline"}
                    size="lg"
                    onClick={() => setShowArchived(!showArchived)}
                    className="h-11 flex-1 sm:flex-none transition-all hover:scale-105"
                  >
                    <Archive className="w-4 h-4 mr-2" />
                    <span className="hidden sm:inline">{showArchived ? "Hide Archived" : "Show Archived"}</span>
                    <span className="sm:hidden">Archived</span>
                  </Button>
                  <Button
                    variant={showBookmarkedOnly ? "default" : "outline"}
                    size="lg"
                    onClick={() => setShowBookmarkedOnly(!showBookmarkedOnly)}
                    className="h-11 flex-1 sm:flex-none transition-all hover:scale-105"
                  >
                    <Star className={`w-4 h-4 mr-2 ${showBookmarkedOnly ? "fill-current" : ""}`} />
                    <span className="hidden sm:inline">All</span>
                    <span className="sm:hidden">All</span>
                  </Button>
                </div>
              </div>
            </Card>

            {/* Draft Workspace Sessions */}
            <DraftWorkspaceSessions sessions={draftSessions} isLoading={isLoadingDrafts} />

            {/* Notebooks Grid */}
            {isLoading || filteredNotebooks.length > 0 ? (
              <NotebookList
                notebooks={filteredNotebooks}
                isLoading={isLoading}
                onEdit={handleEdit}
                onDuplicate={handleDuplicate}
              />
            ) : (
              <Card className="shadow-lg border-2">
                <CardContent className="flex flex-col items-center justify-center py-24">
                  <div className="rounded-full bg-primary/10 p-6 mb-6">
                    <BookOpen className="w-16 h-16 text-primary" />
                  </div>
                  <h3 className="text-2xl font-bold mb-2">
                    {searchQuery ? "No workspaces found" : "No workspaces yet"}
                  </h3>
                  <p className="text-muted-foreground text-center mb-8 max-w-md text-base">
                    {searchQuery
                      ? "No workspaces match your search. Try a different query."
                      : "Create your first workspace to start organizing your research materials."}
                  </p>
                  {!searchQuery && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="lg" className="shadow-lg">
                          <Plus className="w-5 h-5 mr-2" />
                          Create Workspace
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="center" className="w-[300px] p-2">
                        <DropdownMenuItem
                          onClick={() => router.push('/workspaces/create/guided')}
                          className="p-4 cursor-pointer"
                        >
                          <Sparkles className="w-5 h-5 mr-3 text-primary flex-shrink-0" />
                          <div className="flex flex-col items-start">
                            <span className="font-semibold text-base">Guided Setup (AI-Powered)</span>
                            <span className="text-sm text-muted-foreground mt-0.5">
                              Let AI help you set up your workspace
                            </span>
                          </div>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator className="my-2" />
                        <DropdownMenuItem
                          onClick={() => setShowForm(true)}
                          className="p-4 cursor-pointer"
                        >
                          <Plus className="w-5 h-5 mr-3 flex-shrink-0" />
                          <div className="flex flex-col items-start">
                            <span className="font-semibold text-base">Quick Setup</span>
                            <span className="text-sm text-muted-foreground mt-0.5">
                              Create workspace manually
                            </span>
                          </div>
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Templates Tab */}
          <TabsContent value="templates" className="space-y-6 mt-6">
            {/* Template Filters */}
            <Card className="p-4 shadow-sm border-2">
              <div className="flex flex-col gap-4">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      placeholder="Search templates by name, description, or tags..."
                      value={templateSearch}
                      onChange={(e) => setTemplateSearch(e.target.value)}
                      className="pl-11 h-11 text-base w-full"
                    />
                  </div>
                  <Select value={templateCategory} onValueChange={setTemplateCategory}>
                    <SelectTrigger className="w-full sm:w-[200px] h-11">
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
                <Tabs value={templateView} onValueChange={(v) => setTemplateView(v as "my" | "public")}>
                  <TabsList>
                    <TabsTrigger value="my">My Templates</TabsTrigger>
                    <TabsTrigger value="public">Public Templates</TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
            </Card>

            {/* Templates Grid */}
            {isLoadingTemplates ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : filteredTemplates && filteredTemplates.length > 0 ? (
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {filteredTemplates.map((template) => (
                  <TemplateCard
                    key={template.id}
                    template={template}
                    onInstantiate={handleInstantiateTemplate}
                    onSchedule={handleScheduleTemplate}
                    isExecuting={executingTemplateId === template.id}
                  />
                ))}
              </div>
            ) : (
              <Card className="shadow-lg border-2">
                <CardContent className="flex flex-col items-center justify-center py-24">
                  <div className="rounded-full bg-primary/10 p-6 mb-6">
                    <BookOpen className="w-16 h-16 text-primary" />
                  </div>
                  <h3 className="text-2xl font-bold mb-2">
                    {templateSearch ? "No templates found" : "No templates yet"}
                  </h3>
                  <p className="text-muted-foreground text-center mb-8 max-w-md text-base">
                    {templateSearch
                      ? "No templates match your search. Try a different query."
                      : templateView === "my"
                      ? "Create your first template to reuse workspace configurations."
                      : "No public templates available in this category."}
                  </p>
                  {!templateSearch && templateView === "my" && (
                    <Button size="lg" className="shadow-lg" onClick={() => setIsCreateTemplateDialogOpen(true)}>
                      <Plus className="w-5 h-5 mr-2" />
                      Create Template
                    </Button>
                  )}
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>

        {/* Create Form */}
        <NotebookForm
          open={showForm}
          onOpenChange={setShowForm}
          onSubmit={handleCreate}
          isLoading={createMutation.isPending}
        />

        {/* Edit Form */}
        {editingNotebook && (
          <NotebookForm
            notebook={editingNotebook}
            open={!!editingNotebook}
            onOpenChange={(open) => !open && setEditingNotebook(undefined)}
            onSubmit={handleUpdate}
            isLoading={updateMutation.isPending}
          />
        )}

        {/* Template Creator Dialog */}
        <TemplateCreator
          open={isCreateTemplateDialogOpen}
          onOpenChange={setIsCreateTemplateDialogOpen}
        />

        {/* Template Execution Dialog */}
        {selectedTemplate && (
          <TemplateExecutionDialog
            open={executeDialogOpen}
            onOpenChange={handleExecuteDialogClose}
            templateId={selectedTemplate.id}
            templateName={selectedTemplate.name}
            parameters={selectedTemplate.parameters || []}
          />
        )}
      </div>
    </div>
  );
}
