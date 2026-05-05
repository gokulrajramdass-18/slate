"use client";

import { useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useChatSession, useDeleteChatSession, useNotebook } from "@/lib/hooks/use-api";
import { chatApi } from "@/lib/api/chat";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ChatInterface } from "@/components/chat/chat-interface";
import { DeepResearchToggle } from "@/components/chat/deep-research-toggle";
import { ArrowLeft, Download, Trash2, Edit2, Check, X, Loader2 } from "lucide-react";
import { toast } from "sonner";
import type { AgentStep } from "@/lib/types";
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

export default function ChatSessionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [streamingMessage, setStreamingMessage] = useState("");
  const [streamingUIComponents, setStreamingUIComponents] = useState<any[]>([]);
  const [streamingToolResults, setStreamingToolResults] = useState<any[]>([]);
  const [streamingAgentSteps, setStreamingAgentSteps] = useState<AgentStep[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState("");
  const [optimisticUserMessage, setOptimisticUserMessage] = useState<string | null>(null);
  const [deepResearchEnabled, setDeepResearchEnabled] = useState(false);
  const [noteIds, setNoteIds] = useState<Set<string>>(new Set());

  const { data: session, refetch } = useChatSession(sessionId);
  const { data: workspace } = useNotebook(session?.notebook_id || "");
  const deleteMutation = useDeleteChatSession();

  // Memoize the callback to prevent infinite re-renders in ContextSelector
  const handleNoteIdsChange = useCallback((ids: string[]) => {
    console.log("[Chat Page] handleNoteIdsChange called with:", ids);
    setNoteIds(new Set(ids));
    console.log("[Chat Page] Note IDs Set updated, size:", ids.length);
  }, []);

  const handleSendMessage = async (content: string) => {
    console.log("[Chat Page] Sending message:", content);

    // Optimistically show user message immediately
    setOptimisticUserMessage(content);
    setIsSending(true);
    setStreamingMessage("");
    setStreamingUIComponents([]);
    setStreamingToolResults([]);
    setStreamingAgentSteps([]);

    try {
      // Filter out note IDs - only send actual source IDs
      // Notes are automatically included by the backend via include_notes=True
      const actualSourceIds = selectedSources.filter(id => !noteIds.has(id));

      console.log("[Chat Page] Selected sources:", selectedSources);
      console.log("[Chat Page] Note IDs:", Array.from(noteIds));
      console.log("[Chat Page] Actual source IDs:", actualSourceIds);

      const result = await chatApi.sendMessage(
        sessionId,
        {
          message: content,
          deep_research: deepResearchEnabled,
          selected_tool_ids: selectedTools.length > 0 ? selectedTools : undefined,
          selected_source_ids: actualSourceIds.length > 0 ? actualSourceIds : undefined,
        },
        (chunk) => {
          console.log("[Chat Page] Received chunk:", chunk);
          setStreamingMessage((prev) => prev + chunk);
        },
        undefined, // onMetadata
        (components) => {
          console.log("[Chat Page] ===== RECEIVED UI COMPONENTS =====");
          console.log("[Chat Page] Components:", components);
          console.log("[Chat Page] Components type:", typeof components);
          console.log("[Chat Page] Components is array:", Array.isArray(components));
          console.log("[Chat Page] Components length:", components?.length);
          console.log("[Chat Page] First component:", components?.[0]);
          console.log("[Chat Page] First component props:", components?.[0]?.props);
          console.log("[Chat Page] First component columns:", components?.[0]?.props?.columns);
          setStreamingUIComponents(components);
        },
        (results) => {
          console.log("[Chat Page] Received tool results:", results);
          setStreamingToolResults(results);
        },
        (step) => {
          console.log("[Chat Page] Received agent step:", step);
          console.log("[Chat Page] Current step count before add:", streamingAgentSteps.length);
          setStreamingAgentSteps((prev) => {
            const newSteps = [...prev, step];
            console.log("[Chat Page] Updated step count:", newSteps.length);
            return newSteps;
          });
        }
      );

      console.log("[Chat Page] Message sent successfully, result:", result);

      // Force refetch to show the conversation FIRST
      await refetch();
      console.log("[Chat Page] Session refetched");

      // THEN clear streaming states (so agent steps from DB show without gap)
      setStreamingMessage("");
      setStreamingUIComponents([]);
      setStreamingToolResults([]);
      setStreamingAgentSteps([]);
      setOptimisticUserMessage(null);
    } catch (error: any) {
      console.error("[Chat Page] Error sending message:", error);
      toast.error(error.message || "Failed to send message");
      setStreamingMessage("");
      setStreamingUIComponents([]);
      setStreamingToolResults([]);
      setStreamingAgentSteps([]);
      setOptimisticUserMessage(null);
    } finally {
      console.log("[Chat Page] Setting isSending to false");
      setIsSending(false);
    }
  };

  const handleBack = () => {
    // If session has a notebook_id, go back to workspace, otherwise to chat list
    if (session?.notebook_id) {
      router.push(`/workspaces/${session.notebook_id}`);
    } else {
      router.push("/chat");
    }
  };

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(sessionId);
      toast.success("Chat session deleted");
      // Navigate back after delete
      if (session?.notebook_id) {
        router.push(`/workspaces/${session.notebook_id}`);
      } else {
        router.push("/chat");
      }
    } catch (error: any) {
      toast.error(error.message || "Failed to delete chat session");
    }
  };

  const handleUpdateTitle = async () => {
    if (!editedTitle.trim()) return;

    try {
      await chatApi.update(sessionId, { title: editedTitle });
      refetch();
      setIsEditingTitle(false);
      toast.success("Title updated");
    } catch (error: any) {
      toast.error(error.message || "Failed to update title");
    }
  };

  const handleExport = () => {
    if (!session) return;

    const content = session.messages
      .map((msg) => `${msg.role.toUpperCase()}: ${msg.content}`)
      .join("\n\n");

    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat-${session.title || "session"}-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Chat exported");
  };

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <p>Loading chat session...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-gray-50 dark:bg-gray-950">
      {/* Compact Header */}
      <div className="flex items-center justify-between px-6 py-3 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex-shrink-0 animate-fade-in-up">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBack}
            className="flex-shrink-0 transition-all hover:scale-110"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>

          {isEditingTitle ? (
            <div className="flex items-center gap-2 flex-1 max-w-md">
              <Input
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleUpdateTitle();
                  if (e.key === "Escape") setIsEditingTitle(false);
                }}
                autoFocus
                className="h-8"
              />
              <Button size="sm" onClick={handleUpdateTitle} className="transition-all hover:scale-110">
                <Check className="w-4 h-4" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setIsEditingTitle(false)}
                className="transition-all hover:scale-110"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">{session.title || "Untitled Chat"}</h1>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setEditedTitle(session.title || "");
                    setIsEditingTitle(true);
                  }}
                  className="transition-all hover:scale-110"
                >
                  <Edit2 className="w-4 h-4" />
                </Button>
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
              {workspace && (
                <p className="text-sm text-gray-500">
                  Workspace: <span className="font-medium">{workspace.name}</span>
                </p>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Deep Research Toggle - Compact version for header */}
          <DeepResearchToggle
            enabled={deepResearchEnabled}
            onToggle={setDeepResearchEnabled}
            disabled={isSending}
            compact
          />

          <Button variant="outline" size="sm" onClick={handleExport} className="transition-all hover:scale-105">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" size="sm" className="transition-all hover:scale-105">
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent className="animate-fade-in">
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Chat Session</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete this chat session? This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete} className="transition-all hover:scale-105">Delete</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Main Layout */}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden max-w-5xl mx-auto w-full p-4 animate-fade-in animation-delay-200">
        {/* Chat Interface */}
        <div className="flex-1 min-h-0 flex flex-col">
          <ChatInterface
            messages={[
              ...session.messages,
              // Add optimistic user message
              ...(optimisticUserMessage
                ? [{
                    id: "optimistic-user",
                    session_id: sessionId,
                    role: "user" as const,
                    content: optimisticUserMessage,
                    created: new Date().toISOString(),
                  }]
                : []),
            ]}
            onSendMessage={handleSendMessage}
            isLoading={isSending}
            streamingMessage={streamingMessage}
            streamingUIComponents={streamingUIComponents}
            streamingToolResults={streamingToolResults}
            streamingAgentSteps={streamingAgentSteps}
            placeholder="Continue the conversation..."
            notebookId={session.notebook_id}
            sessionId={sessionId}
            selectedTools={selectedTools}
            onToolsChange={setSelectedTools}
            selectedSources={selectedSources}
            onSourcesChange={setSelectedSources}
            onNoteIdsChange={handleNoteIdsChange}
          />
        </div>
      </div>
    </div>
  );
}
