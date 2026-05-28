"use client";

import { User, Bot, Copy, Check, FileText, Wrench, Save } from "lucide-react";
import { useState, useEffect, useRef, useMemo } from "react";
import { useRouter } from "@/lib/routing/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import rehypeRaw from "rehype-raw";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  ChatMessage as ChatMessageType,
  UIComponentData,
  ToolResultData,
} from "@/lib/types";
import { parseAgentSteps } from "@/lib/types";
import { GenerativeUIRenderer } from "@/components/chat/generative-ui/GenerativeUIRenderer";
import { AgentStepsViewer } from "./agent-steps-viewer";
import { PresentationChatCommands, detectPresentationIntent } from "@/components/presentations/PresentationChatCommands";

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
  notebookId?: string; // For saving to notes
}

export function ChatMessage({ message, isStreaming = false, notebookId }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [noteTitle, setNoteTitle] = useState("");
  const isUser = message.role === "user";
  const contentRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Memoize presentation intent detection to avoid re-computing on every render
  const presentationIntent = useMemo(() => {
    if (!isUser || isStreaming) return { isMatch: false };
    return detectPresentationIntent(message.content);
  }, [isUser, isStreaming, message.content]);

  // Determine effective render mode
  const renderMode = message.render_mode ?? "markdown";

  // Parse JSON fields safely
  const parsedUIComponents = useMemo((): UIComponentData[] | undefined => {
    if (!message.ui_components) return undefined;
    try {
      const parsed = typeof message.ui_components === "string"
        ? JSON.parse(message.ui_components)
        : message.ui_components;
      return parsed;
    } catch (e) {
      return undefined;
    }
  }, [message.ui_components]);

  const parsedToolResults = useMemo((): ToolResultData[] | undefined => {
    if (!message.tool_results) return undefined;
    try {
      return typeof message.tool_results === "string"
        ? JSON.parse(message.tool_results)
        : message.tool_results;
    } catch {
      return undefined;
    }
  }, [message.tool_results]);

  // Parse agent steps
  const agentSteps = useMemo(() => parseAgentSteps(message), [message]);

  const hasGenerativeContent =
    (parsedUIComponents && parsedUIComponents.length > 0) ||
    (parsedToolResults && parsedToolResults.length > 0);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveToNotesClick = () => {
    if (!notebookId) {
      alert("No workspace selected. Please select a workspace to save notes.");
      return;
    }

    // Generate default title from first 50 characters of content
    const defaultTitle = message.content.substring(0, 50).trim() + (message.content.length > 50 ? "..." : "");
    setNoteTitle(defaultTitle);
    setShowSaveDialog(true);
  };

  const handleConfirmSave = async () => {
    if (!noteTitle.trim()) {
      alert("Please enter a title for the note.");
      return;
    }

    setIsSaving(true);
    try {
      const response = await fetch(`/api/notes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": "default-user",
        },
        body: JSON.stringify({
          notebook_id: notebookId,
          title: noteTitle.trim(),
          content: message.content,
          note_type: "ai_generated",
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to save note");
      }

      setSaved(true);
      setShowSaveDialog(false);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error("Error saving note:", error);
      alert("Failed to save note. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  // Add click handlers to citation links after render
  useEffect(() => {
    if (!contentRef.current || isUser) return;

    const handleCitationClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains('citation-link')) {
        e.preventDefault();
        e.stopPropagation();
        const sourceIndex = target.getAttribute('data-source');
        if (sourceIndex) {
          const badge = document.querySelector(`[data-source-index="${sourceIndex}"]`);
          if (badge) {
            badge.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            badge.classList.add('ring-2', 'ring-blue-500', 'ring-offset-2');
            setTimeout(() => {
              badge.classList.remove('ring-2', 'ring-blue-500', 'ring-offset-2');
            }, 2000);
          }
        }
      }
    };

    contentRef.current.addEventListener('click', handleCitationClick);
    return () => {
      contentRef.current?.removeEventListener('click', handleCitationClick);
    };
  }, [message.content, isUser]);

  // Process message content to make citations clickable
  const processedContent = useMemo(() => {
    if (!message.sources || message.sources.length === 0) {
      return message.content;
    }

    return message.content.replace(
      /\[(\d+)\]/g,
      (match, num) => {
        const sourceIndex = parseInt(num);
        const source = message.sources?.[sourceIndex - 1];
        const sourceName = source?.source_name || 'Source';
        return `<sup class="citation-link cursor-pointer text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 hover:underline font-bold transition-colors" data-source="${num}" title="${sourceName}">[${num}]</sup>`;
      }
    );
  }, [message.content, message.sources]);

  const renderMarkdownContent = () => (
    <div ref={contentRef} data-streaming={isStreaming} className="prose prose-sm dark:prose-invert max-w-full leading-7 prose-pre:max-w-full prose-pre:overflow-x-auto prose-table:max-w-full prose-table:overflow-x-auto prose-p:my-3 prose-p:break-words prose-headings:mb-3 prose-headings:mt-4 overflow-hidden">
      {isStreaming ? (
        // During streaming, show raw text with basic formatting to avoid expensive markdown parsing.
        // Use a <div> (not <pre>) to avoid inheriting Tailwind Typography's dark <pre> background,
        // and match the final paragraph styling so there's no visual flash when markdown takes over.
        <div className="whitespace-pre-wrap font-sans text-[15px] leading-7 bg-transparent text-inherit m-0 p-0">
          {processedContent}
          <span className="inline-block w-2 h-4 ml-1 bg-current animate-pulse" />
        </div>
      ) : (
        // After streaming completes, render full markdown
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight, rehypeRaw]}
          components={{
          pre: ({ children, ...props }: any) => (
            <pre
              className="overflow-x-auto max-w-full bg-gray-900 text-gray-100 p-4 rounded-lg my-4"
              {...props}
            >
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }: any) => {
            const inline = !className?.includes("language-");
            return inline ? (
              <code
                className={cn(
                  "px-2 py-1 rounded bg-gray-200 dark:bg-gray-700 text-sm font-mono whitespace-nowrap",
                  className
                )}
                {...props}
              >
                {children}
              </code>
            ) : (
              <code className={cn("text-sm block overflow-x-auto", className)} {...props}>
                {children}
              </code>
            );
          },
          table: ({ children, ...props }: any) => (
            <div className="overflow-x-auto max-w-full my-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700" {...props}>
                {children}
              </table>
            </div>
          ),
          thead: ({ children, ...props }: any) => (
            <thead className="bg-gray-50 dark:bg-gray-800" {...props}>
              {children}
            </thead>
          ),
          tbody: ({ children, ...props }: any) => (
            <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700" {...props}>
              {children}
            </tbody>
          ),
          tr: ({ children, ...props }: any) => (
            <tr className="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors" {...props}>
              {children}
            </tr>
          ),
          th: ({ children, ...props }: any) => (
            <th
              className="px-6 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider border-r border-gray-200 dark:border-gray-700 last:border-r-0"
              {...props}
            >
              {children}
            </th>
          ),
          td: ({ children, ...props }: any) => (
            <td
              className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100 border-r border-gray-200 dark:border-gray-700 last:border-r-0"
              {...props}
            >
              {children}
            </td>
          ),
          a: ({ children, ...props }: any) => (
            <a
              className="text-primary-600 dark:text-primary-400 hover:underline font-medium"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            >
              {children}
            </a>
          ),
          p: ({ children, ...props }: any) => (
            <p className="mb-3 last:mb-0 text-[15px]" {...props}>
              {children}
            </p>
          ),
          ul: ({ children, ...props }: any) => (
            <ul className="mb-3 pl-6 list-disc space-y-1.5" {...props}>
              {children}
            </ul>
          ),
          ol: ({ children, ...props }: any) => (
            <ol className="mb-3 pl-6 list-decimal space-y-1.5" {...props}>
              {children}
            </ol>
          ),
          li: ({ children, ...props }: any) => (
            <li className="text-[15px] leading-7" {...props}>
              {children}
            </li>
          ),
          h1: ({ children, ...props }: any) => (
            <h1 className="text-2xl font-bold mb-3 mt-4" {...props}>
              {children}
            </h1>
          ),
          h2: ({ children, ...props }: any) => (
            <h2 className="text-xl font-bold mb-3 mt-4" {...props}>
              {children}
            </h2>
          ),
          h3: ({ children, ...props }: any) => (
            <h3 className="text-lg font-semibold mb-3 mt-4" {...props}>
              {children}
            </h3>
          ),
          sup: ({ children, ...props }: any) => {
            // Preserve citation link styling from processedContent
            return <sup {...props}>{children}</sup>;
          },
        }}
      >
        {processedContent}
      </ReactMarkdown>
      )}
    </div>
  );

  const renderGenerativeContent = () => (
    <div className="w-full space-y-4 block clear-both">
      <GenerativeUIRenderer
        components={parsedUIComponents}
        toolResults={parsedToolResults}
      />
    </div>
  );

  const renderAssistantContent = () => {
    switch (renderMode) {
      case "generative":
        // Pure generative: only render UI components (with text fallback)
        if (hasGenerativeContent) {
          return renderGenerativeContent();
        }
        // Fallback to markdown if no generative content
        return renderMarkdownContent();

      case "hybrid":
        // Hybrid mode: text and charts will be rendered separately in the layout
        // This should NOT be called when hybrid mode is active at the layout level
        return (
          <div className="space-y-8">
            {message.content && renderMarkdownContent()}
            {hasGenerativeContent && renderGenerativeContent()}
          </div>
        );

      case "markdown":
      default:
        return renderMarkdownContent();
    }
  };

  return (
    <div className={cn("flex gap-4 group items-start mb-12 clear-both w-full", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-transform group-hover:scale-105",
          isUser
            ? "bg-gradient-to-br from-blue-500 to-blue-600 text-white"
            : "bg-gradient-to-br from-purple-500 to-indigo-600 text-white border-2 border-purple-200 dark:border-purple-800"
        )}
      >
        {isUser ? <User className="w-6 h-6" /> : <Bot className="w-6 h-6" />}
      </div>

      {/* Message Content */}
      <div className={cn("flex-1 space-y-3 min-w-0 max-w-full relative block", isUser ? "flex flex-col items-end" : "")}>
        {/* Agent Execution Steps - Always appears FIRST (above response) */}
        {!isUser && agentSteps.length > 0 && (
          <div className="max-w-full overflow-hidden block">
            <AgentStepsViewer steps={agentSteps} isStreaming={isStreaming} />
          </div>
        )}

        {/* Check if this is hybrid mode with special rendering */}
        {!isUser && renderMode === "hybrid" ? (
          <div className="space-y-6 clear-both block w-full">
            {/* Text content in rounded bubble */}
            {message.content && message.content.trim() && (
              <div className="rounded-2xl px-6 py-5 shadow-sm transition-all bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 hover:shadow-md">
                {renderMarkdownContent()}
              </div>
            )}

            {/* Visual separator between text and charts */}
            {message.content && message.content.trim() && hasGenerativeContent && (
              <div className="relative">
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="w-full border-t border-gray-200 dark:border-gray-700"></div>
                </div>
                <div className="relative flex justify-center">
                  <span className="px-3 bg-gray-50 dark:bg-gray-900 text-sm text-gray-500 dark:text-gray-400 font-medium">
                    Visualizations
                  </span>
                </div>
              </div>
            )}

            {/* Charts and visualizations with clear separation */}
            {hasGenerativeContent && (
              <div className="space-y-4 clear-both block w-full min-h-fit">
                {renderGenerativeContent()}
              </div>
            )}
          </div>
        ) : (
          /* Normal rendering for non-hybrid modes */
          <div
            className={cn(
              "rounded-2xl px-6 py-4 shadow-sm transition-all break-words overflow-hidden",
              isUser
                ? "bg-gradient-to-br from-blue-500 to-blue-600 text-white max-w-[85%] shadow-md"
                : "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 max-w-full hover:shadow-md",
            )}
          >
            {isUser ? (
              <p className="whitespace-pre-wrap m-0 leading-relaxed text-[15px]">{message.content}</p>
            ) : (
              renderAssistantContent()
            )}
          </div>
        )}

        {/* Presentation Intent Detection - Show after user messages */}
        {presentationIntent.isMatch && (
          <div className="w-full max-w-2xl mt-4">
            <PresentationChatCommands
              message={message.content}
              notebookId={notebookId}
            />
          </div>
        )}

        {/* Sources Used */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-2.5 max-w-[95%]">
            {message.sources.map((source, idx) => (
              <Badge
                key={idx}
                variant="secondary"
                className="text-xs py-1.5 px-3 transition-all hover:shadow-sm cursor-pointer bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-700"
                data-source-index={idx + 1}
              >
                <FileText className="w-3 h-3 mr-1.5" />
                [{idx + 1}] {source.source_name}
              </Badge>
            ))}
          </div>
        )}

        {/* Actions - positioned below all content */}
        {!isUser && !isStreaming && (
          <div className="flex gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="h-9 px-4 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors font-medium"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 mr-2 text-green-600" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 mr-2" />
                  Copy
                </>
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSaveToNotesClick}
              disabled={isSaving}
              className="h-9 px-4 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors disabled:opacity-50 font-medium"
            >
              {saved ? (
                <>
                  <Check className="w-4 h-4 mr-2 text-green-600" />
                  Saved
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 mr-2" />
                  Save to Notes
                </>
              )}
            </Button>
          </div>
        )}
      </div>

      {/* Save to Notes Dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Save to Notes</DialogTitle>
            <DialogDescription>
              Enter a title for this note. It will be saved to the current workspace.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="note-title">Note Title</Label>
              <Input
                id="note-title"
                value={noteTitle}
                onChange={(e) => setNoteTitle(e.target.value)}
                placeholder="Enter a descriptive title..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleConfirmSave();
                  }
                }}
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowSaveDialog(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button onClick={handleConfirmSave} disabled={isSaving || !noteTitle.trim()}>
              {isSaving ? "Saving..." : "Save Note"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
