"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useNotebook, useNotebookSources, useNotebookChatSessions, useCreateSource, useCreateChatSession, useUploadFile } from "@/lib/hooks/use-api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { ArrowLeft, FileText, MessageSquare, Plus, Link as LinkIcon, Upload, Youtube, Globe, Share2, MessageCircle, Sparkles, Database, Code, Network, Search, Filter, X, RefreshCw, RotateCcw, CheckCircle, ChevronRight, ChevronDown, FolderOpen, Folder as FolderIcon, Presentation, ChevronLeft } from "lucide-react";
import Link from "next/link";
import { formatRelativeTime } from "@/lib/utils";
import { toast } from "sonner";
import type { SourceCreate } from "@/lib/types";
import { MicrositeCreateDialog } from "@/components/microsites/microsite-create-dialog";
import { NoteEditor } from "@/components/notes/note-editor";
import { NoteCard } from "@/components/notes/note-card";
import { PresentationCard } from "@/components/notes/presentation-card";
import { DocumentUploadDialog } from "@/components/workspaces/DocumentUploadDialog";
import { DocumentCard } from "@/components/workspaces/DocumentCard";
import { FileUploadForm } from "@/components/sources/file-upload-form";
import { WorkspaceTasks } from "@/components/workspaces/workspace-tasks";
import { WorkspaceTagManager } from "@/components/workspaces/workspace-tag-manager";
import { GeneratePlanButton } from "@/components/workspaces/generate-plan-button";
import { regenerateWorkspaceTasks, finalizeWorkspace } from "@/lib/api/workspace-tasks";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { apiClient } from "@/lib/api/client";

