"use client";

import { useState, useEffect } from "react";
import { useChatSessions, useChatSession, useCreateChatSession, useUpdateChatSession, useDeleteChatSession, useNotebooks } from "@/lib/hooks/use-api";
import { chatApi } from "@/lib/api/chat";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChatSessionList } from "@/components/chat/chat-session-list";
import { ChatInterface } from "@/components/chat/chat-interface";
import { ChatTitleEditor } from "@/components/chat/chat-title-editor";
import { ContextSelector } from "@/components/chat/context-selector";
import { DeepResearchToggle } from "@/components/chat/deep-research-toggle";
import { ToolsSelector } from "@/components/chat/tools-selector";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, PanelLeftClose, PanelLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function ChatPage() {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [streamingMessage, setStreamingMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [showContext, setShowContext] = useState(true);
  const [optimisticMessages, setOptimisticMessages] = useState<any[]>([]);
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [newChatTitle, setNewChatTitle] = useState("");
  const [newChatNotebook, setNewChatNotebook] = useState<string>("");
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
  const [deepResearchEnabled, setDeepResearchEnabled] = useState(false);

  const { data: sessions = [] } = useChatSessions();
  const { data: currentSession, refetch } = useChatSession(selectedSessionId!);
  const { data: notebooks = [] } = useNotebooks();
  const createSessionMutation = useCreateChatSession();
  const updateSessionMutation = useUpdateChatSession();
  const deleteSessionMutation = useDeleteChatSession();

  // Auto-select first session (don't auto-create)
  useEffect(() => {
    if (!selectedSessionId && sessions.length > 0) {
      setSelectedSessionId(sessions[0].id);
    }
  }, [sessions, selectedSessionId]);

  const handleCreateSession = async () => {
    try {
      // If a notebook is selected and no custom title is provided,
      // use the notebook name as the chat title
      let finalTitle = newChatTitle || "New Chat";

      if (!newChatTitle && newChatNotebook) {
        const notebook = notebooks.find(nb => nb.id === newChatNotebook);
        if (notebook) {
          finalTitle = notebook.name;
        }
      }

      const newSession = await createSessionMutation.mutateAsync({
        title: finalTitle,
        notebook_id: newChatNotebook || undefined,
      } as any);
      setSelectedSessionId(newSession.id);
      setShowNewChatDialog(false);
      setNewChatTitle("");
      setNewChatNotebook("");
      toast.success("New chat session created");
    } catch (error: any) {
      toast.error(error.message || "Failed to create chat session");
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    // Open confirmation dialog instead of window.confirm
    setSessionToDelete(sessionId);
  };

  const confirmDelete = async () => {
    if (!sessionToDelete) return;

    try {
      await deleteSessionMutation.mutateAsync(sessionToDelete);

      // If we deleted the selected session, select another one
      if (selectedSessionId === sessionToDelete) {
        const remaining = sessions.filter(s => s.id !== sessionToDelete);
        setSelectedSessionId(remaining.length > 0 ? remaining[0].id : null);
      }

      toast.success("Chat session deleted");
      setSessionToDelete(null);
    } catch (error: any) {
      toast.error(error.message || "Failed to delete chat session");
    }
  };

  const handleUpdateChatTitle = async (newTitle: string) => {
    if (!selectedSessionId) return;

    try {
      await updateSessionMutation.mutateAsync({
        sessionId: selectedSessionId,
        updates: { title: newTitle },
      });
      toast.success("Chat title updated");
    } catch (error: any) {
      toast.error(error.message || "Failed to update chat title");
      throw error; // Re-throw to let the component handle it
    }
  };

  const handleSendMessage = async (content: string) => {
    if (!selectedSessionId) return;

    setIsSending(true);
    setStreamingMessage("");

    // Add user message to optimistic messages immediately
    const tempUserMessage = {
      id: `temp-${Date.now()}`,
      role: "user" as const,
      content: content,
      session_id: selectedSessionId,
      created: new Date().toISOString(),
    };

    setOptimisticMessages((prev) => [...prev, tempUserMessage]);

    try {
      await chatApi.sendMessage(
        selectedSessionId,
        {
          message: content,  // Backend expects 'message' field
          stream: true,
          include_context: true,
          selected_source_ids: selectedSources,
          deep_research: deepResearchEnabled,
        },
        (chunk) => {
          setStreamingMessage((prev) => prev + chunk);
        }
      );

      setStreamingMessage("");
      // Clear optimistic messages and refetch actual data
      setOptimisticMessages([]);
      refetch();
    } catch (error: any) {
      toast.error(error.message || "Failed to send message");
      setStreamingMessage("");
      // Remove optimistic message on error
      setOptimisticMessages([]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-h-full bg-background p-6">
      <div className="max-w-[1920px] mx-auto w-full h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between mb-4 animate-fade-in-up">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSidebar(!showSidebar)}
            className="transition-all hover:scale-110"
          >
            {showSidebar ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeft className="w-4 h-4" />}
          </Button>
          <div>
            <div className="flex items-center gap-2">
              {currentSession ? (
                <ChatTitleEditor
                  title={currentSession.title || "New Chat"}
                  workspaceName={
                    currentSession.notebook_id
                      ? notebooks.find(nb => nb.id === currentSession.notebook_id)?.name
                      : undefined
                  }
                  onSave={handleUpdateChatTitle}
                />
              ) : (
                <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
                  Chat
                </h1>
              )}
              {deepResearchEnabled && (
                <Badge variant="outline" className="text-purple-600 border-purple-300 bg-purple-50 dark:bg-purple-950 animate-pulse-slow">
                  Deep Research
                </Badge>
              )}
              {isSending && (
                <Badge variant="outline" className="text-blue-600 border-blue-300 bg-blue-50 dark:bg-blue-950 animate-pulse">
                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  Processing...
                </Badge>
              )}
            </div>
            <p className="text-gray-500 dark:text-gray-400 mt-1">
              Have AI-powered conversations about your research
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowContext(!showContext)}
            className="transition-all hover:scale-105"
          >
            {showContext ? "Hide Context" : "Show Context"}
          </Button>
          <Dialog open={showNewChatDialog} onOpenChange={setShowNewChatDialog}>
            <DialogTrigger asChild>
              <Button className="transition-all hover:scale-105 hover:shadow-lg">
                <Plus className="w-4 h-4 mr-2" />
                New Chat
              </Button>
            </DialogTrigger>
            <DialogContent className="animate-fade-in">
              <DialogHeader>
                <DialogTitle>Create New Chat</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label>Chat Title (optional)</Label>
                  <Input
                    value={newChatTitle}
                    onChange={(e) => setNewChatTitle(e.target.value)}
                    placeholder="e.g., Research Discussion"
                  />
                </div>
                <div>
                  <Label>Workspace (optional)</Label>
                  <Select value={newChatNotebook || "none"} onValueChange={(val) => setNewChatNotebook(val === "none" ? "" : val)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a workspace or leave empty for General" />
                    </SelectTrigger>
                    <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                      <SelectItem value="none">None (General)</SelectItem>
                      {notebooks.map((nb) => (
                        <SelectItem key={nb.id} value={nb.id}>
                          {nb.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-sm text-muted-foreground mt-1">
                    Chat will use sources from this workspace as knowledge
                  </p>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowNewChatDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateSession} className="transition-all hover:scale-105">
                    Create Chat
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Main Layout */}
      <div className="flex-1 flex gap-6 min-h-0 overflow-hidden">
        {/* Sessions Sidebar */}
        {showSidebar && (
          <div className="w-80 flex-shrink-0 animate-fade-in">
            <ChatSessionList
              sessions={sessions}
              selectedId={selectedSessionId || undefined}
              onSelect={setSelectedSessionId}
              onDelete={handleDeleteSession}
            />
          </div>
        )}

        {/* Chat Interface */}
        <div className="flex-1 min-w-0 overflow-hidden animate-fade-in animation-delay-200">
          {selectedSessionId ? (
            <ChatInterface
              messages={[...(currentSession?.messages || []), ...optimisticMessages]}
              onSendMessage={handleSendMessage}
              isLoading={isSending}
              streamingMessage={streamingMessage}
              placeholder="Ask a question about your research..."
              notebookId={currentSession?.notebook_id}
            />
          ) : (
            <div className="flex items-center justify-center h-full animate-fade-in">
              <div className="text-center">
                <h3 className="text-lg font-semibold mb-2">No chat session selected</h3>
                <p className="text-gray-500 mb-4">
                  Create a new chat session to get started
                </p>
                <Button onClick={handleCreateSession} className="transition-all hover:scale-105 hover:shadow-lg">
                  <Plus className="w-4 h-4 mr-2" />
                  Create Session
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Context Sidebar with Tabs */}
        {showContext && (
          <div className="w-80 flex-shrink-0 flex flex-col space-y-4 animate-fade-in animation-delay-400">
            <DeepResearchToggle
              enabled={deepResearchEnabled}
              onToggle={setDeepResearchEnabled}
              disabled={isSending}
            />

            <Tabs defaultValue="tools" className="flex-1 flex flex-col min-h-0">
              <TabsList className="w-full grid grid-cols-2">
                <TabsTrigger value="tools">Tools</TabsTrigger>
                <TabsTrigger value="sources">Sources</TabsTrigger>
              </TabsList>

              <TabsContent value="tools" className="flex-1 mt-4 overflow-hidden">
                {selectedSessionId && (
                  <ToolsSelector
                    sessionId={selectedSessionId}
                    notebookId={currentSession?.notebook_id}
                    selectedToolIds={selectedTools}
                    onSelectionChange={setSelectedTools}
                    disabled={isSending}
                  />
                )}
              </TabsContent>

              <TabsContent value="sources" className="flex-1 mt-4 overflow-hidden">
                <ContextSelector
                  selectedSources={selectedSources}
                  onSelectionChange={setSelectedSources}
                  notebookId={currentSession?.notebook_id}
                />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!sessionToDelete} onOpenChange={(open) => !open && setSessionToDelete(null)}>
        <AlertDialogContent className="animate-fade-in">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Chat Session</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this chat session? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="transition-all hover:scale-105">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
