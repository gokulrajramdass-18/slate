"use client";

import { useState, useCallback, useEffect, useRef, startTransition } from "react";
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

  console.log('[ChatSessionPage] RENDER');

  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [streamingMessage, setStreamingMessage] = useState("");
  const [streamingSources, setStreamingSources] = useState<any[]>([]);
  const [streamingUIComponents, setStreamingUIComponents] = useState<any[]>([]);
  const [streamingToolResults, setStreamingToolResults] = useState<any[]>([]);
  const [streamingAgentSteps, setStreamingAgentSteps] = useState<AgentStep[]>([]);
  const [deepResearchJobId, setDeepResearchJobId] = useState<string | null>(null);
  const [deepResearchStatus, setDeepResearchStatus] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState("");
  const [optimisticUserMessage, setOptimisticUserMessage] = useState<string | null>(null);
  const [deepResearchEnabled, setDeepResearchEnabled] = useState(false);
  const [noteIds, setNoteIds] = useState<Set<string>>(new Set());
  const [isAnimating, setIsAnimating] = useState(false);

  // Refs for accumulating streamed text
  const fullTextRef = useRef("");

  const { data: session, refetch } = useChatSession(sessionId);
  const { data: workspace } = useNotebook(session?.notebook_id || "");
  const deleteMutation = useDeleteChatSession();

  // Poll for deep research job status
  useEffect(() => {
    if (!deepResearchJobId) return;

    const pollInterval = setInterval(async () => {
      try {
        const status = await chatApi.getDeepResearchStatus(sessionId);
        const job = status.latest;

        if (job) {
          setDeepResearchStatus(job.status);

          // If completed or failed, stop polling and refetch messages
          if (job.status === "completed" || job.status === "failed") {
            clearInterval(pollInterval);
            setDeepResearchJobId(null);
            await refetch();

            if (job.status === "completed") {
              toast.success("Deep research completed!");
            } else {
              toast.error(job.error || "Deep research failed");
            }
          }
        }
      } catch (error) {
        console.error("[Chat] Failed to poll deep research status:", error);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [deepResearchJobId, sessionId, refetch]);

  const handleNoteIdsChange = useCallback((ids: string[]) => {
    setNoteIds(new Set(ids));
  }, []);

  const handleSendMessage = async (content: string) => {
    setOptimisticUserMessage(content);
    setIsSending(true);
    setStreamingMessage("");
    setStreamingSources([]);
    setStreamingUIComponents([]);
    setStreamingToolResults([]);
    setStreamingAgentSteps([]);

    // Notify streaming manager that a new stream is starting
    window.dispatchEvent(new CustomEvent('streaming:start', {
      detail: { sessionId }
    }));

    try {
      const actualSourceIds = selectedSources.filter(id => !noteIds.has(id));

      const result = await chatApi.sendMessage(
        sessionId,
        {
          message: content,
          deep_research: deepResearchEnabled,
          selected_tool_ids: selectedTools.length > 0 ? selectedTools : undefined,
          selected_source_ids: actualSourceIds.length > 0 ? actualSourceIds : undefined,
        },
        (chunk) => setStreamingMessage((prev) => prev + chunk),
        (metadata) => {
          // Update streaming sources from metadata
          if (metadata?.sources) {
            setStreamingSources(metadata.sources);
          }
        },
        (components) => setStreamingUIComponents(components),
        (results) => setStreamingToolResults(results),
        (step) => setStreamingAgentSteps((prev) => [...prev, step])
      );

      // Notify streaming manager that stream ended
      window.dispatchEvent(new CustomEvent('streaming:end', {
        detail: { sessionId }
      }));

      // Check if this is a deep research job
      if ((result as any)?.metadata?.deep_research && (result as any)?.metadata?.job_id) {
        const jobId = (result as any).metadata.job_id;
        console.log('[Chat] Deep research job started:', jobId);
        setDeepResearchJobId(jobId);
        setDeepResearchStatus("running");
        toast.info("Deep research started in background. You can switch tabs or close the browser - results will be saved.");
      } else {
        // Regular message - refetch to get the saved message from database
        await refetch();
      }

      // Clear streaming state
      setStreamingMessage("");
      setStreamingSources([]);
      setStreamingUIComponents([]);
      setStreamingToolResults([]);
      setStreamingAgentSteps([]);
      setOptimisticUserMessage(null);
    } catch (error: any) {
      toast.error(error.message || "Failed to send message");
      setStreamingMessage("");
      setStreamingSources([]);
      setStreamingUIComponents([]);
      setStreamingToolResults([]);
      setStreamingAgentSteps([]);
      setOptimisticUserMessage(null);
    } finally {
      setIsSending(false);
    }
  };

  const handleBack = () => {
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
    <div className="flex flex-col h-full overflow-hidden">
      {/* Compact Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-3 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Button variant="ghost" size="sm" onClick={handleBack} className="flex-shrink-0">
            <ArrowLeft className="w-4 h-4" />
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
                className="h-8 text-sm"
              />
              <Button size="sm" onClick={handleUpdateTitle}><Check className="w-3 h-3" /></Button>
              <Button size="sm" variant="ghost" onClick={() => setIsEditingTitle(false)}><X className="w-3 h-3" /></Button>
            </div>
          ) : (
            <div className="flex items-center gap-2 min-w-0">
              <h1 className="text-base font-semibold truncate">{session.title || "Untitled Chat"}</h1>
              <Button variant="ghost" size="sm" onClick={() => { setEditedTitle(session.title || ""); setIsEditingTitle(true); }} className="flex-shrink-0 h-7 w-7 p-0">
                <Edit2 className="w-3 h-3" />
              </Button>
              {deepResearchEnabled && <Badge variant="secondary" className="text-xs flex-shrink-0">Research</Badge>}
              {isSending && <Loader2 className="w-4 h-4 animate-spin text-blue-500 flex-shrink-0" />}
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5 flex-shrink-0">
          <DeepResearchToggle enabled={deepResearchEnabled} onToggle={setDeepResearchEnabled} disabled={isSending} compact />
          <Button variant="ghost" size="sm" onClick={handleExport} className="h-8"><Download className="w-4 h-4" /></Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8"><Trash2 className="w-4 h-4" /></Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Chat Session</AlertDialogTitle>
                <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete}>Delete</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Chat Area - Fills remaining space */}
      <div className="flex-1 min-h-0">
        <ChatInterface
          messages={[
            ...session.messages,
            ...(optimisticUserMessage ? [{ id: "optimistic-user", session_id: sessionId, role: "user" as const, content: optimisticUserMessage, created: new Date().toISOString() }] : []),
          ]}
          onSendMessage={handleSendMessage}
          isLoading={isSending}
          streamingMessage={streamingMessage}
          streamingSources={streamingSources}
          streamingUIComponents={streamingUIComponents}
          streamingToolResults={streamingToolResults}
          streamingAgentSteps={streamingAgentSteps}
          placeholder="Type your message..."
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
  );
}