export default function NotebookDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const notebookId = params.id as string;
  const queryClient = useQueryClient();
  const { data: notebook, isLoading, error } = useNotebook(notebookId);
  const { data: sources = [], refetch: refetchSources } = useNotebookSources(notebookId);
  const { data: chatSessions = [] } = useNotebookChatSessions(notebookId);
  const createSourceMutation = useCreateSource();
  const createChatSessionMutation = useCreateChatSession();
  const uploadFileMutation = useUploadFile();

  // Check if workspace has an AI-generated plan (from guided workspace creation)
  const { data: workspacePlan } = useQuery({
    queryKey: ["workspace-plan", notebookId],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get(`/workspaces/${notebookId}/plan`);
        return data;
      } catch (error) {
        return null;
      }
    },
    enabled: !!notebookId,
  });

  // Check if workspace has tasks
  const { data: workspaceTasks } = useQuery({
    queryKey: ["workspace-tasks", notebookId],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get(`/workspaces/${notebookId}/tasks`);
        return data;
      } catch (error) {
        return [];
      }
    },
    enabled: !!notebookId,
  });

  // Workspace is AI-guided if it has a plan in the workspace_plans table
  const hasPlan = !!workspacePlan;

  const [showSourceDialog, setShowSourceDialog] = useState(false);
  const [showLinkSourceDialog, setShowLinkSourceDialog] = useState(false);
  const [showMicrositeDialog, setShowMicrositeDialog] = useState(false);
  const [showNoteDialog, setShowNoteDialog] = useState(false);
  const [sourceType, setSourceType] = useState<string>("text");
  const [notes, setNotes] = useState<any[]>([]);
  const [folders, setFolders] = useState<any[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [selectedNote, setSelectedNote] = useState<any | null>(null);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [sourceSearchQuery, setSourceSearchQuery] = useState("");
  const [sourceTypeFilter, setSourceTypeFilter] = useState<string>("all");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [tasksRefreshKey, setTasksRefreshKey] = useState(0);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Pagination states
  const [sourcesPage, setSourcesPage] = useState(1);
  const [chatSessionsPage, setChatSessionsPage] = useState(1);
  const [documentsPage, setDocumentsPage] = useState(1);
  const ITEMS_PER_PAGE = 5;

  // Source form states
  const [textContent, setTextContent] = useState("");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");

  // Fetch all sources with notebook information
  const { data: allSources = [], isLoading: sourcesLoading } = useQuery({
    queryKey: ["sources"],
    queryFn: async () => {
      const { data } = await apiClient.get("/sources");
      return data;
    },
    enabled: showLinkSourceDialog,
  });

  // Get source IDs already in this notebook
  const existingSourceIds = sources.map((s: any) => s.id);

  // Show all sources, but indicate which are already in this notebook
  const availableSources = allSources;

  // Filter sources by search query and type
  const filteredSources = availableSources.filter((source: any) => {
    const matchesSearch = !sourceSearchQuery ||
      source.title?.toLowerCase().includes(sourceSearchQuery.toLowerCase()) ||
      source.source_type?.toLowerCase().includes(sourceSearchQuery.toLowerCase());

    const matchesType = sourceTypeFilter === "all" || source.source_type === sourceTypeFilter;

    return matchesSearch && matchesType;
  });

  // Get unique source types for filter
  const sourceTypes = Array.from(new Set(availableSources.map((s: any) => s.source_type)));

  // Count sources by category
  const typeCounts: any = (sourceTypes as any).reduce((acc: any, type: string) => {
    acc[type] = availableSources.filter((s: any) => s.source_type === type).length;
    return acc;
  }, {} as any);

  const categoryCount: any = {
    all: availableSources.length,
    ...typeCounts,
  };

  // Pagination logic
  const paginateItems = (items: any[], page: number) => {
    const startIndex = (page - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    return items.slice(startIndex, endIndex);
  };

  const getTotalPages = (totalItems: number) => {
    return Math.ceil(totalItems / ITEMS_PER_PAGE);
  };

  // Paginated data
  const paginatedSources = paginateItems(sources, sourcesPage);
  const paginatedChatSessions = paginateItems(chatSessions, chatSessionsPage);
  const paginatedNotes = paginateItems(notes, documentsPage);

  const sourcesTotalPages = getTotalPages(sources.length);
  const chatSessionsTotalPages = getTotalPages(chatSessions.length);
  const documentsTotalPages = getTotalPages(notes.length);

  // Fetch notes
  useEffect(() => {
    if (notebookId) {
      fetchNotes();
    }
  }, [notebookId]);

  // Auto-refresh notes and tasks every 10 seconds if workspace is AI-guided (has a plan)
  // Only refresh when there are pending or in-progress tasks
  useEffect(() => {
    if (!hasPlan) return; // Only for AI-guided workspaces (with a plan)

    const checkAndRefresh = async () => {
      try {
        // Check if there are active tasks
        const { data: progress } = await apiClient.get(`/workspaces/${notebookId}/progress`);
        const hasActiveTasks = progress.in_progress_tasks > 0 || progress.pending_tasks > 0;

        if (hasActiveTasks) {
          // Start polling if not already running
          if (!pollingIntervalRef.current) {
            console.log('Starting auto-refresh polling - active tasks detected');
            pollingIntervalRef.current = setInterval(() => {
              fetchNotes();
              setTasksRefreshKey(prev => prev + 1);
              // Also invalidate notebook query to update note_count
              queryClient.invalidateQueries({ queryKey: ["notebook", notebookId] });
            }, 5000); // Refresh every 5 seconds (changed from 10)
          }
        } else {
          // Stop polling when no active tasks, but do one final refresh
          if (pollingIntervalRef.current) {
            console.log('Stopping auto-refresh polling - no active tasks');
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
            // Final refresh to catch any notes created at the very end
            setTimeout(() => {
              fetchNotes();
              setTasksRefreshKey(prev => prev + 1);
              queryClient.invalidateQueries({ queryKey: ["notebook", notebookId] });
            }, 2000);
          }
        }
      } catch (error) {
        console.error('Failed to check task progress:', error);
      }
    };

    // Initial check
    checkAndRefresh();

    // Re-check every 10 seconds to see if we should start/stop polling (changed from 15)
    const checkInterval = setInterval(checkAndRefresh, 10000);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      clearInterval(checkInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasPlan, notebookId]);

  const fetchNotes = async () => {
    try {
      // Fetch from new documents API that includes both notes and presentations
      const { data } = await apiClient.get(`/documents/workspace/${notebookId}`);

      // The API returns { documents: [], total: number, has_more: boolean }
      // Filter to separate notes and presentations
      const allDocuments = data.documents || [];

      // For now, keep notes in the notes state for existing note functionality
      // Presentations will be shown alongside notes
      setNotes(allDocuments);
    } catch (error) {
      console.error("Failed to fetch documents:", error);
      // Fallback to old API if new one fails
      try {
        const { data } = await apiClient.get(`/notes?notebook_id=${notebookId}`);
        setNotes(data);
      } catch (fallbackError) {
        console.error("Fallback to notes API also failed:", fallbackError);
      }
    }
  };

  const fetchFolders = async () => {
    try {
      const { data } = await apiClient.get(`/folders?notebook_id=${notebookId}`);
      setFolders(data);

      // Auto-expand "Template Executions" folders
      const templateFolders = data.filter((f: any) => f.name === "Template Executions");
      if (templateFolders.length > 0) {
        setExpandedFolders(new Set(templateFolders.map((f: any) => f.id)));
      }
    } catch (error) {
      console.error("Failed to fetch folders:", error);
    }
  };

  useEffect(() => {
    if (notebookId) {
      fetchNotes();
      fetchFolders();
    }
  }, [notebookId]);

  // Auto-select note from query parameter
  useEffect(() => {
    const noteId = searchParams.get("noteId");
    if (noteId && notes.length > 0) {
      const note = notes.find((n) => n.id === noteId);
      if (note) {
        setSelectedNote(note);

        // Auto-expand parent folders to make note visible
        if (note.folder_id) {
          const expandFoldersRecursively = (folderId: string) => {
            const folder = folders.find((f) => f.id === folderId);
            if (folder) {
              setExpandedFolders((prev) => new Set([...prev, folderId]));
              if (folder.parent_id) {
                expandFoldersRecursively(folder.parent_id);
              }
            }
          };
          expandFoldersRecursively(note.folder_id);
        }
      }
    }
  }, [searchParams, notes, folders]);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        fetchNotes(),
        queryClient.invalidateQueries({ queryKey: ["notebook", notebookId] }),
        queryClient.invalidateQueries({ queryKey: ["notebook-sources", notebookId] }),
      ]);
      setTasksRefreshKey(prev => prev + 1); // Trigger tasks refresh
      toast.success("Workspace refreshed");
    } catch (error) {
      toast.error("Failed to refresh workspace");
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleRegenerateTasks = async () => {
    setIsRegenerating(true);
    try {
      const result = await regenerateWorkspaceTasks(notebookId);
      toast.success(
        `Tasks regenerated successfully! Reset ${result.tasks_reset} tasks and deleted ${result.notes_deleted} notes.`
      );

      // Refresh everything
      await Promise.all([
        fetchNotes(),
        queryClient.invalidateQueries({ queryKey: ["notebook", notebookId] }),
        queryClient.invalidateQueries({ queryKey: ["notebook-sources", notebookId] }),
      ]);
      setTasksRefreshKey(prev => prev + 1);
    } catch (error: any) {
      console.error("Failed to regenerate tasks:", error);
      toast.error(error.response?.data?.detail || "Failed to regenerate tasks");
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleFinalizeWorkspace = async () => {
    setIsFinalizing(true);
    try {
      const result = await finalizeWorkspace(notebookId);
      toast.success(
        `Workspace finalized! Generated summary for ${result.tasks_completed} completed tasks.`
      );

      // Refresh everything to show the new summary note
      await Promise.all([
        fetchNotes(),
        queryClient.invalidateQueries({ queryKey: ["notebook", notebookId] }),
        queryClient.invalidateQueries({ queryKey: ["notebook-sources", notebookId] }),
      ]);
      setTasksRefreshKey(prev => prev + 1);
    } catch (error: any) {
      console.error("Failed to finalize workspace:", error);
      toast.error(error.response?.data?.detail || "Failed to finalize workspace");
    } finally {
      setIsFinalizing(false);
    }
  };

  const handleEditNote = (note: any) => {
    setSelectedNote(note);
    setShowNoteDialog(true);
  };

  const handleDeleteNote = async (noteId: string) => {
    try {
      await apiClient.delete(`/notes/${noteId}`);
      toast.success("Note deleted");
      fetchNotes();
    } catch (error) {
      toast.error("Failed to delete note");
    }
  };

  const handleDeleteDocument = async (documentId: string) => {
    try {
      await apiClient.delete(`/documents/${documentId}`);
      toast.success("Document deleted");
      fetchNotes(); // This will refresh all documents
    } catch (error) {
      toast.error("Failed to delete document");
    }
  };

  const handleNoteSaved = () => {
    fetchNotes();
    setSelectedNote(null);
  };

  const handleNoteClick = (noteId: string) => {
    const note = notes.find((n) => n.id === noteId);
    if (note) {
      handleEditNote(note);
    }
  };

  const handleCreateSource = async () => {
    try {
      let sourceData: SourceCreate;

      if (sourceType === "text") {
        if (!textContent.trim()) {
          toast.error("Please enter some text");
          return;
        }
        sourceData = {
          source_type: "text",
          content: textContent,
          title: title || "Text Source",
          notebook_id: notebookId,
        };
      } else if (sourceType === "url") {
        if (!url.trim()) {
          toast.error("Please enter a URL");
          return;
        }
        sourceData = {
          source_type: "url",
          url: url,
          title: title || url,
          notebook_id: notebookId,
        };
      } else if (sourceType === "youtube") {
        if (!url.trim()) {
          toast.error("Please enter a YouTube URL");
          return;
        }
        sourceData = {
          source_type: "youtube",
          url: url,
          title: title || url,
          notebook_id: notebookId,
        };
      } else {
        toast.error("Source type not yet implemented");
        return;
      }

      console.log("Creating source with data:", sourceData);
      await createSourceMutation.mutateAsync(sourceData);
      toast.success("Source added successfully");
      setShowSourceDialog(false);
      setTextContent("");
      setUrl("");
      setTitle("");
      refetchSources();
    } catch (error: any) {
      toast.error(error.message || "Failed to add source");
    }
  };

  const handleFileUpload = async (data: { file: File; title?: string }) => {
    try {
      await uploadFileMutation.mutateAsync({
        ...data,
        notebookId,
      });
      toast.success("File uploaded successfully");
      setShowSourceDialog(false);
      refetchSources();
    } catch (error: any) {
      toast.error(error.message || "Failed to upload file");
    }
  };

  const handleStartChat = async () => {
    try {
      const session = await createChatSessionMutation.mutateAsync({
        title: `Chat with ${notebook?.name || "Workspace"}`,
        notebook_id: notebookId,
      });

      toast.success("Chat session created");
      router.push(`/chat/${session.id}`);
    } catch (error: any) {
      toast.error(error.message || "Failed to create chat session");
    }
  };

  const handleLinkSources = async () => {
    if (selectedSourceIds.length === 0) {
      toast.error("Please select at least one source");
      return;
    }

    try {
      // Link each selected source to the notebook
      await Promise.all(
        selectedSourceIds.map(sourceId =>
          apiClient.post(`/workspaces/${notebookId}/sources/${sourceId}`)
        )
      );

      toast.success(`Linked ${selectedSourceIds.length} source(s) to workspace`);
      setShowLinkSourceDialog(false);
      setSelectedSourceIds([]);
      setSourceSearchQuery("");
      setSourceTypeFilter("all");
      refetchSources();
      queryClient.invalidateQueries({ queryKey: ["notebook", notebookId] });
    } catch (error: any) {
      toast.error(error.message || "Failed to link sources");
    }
  };

  const toggleSourceSelection = (sourceId: string) => {
    setSelectedSourceIds(prev =>
      prev.includes(sourceId)
        ? prev.filter(id => id !== sourceId)
        : [...prev, sourceId]
    );
  };


  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error || !notebook) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <h3 className="text-lg font-semibold mb-2">Workspace not found</h3>
          <p className="text-gray-500 mb-4">
            The workspace you're looking for doesn't exist or has been deleted.
          </p>
          <Link href="/workspaces">
            <Button>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Workspaces
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-4 max-w-7xl mx-auto px-4 md:px-6 lg:px-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 pb-3 border-b">
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <Link href="/workspaces">
            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
              <ArrowLeft className="w-3.5 h-3.5" />
            </Button>
          </Link>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight truncate">
              {notebook.name || "Untitled Workspace"}
            </h1>
            {notebook.description && (
              <p className="text-sm text-muted-foreground mt-0.5 line-clamp-1">
                {notebook.description}
              </p>
            )}
            <div className="mt-2">
              <WorkspaceTagManager
                workspaceId={notebookId}
                tags={notebook.tags || []}
              />
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2 shrink-0">
          {/* AI Workspace Controls */}
          {hasPlan && (
            <div className="flex items-center gap-1.5 pr-2.5 mr-1 border-r">
              <Button
                variant="outline"
                size="sm"
                onClick={handleManualRefresh}
                disabled={isRefreshing}
                className="gap-1.5 h-8 text-xs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">{isRefreshing ? 'Refreshing' : 'Refresh'}</span>
              </Button>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isRegenerating}
                    className="gap-1.5 h-8 text-xs"
                  >
                    <RotateCcw className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
                    <span className="hidden sm:inline">{isRegenerating ? 'Regenerating' : 'Regenerate'}</span>
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Regenerate All Tasks?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will reset all tasks to pending status and delete all task-generated notes (including the completion summary).
                      The tasks will execute again from the beginning.
                      <br /><br />
                      <strong>This action cannot be undone.</strong>
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={handleRegenerateTasks}>
                      Regenerate Tasks
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="default"
                    size="sm"
                    disabled={isFinalizing}
                    className="gap-1.5 h-8 text-xs bg-green-600 hover:bg-green-700"
                  >
                    <CheckCircle className={`w-3.5 h-3.5 ${isFinalizing ? 'animate-spin' : ''}`} />
                    <span className="hidden sm:inline">{isFinalizing ? 'Generating...' : 'Finalize'}</span>
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Generate Final Summary?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will mark the workspace as completed and generate an AI-powered consolidated summary of all task results.
                      <br /><br />
                      This process analyzes all completed tasks and creates a comprehensive final deliverable note.
                      <br /><br />
                      <strong>Note:</strong> This may take 30-60 seconds depending on the number of tasks.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={handleFinalizeWorkspace}>
                      Generate Summary
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          )}

          {/* Generate Plan Button - Show only for workspaces without plans */}
          {!hasPlan && (
            <GeneratePlanButton
              workspaceId={notebookId}
              workspaceName={notebook.name || "Untitled Workspace"}
              variant="outline"
              size="sm"
              className="h-8 text-xs"
            />
          )}

          {/* Secondary Actions */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/workspaces/${notebookId}/graph`)}
            className="gap-1.5 h-8 text-xs"
          >
            <Network className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Graph</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowMicrositeDialog(true)}
            className="gap-1.5 h-8 text-xs"
          >
            <Share2 className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Microsite</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/presentations/new?notebook_id=${notebookId}`)}
            className="gap-1.5 h-8 text-xs"
          >
            <Presentation className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Presentation</span>
          </Button>

          {/* Primary Action - Last */}
          <Button onClick={handleStartChat} size="sm" className="gap-1.5 h-8 text-xs shadow-sm">
            <MessageCircle className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Start Chat</span>
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card className="shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1.5 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Sources</CardTitle>
            <FileText className="h-3.5 w-3.5 text-muted-foreground/70" />
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">{notebook.source_count || 0}</div>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Total sources added
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1.5 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Documents</CardTitle>
            <FileText className="h-3.5 w-3.5 text-muted-foreground/70" />
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">{notebook.note_count || 0}</div>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Documents and presentations
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1.5 pt-3">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Chat Sessions</CardTitle>
            <MessageSquare className="h-3.5 w-3.5 text-muted-foreground/70" />
          </CardHeader>
          <CardContent className="pb-3">
            <div className="text-2xl font-bold">{chatSessions.length}</div>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Active conversations
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tasks Section */}
      <WorkspaceTasks workspaceId={notebookId} refreshKey={tasksRefreshKey} />

      {/* Content sections - placeholder for future implementation */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between pb-3 border-b">
          <CardTitle className="text-base font-semibold">Sources</CardTitle>
          <div className="flex gap-1.5">
            <Dialog open={showLinkSourceDialog} onOpenChange={setShowLinkSourceDialog}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline" className="h-8 text-xs">
                  <LinkIcon className="w-3.5 h-3.5 mr-1.5" />
                  Link Existing
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Link Existing Sources</DialogTitle>
                  <p className="text-sm text-muted-foreground">
                    Select sources to add to this workspace
                  </p>
                </DialogHeader>
                <div className="space-y-4">
                  {/* Search and Filter */}
                  <div className="flex items-center gap-3">
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <Input
                        placeholder="Search sources by name or type..."
                        value={sourceSearchQuery}
                        onChange={(e) => setSourceSearchQuery(e.target.value)}
                        className="pl-10 pr-10"
                      />
                      {sourceSearchQuery && (
                        <button
                          onClick={() => setSourceSearchQuery("")}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <Select value={sourceTypeFilter} onValueChange={setSourceTypeFilter}>
                      <SelectTrigger className="w-[180px]">
                        <Filter className="w-4 h-4 mr-2" />
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          All Types ({categoryCount.all})
                        </SelectItem>
                        {(sourceTypes as string[]).map((type: string) => (
                          <SelectItem key={type} value={type}>
                            {type.replace(/_/g, " ")} ({categoryCount[type]})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {sourcesLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                    </div>
                  ) : filteredSources.length === 0 ? (
                    <div className="text-center py-8">
                      <p className="text-muted-foreground">
                        {sourceSearchQuery || sourceTypeFilter !== "all"
                          ? "No sources match your filters. Try adjusting your search or filter."
                          : "No available sources to link. All sources are already in this workspace or create new sources first."}
                      </p>
                      {(sourceSearchQuery || sourceTypeFilter !== "all") && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSourceSearchQuery("");
                            setSourceTypeFilter("all");
                          }}
                          className="mt-4"
                        >
                          Clear Filters
                        </Button>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-[400px] overflow-y-auto">
                      {filteredSources.map((source: any) => {
                        const isAlreadyLinked = existingSourceIds.includes(source.id);
                        return (
                          <div
                            key={source.id}
                            className={`flex items-start gap-3 p-3 border rounded-lg ${
                              isAlreadyLinked
                                ? "bg-gray-50 dark:bg-gray-900 opacity-60"
                                : "hover:bg-gray-50 dark:hover:bg-gray-800"
                            }`}
                          >
                            <Checkbox
                              checked={selectedSourceIds.includes(source.id)}
                              onCheckedChange={() => toggleSourceSelection(source.id)}
                              disabled={isAlreadyLinked}
                              className="mt-1"
                            />
                            <div className="flex items-start gap-3 flex-1 min-w-0">
                              <div className="mt-0.5">
                                {source.source_type === "text" && <FileText className="w-4 h-4 text-gray-500" />}
                                {source.source_type === "url" && <Globe className="w-4 h-4 text-gray-500" />}
                                {source.source_type === "youtube" && <Youtube className="w-4 h-4 text-gray-500" />}
                                {source.source_type === "file" && <Upload className="w-4 h-4 text-gray-500" />}
                                {source.source_type === "hana_table" && <Database className="w-4 h-4 text-blue-500" />}
                                {source.source_type === "api" && <Code className="w-4 h-4 text-purple-500" />}
                              </div>
                              <div className="flex-1 min-w-0 space-y-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <p className="font-medium truncate">{source.title || "Untitled"}</p>
                                  {isAlreadyLinked && (
                                    <Badge className="text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                                      Already linked
                                    </Badge>
                                  )}
                                  {source.chunk_count > 0 && (
                                    <Badge variant="outline" className="text-xs shrink-0">
                                      {source.chunk_count} chunks
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-sm text-gray-500">{source.source_type}</p>
                                {source.notebooks && source.notebooks.length > 0 && (
                                  <div className="flex items-center gap-1 flex-wrap">
                                    <span className="text-xs text-gray-400">In:</span>
                                    {source.notebooks.slice(0, 3).map((notebook: any) => (
                                      <Link
                                        key={notebook.id}
                                        href={`/workspaces/${notebook.id}`}
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <Badge
                                          className="text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-800 cursor-pointer transition-colors border-green-200 dark:border-green-800"
                                        >
                                          {notebook.name || "Untitled"}
                                        </Badge>
                                      </Link>
                                    ))}
                                    {source.notebooks.length > 3 && (
                                      <Badge className="text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 border-green-200 dark:border-green-800">
                                        +{source.notebooks.length - 3} more
                                      </Badge>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  <div className="flex justify-between items-center pt-4 border-t">
                    <p className="text-sm text-muted-foreground">
                      {selectedSourceIds.length} source(s) selected
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={() => {
                          setShowLinkSourceDialog(false);
                          setSelectedSourceIds([]);
                          setSourceSearchQuery("");
                          setSourceTypeFilter("all");
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={handleLinkSources}
                        disabled={selectedSourceIds.length === 0}
                      >
                        <LinkIcon className="w-4 h-4 mr-2" />
                        Link {selectedSourceIds.length > 0 && `(${selectedSourceIds.length})`}
                      </Button>
                    </div>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
            <Dialog open={showSourceDialog} onOpenChange={setShowSourceDialog}>
            <DialogTrigger asChild>
              <Button size="sm" className="h-8 text-xs">
                <Plus className="w-3.5 h-3.5 mr-1.5" />
                Add Source
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
              <DialogHeader className="space-y-3 pb-4">
                <DialogTitle className="text-2xl font-semibold">Add Source</DialogTitle>
                <p className="text-sm text-muted-foreground">
                  Choose a source type and provide the necessary information to add it to your workspace.
                </p>
              </DialogHeader>
              <div className="space-y-6">
                {/* Source Type Selection */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">Source Type</Label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setSourceType("text")}
                      className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all hover:border-primary-400 hover:shadow-md ${
                        sourceType === "text"
                          ? "border-primary-500 bg-primary-50 dark:bg-primary-950 shadow-md"
                          : "border-gray-200 dark:border-gray-700"
                      }`}
                    >
                      <FileText className={`w-5 h-5 mt-0.5 ${sourceType === "text" ? "text-primary-600" : "text-gray-500"}`} />
                      <div className="text-left">
                        <div className={`font-medium ${sourceType === "text" ? "text-primary-700 dark:text-primary-400" : ""}`}>
                          Text
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Paste or type text content directly
                        </div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setSourceType("url")}
                      className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all hover:border-primary-400 hover:shadow-md ${
                        sourceType === "url"
                          ? "border-primary-500 bg-primary-50 dark:bg-primary-950 shadow-md"
                          : "border-gray-200 dark:border-gray-700"
                      }`}
                    >
                      <LinkIcon className={`w-5 h-5 mt-0.5 ${sourceType === "url" ? "text-primary-600" : "text-gray-500"}`} />
                      <div className="text-left">
                        <div className={`font-medium ${sourceType === "url" ? "text-primary-700 dark:text-primary-400" : ""}`}>
                          URL / Web Page
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Import content from any website
                        </div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setSourceType("youtube")}
                      className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all hover:border-primary-400 hover:shadow-md ${
                        sourceType === "youtube"
                          ? "border-primary-500 bg-primary-50 dark:bg-primary-950 shadow-md"
                          : "border-gray-200 dark:border-gray-700"
                      }`}
                    >
                      <Youtube className={`w-5 h-5 mt-0.5 ${sourceType === "youtube" ? "text-primary-600" : "text-gray-500"}`} />
                      <div className="text-left">
                        <div className={`font-medium ${sourceType === "youtube" ? "text-primary-700 dark:text-primary-400" : ""}`}>
                          YouTube Video
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Extract transcript from video
                        </div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setSourceType("file")}
                      className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all hover:border-primary-400 hover:shadow-md ${
                        sourceType === "file"
                          ? "border-primary-500 bg-primary-50 dark:bg-primary-950 shadow-md"
                          : "border-gray-200 dark:border-gray-700"
                      }`}
                    >
                      <Upload className={`w-5 h-5 mt-0.5 ${sourceType === "file" ? "text-primary-600" : "text-gray-500"}`} />
                      <div className="text-left">
                        <div className={`font-medium ${sourceType === "file" ? "text-primary-700 dark:text-primary-400" : ""}`}>
                          File Upload
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Upload documents and files
                        </div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setSourceType("hana_table")}
                      className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all hover:border-primary-400 hover:shadow-md ${
                        sourceType === "hana_table"
                          ? "border-primary-500 bg-primary-50 dark:bg-primary-950 shadow-md"
                          : "border-gray-200 dark:border-gray-700"
                      }`}
                    >
                      <Database className={`w-5 h-5 mt-0.5 ${sourceType === "hana_table" ? "text-primary-600" : "text-gray-500"}`} />
                      <div className="text-left">
                        <div className={`font-medium ${sourceType === "hana_table" ? "text-primary-700 dark:text-primary-400" : ""}`}>
                          HANA Table
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Connect to SAP HANA Cloud tables
                        </div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => setSourceType("api")}
                      className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all hover:border-primary-400 hover:shadow-md ${
                        sourceType === "api"
                          ? "border-primary-500 bg-primary-50 dark:bg-primary-950 shadow-md"
                          : "border-gray-200 dark:border-gray-700"
                      }`}
                    >
                      <Code className={`w-5 h-5 mt-0.5 ${sourceType === "api" ? "text-primary-600" : "text-gray-500"}`} />
                      <div className="text-left">
                        <div className={`font-medium ${sourceType === "api" ? "text-primary-700 dark:text-primary-400" : ""}`}>
                          API Connection
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Connect to REST APIs with authentication
                        </div>
                      </div>
                    </button>
                  </div>
                </div>

                {/* Conditional Content Based on Source Type */}
                {sourceType === "file" && (
                  <FileUploadForm
                    onSubmit={handleFileUpload}
                    isLoading={uploadFileMutation.isPending}
                  />
                )}

                {sourceType === "hana_table" && (
                  <div className="rounded-lg border-2 border-dashed border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950 p-8 text-center">
                    <Database className="w-12 h-12 text-blue-500 mx-auto mb-3" />
                    <p className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-2">
                      HANA Table source requires advanced configuration
                    </p>
                    <p className="text-xs text-muted-foreground mb-4">
                      Connection details, table selection, and column mapping
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => router.push("/sources/new")}
                    >
                      Go to Sources Page
                    </Button>
                  </div>
                )}

                {sourceType === "api" && (
                  <div className="rounded-lg border-2 border-dashed border-purple-300 dark:border-purple-700 bg-purple-50 dark:bg-purple-950 p-8 text-center">
                    <Code className="w-12 h-12 text-purple-500 mx-auto mb-3" />
                    <p className="text-sm font-medium text-purple-700 dark:text-purple-300 mb-2">
                      API Connection requires authentication setup
                    </p>
                    <p className="text-xs text-muted-foreground mb-4">
                      OAuth 2.0, API keys, and endpoint configuration
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => router.push("/sources/new")}
                    >
                      Go to Sources Page
                    </Button>
                  </div>
                )}

                {sourceType !== "file" && sourceType !== "hana_table" && sourceType !== "api" && (
                  <>
                    {/* Title Input */}
                    <div className="space-y-2">
                      <Label htmlFor="title" className="text-sm font-medium">
                        Title <span className="text-muted-foreground font-normal">(optional)</span>
                      </Label>
                      <Input
                        id="title"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="Give this source a descriptive name"
                        className="h-11"
                      />
                      <p className="text-xs text-muted-foreground">
                        A memorable name to help you identify this source later
                      </p>
                    </div>

                    {/* Text Content */}
                    {sourceType === "text" && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="textContent" className="text-sm font-medium">
                            Text Content
                          </Label>
                          {textContent && (
                            <span className="text-xs text-muted-foreground">
                              {textContent.length} characters • ~{Math.ceil(textContent.length / 500)} chunks
                            </span>
                          )}
                        </div>
                        <Textarea
                          id="textContent"
                          value={textContent}
                          onChange={(e) => setTextContent(e.target.value)}
                          placeholder="Enter or paste your text here..."
                          rows={12}
                          className="resize-none font-mono text-sm"
                        />
                        <p className="text-xs text-muted-foreground">
                          Your text will be automatically chunked and embedded for semantic search
                        </p>
                      </div>
                    )}

                    {/* URL Input */}
                    {(sourceType === "url" || sourceType === "youtube") && (
                      <div className="space-y-2">
                        <Label htmlFor="url" className="text-sm font-medium">
                          {sourceType === "youtube" ? "YouTube URL" : "URL"}
                        </Label>
                        <div className="relative">
                          <Input
                            id="url"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder={
                              sourceType === "youtube"
                                ? "https://youtube.com/watch?v=..."
                                : "https://example.com/article"
                            }
                            className="h-11 pr-10"
                          />
                          {sourceType === "youtube" ? (
                            <Youtube className="absolute right-3 top-3 w-5 h-5 text-muted-foreground" />
                          ) : (
                            <Globe className="absolute right-3 top-3 w-5 h-5 text-muted-foreground" />
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {sourceType === "youtube"
                            ? "The video transcript will be extracted and processed"
                            : "The webpage content will be scraped and processed"}
                        </p>
                      </div>
                    )}
                  </>
                )}

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-3 pt-4 border-t">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowSourceDialog(false);
                      setTextContent("");
                      setUrl("");
                      setTitle("");
                    }}
                    className="min-w-[100px]"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateSource}
                    disabled={sourceType === "file" || sourceType === "hana_table" || sourceType === "api"}
                    className="min-w-[120px]"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add Source
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {sources.length === 0 ? (
            <div className="text-center py-6 px-4">
              <p className="text-sm text-muted-foreground">
                No sources yet. Add sources to get started.
              </p>
            </div>
          ) : (
            <>
              <div className="divide-y">
                {paginatedSources.map((source: any) => (
                  <div
                    key={source.id}
                    className="flex items-center justify-between p-3 hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-2.5 flex-1">
                      {source.source_type === "text" && <FileText className="w-3.5 h-3.5 text-muted-foreground" />}
                      {source.source_type === "url" && <Globe className="w-3.5 h-3.5 text-muted-foreground" />}
                      {source.source_type === "youtube" && <Youtube className="w-3.5 h-3.5 text-muted-foreground" />}
                      {source.source_type === "file" && <Upload className="w-3.5 h-3.5 text-muted-foreground" />}
                      {source.source_type === "hana_table" && <Database className="w-3.5 h-3.5 text-blue-500" />}
                      {source.source_type === "api" && <Code className="w-3.5 h-3.5 text-purple-500" />}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <p className="font-medium text-sm truncate">{source.title || "Untitled"}</p>
                          {source.sync_status === "embedding" && (
                            <Badge className="bg-purple-100 text-purple-700 text-[10px] px-1.5 py-0 h-4">
                              Embedding...
                            </Badge>
                          )}
                          {source.sync_status === "completed" && source.chunk_count > 0 && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                              <Sparkles className="w-2.5 h-2.5 mr-0.5" />
                              {source.chunk_count}
                            </Badge>
                          )}
                          {source.sync_status === "error" && (
                            <Badge className="bg-red-100 text-red-700 text-[10px] px-1.5 py-0 h-4">
                              Error
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{source.source_type}</p>
                      </div>
                    </div>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">{formatRelativeTime(source.created)}</Badge>
                  </div>
                ))}
              </div>
              {sourcesTotalPages > 1 && (
                <div className="flex items-center justify-between px-4 py-3 border-t bg-muted/20">
                  <p className="text-xs text-muted-foreground">
                    Showing {(sourcesPage - 1) * ITEMS_PER_PAGE + 1} to {Math.min(sourcesPage * ITEMS_PER_PAGE, sources.length)} of {sources.length} sources
                  </p>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSourcesPage(p => Math.max(1, p - 1))}
                      disabled={sourcesPage === 1}
                      className="h-7 w-7 p-0"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </Button>
                    <span className="text-xs text-muted-foreground mx-2">
                      Page {sourcesPage} of {sourcesTotalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSourcesPage(p => Math.min(sourcesTotalPages, p + 1))}
                      disabled={sourcesPage === sourcesTotalPages}
                      className="h-7 w-7 p-0"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Chat Sessions List */}
      {chatSessions.length > 0 && (
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-3 border-b">
            <CardTitle className="text-base font-semibold">Chat Sessions</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {paginatedChatSessions.map((session: any) => (
                <div
                  key={session.id}
                  className="flex items-center justify-between p-3 hover:bg-muted/50 transition-colors cursor-pointer"
                  onClick={() => router.push(`/chat/${session.id}`)}
                >
                  <div className="flex items-center gap-2.5 flex-1 min-w-0">
                    <MessageSquare className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{session.title || "Untitled Chat"}</p>
                      <p className="text-xs text-muted-foreground">Updated {formatRelativeTime(session.updated)}</p>
                    </div>
                  </div>
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4">{formatRelativeTime(session.created)}</Badge>
                </div>
              ))}
            </div>
            {chatSessionsTotalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t bg-muted/20">
                <p className="text-xs text-muted-foreground">
                  Showing {(chatSessionsPage - 1) * ITEMS_PER_PAGE + 1} to {Math.min(chatSessionsPage * ITEMS_PER_PAGE, chatSessions.length)} of {chatSessions.length} sessions
                </p>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setChatSessionsPage(p => Math.max(1, p - 1))}
                    disabled={chatSessionsPage === 1}
                    className="h-7 w-7 p-0"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </Button>
                  <span className="text-xs text-muted-foreground mx-2">
                    Page {chatSessionsPage} of {chatSessionsTotalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setChatSessionsPage(p => Math.min(chatSessionsTotalPages, p + 1))}
                    disabled={chatSessionsPage === chatSessionsTotalPages}
                    className="h-7 w-7 p-0"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between pb-3 border-b">
          <CardTitle className="text-base font-semibold">Documents</CardTitle>
          <div className="flex items-center gap-1.5">
            <DocumentUploadDialog
              workspaceId={notebookId}
              onUploadComplete={fetchNotes}
            />
            <Button
              size="sm"
              onClick={() => {
                setSelectedNote(null);
                setShowNoteDialog(true);
              }}
              className="h-8 text-xs"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              Add Note
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {notes.length === 0 ? (
            <div className="text-center py-6 px-4">
              <p className="text-sm text-muted-foreground">
                No documents yet. Click "Add Note" to create your first note with rich text formatting!
              </p>
            </div>
          ) : (
            <div>
              {/* Group notes by folders */}
              {(() => {
                // Build folder hierarchy
                const folderMap = new Map(folders.map((f: any) => [f.id, f]));
                const rootFolders = folders.filter((f: any) => !f.parent_id);
                const childFoldersMap = new Map<string, any[]>();
                folders.forEach((f: any) => {
                  if (f.parent_id) {
                    if (!childFoldersMap.has(f.parent_id)) {
                      childFoldersMap.set(f.parent_id, []);
                    }
                    childFoldersMap.get(f.parent_id)!.push(f);
                  }
                });

                // Group notes by folder
                const notesByFolder = new Map<string | null, any[]>();
                paginatedNotes.forEach((note) => {
                  const folderId = note.folder_id || null;
                  if (!notesByFolder.has(folderId)) {
                    notesByFolder.set(folderId, []);
                  }
                  notesByFolder.get(folderId)!.push(note);
                });

                const toggleFolder = (folderId: string) => {
                  setExpandedFolders(prev => {
                    const next = new Set(prev);
                    if (next.has(folderId)) {
                      next.delete(folderId);
                    } else {
                      next.add(folderId);
                    }
                    return next;
                  });
                };

                const renderFolder = (folder: any, level: number = 0): React.ReactElement => {
                  const isExpanded = expandedFolders.has(folder.id);
                  const childFolders = childFoldersMap.get(folder.id) || [];
                  const folderNotes = notesByFolder.get(folder.id) || [];
                  const hasContent = childFolders.length > 0 || folderNotes.length > 0;

                  return (
                    <div key={folder.id} className="border-b last:border-b-0">
                      <div
                        className="flex items-center gap-2 px-4 py-3 hover:bg-accent/50 cursor-pointer"
                        style={{ paddingLeft: `${level * 16 + 16}px` }}
                        onClick={() => toggleFolder(folder.id)}
                      >
                        {hasContent ? (
                          isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )
                        ) : (
                          <div className="h-4 w-4" />
                        )}
                        {isExpanded ? (
                          <FolderOpen className="h-4 w-4 text-blue-500" />
                        ) : (
                          <FolderIcon className="h-4 w-4 text-gray-500" />
                        )}
                        <span className="text-sm font-medium">{folder.name}</span>
                        {folderNotes.length > 0 && (
                          <Badge variant="secondary" className="text-xs ml-auto">
                            {folderNotes.length}
                          </Badge>
                        )}
                      </div>

                      {isExpanded && (
                        <div>
                          {/* Render child folders */}
                          {childFolders.map((child: any) => renderFolder(child, level + 1))}

                          {/* Render notes in this folder */}
                          {folderNotes
                            .sort((a, b) => {
                              const aIsFinal = a.title.includes("🎯 FINAL DELIVERABLE");
                              const bIsFinal = b.title.includes("🎯 FINAL DELIVERABLE");
                              if (aIsFinal && !bIsFinal) return -1;
                              if (!aIsFinal && bIsFinal) return 1;
                              return new Date(b.created || b.created_at).getTime() - new Date(a.created || a.created_at).getTime();
                            })
                            .map((doc) => (
                              <div key={doc.id} style={{ paddingLeft: `${(level + 1) * 16}px` }}>
                                {doc.document_type === 'presentation' ? (
                                  <PresentationCard
                                    document={doc}
                                    onDelete={handleDeleteDocument}
                                  />
                                ) : doc.document_type === 'note' ? (
                                  <NoteCard
                                    note={doc}
                                    onEdit={handleEditNote}
                                    onDelete={handleDeleteNote}
                                    onNoteClick={handleNoteClick}
                                  />
                                ) : (
                                  <DocumentCard
                                    document={doc}
                                    onDelete={handleDeleteDocument}
                                  />
                                )}
                              </div>
                            ))}
                        </div>
                      )}
                    </div>
                  );
                };

                // Render root folders first
                const rendered: React.ReactElement[] = [];

                // 1. Render root folders with their hierarchies
                rootFolders.forEach((folder: any) => {
                  rendered.push(renderFolder(folder, 0));
                });

                // 2. Render ungrouped notes (notes without a folder)
                const ungroupedNotes = notesByFolder.get(null) || [];
                if (ungroupedNotes.length > 0) {
                  rendered.push(
                    <div key="ungrouped">
                      {ungroupedNotes
                        .sort((a, b) => {
                          const aIsFinal = a.title.includes("🎯 FINAL DELIVERABLE");
                          const bIsFinal = b.title.includes("🎯 FINAL DELIVERABLE");
                          if (aIsFinal && !bIsFinal) return -1;
                          if (!aIsFinal && bIsFinal) return 1;
                          return new Date(b.created || b.created_at).getTime() - new Date(a.created || a.created_at).getTime();
                        })
                        .map((doc) => (
                          doc.document_type === 'presentation' ? (
                            <PresentationCard
                              key={doc.id}
                              document={doc}
                              onDelete={handleDeleteDocument}
                            />
                          ) : doc.document_type === 'note' ? (
                            <NoteCard
                              key={doc.id}
                              note={doc}
                              onEdit={handleEditNote}
                              onDelete={handleDeleteNote}
                              onNoteClick={handleNoteClick}
                            />
                          ) : (
                            <DocumentCard
                              key={doc.id}
                              document={doc}
                              onDelete={handleDeleteDocument}
                            />
                          )
                        ))}
                    </div>
                  );
                }

                return rendered;
              })()}
            </div>
          )}
          {notes.length > 0 && documentsTotalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t bg-muted/20">
              <p className="text-xs text-muted-foreground">
                Showing {(documentsPage - 1) * ITEMS_PER_PAGE + 1} to {Math.min(documentsPage * ITEMS_PER_PAGE, notes.length)} of {notes.length} documents
              </p>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDocumentsPage(p => Math.max(1, p - 1))}
                  disabled={documentsPage === 1}
                  className="h-7 w-7 p-0"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </Button>
                <span className="text-xs text-muted-foreground mx-2">
                  Page {documentsPage} of {documentsTotalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDocumentsPage(p => Math.min(documentsTotalPages, p + 1))}
                  disabled={documentsPage === documentsTotalPages}
                  className="h-7 w-7 p-0"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Note Editor Dialog */}
      <NoteEditor
        open={showNoteDialog}
        onOpenChange={(open) => {
          setShowNoteDialog(open);
          if (!open) {
            setSelectedNote(null);
          }
        }}
        notebookId={notebookId}
        note={selectedNote}
        availableNotes={notes}
        onSave={handleNoteSaved}
      />

      {/* Microsite Generator Dialog */}
      <MicrositeCreateDialog
        open={showMicrositeDialog}
        onOpenChange={setShowMicrositeDialog}
        notebookId={notebookId}
        notebookTitle={notebook.name || "Untitled Workspace"}
      />
      </div>
    </div>
  );
}
