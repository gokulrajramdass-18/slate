"use client";

import { useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { Loader2, MessageSquare, Brain, Search, Sparkles } from "lucide-react";
import type { ChatMessage as ChatMessageType, AgentStep } from "@/lib/types";

interface ChatInterfaceProps {
  messages: ChatMessageType[];
  onSendMessage: (content: string) => void;
  isLoading?: boolean;
  streamingMessage?: string;
  streamingSources?: any[];
  streamingUIComponents?: any[];
  streamingToolResults?: any[];
  streamingAgentSteps?: AgentStep[];
  placeholder?: string;
  isThinking?: boolean;
  notebookId?: string; // For saving messages to notes
  // New props for selectors in input area
  sessionId?: string;
  selectedTools?: string[];
  onToolsChange?: (tools: string[]) => void;
  selectedSources?: string[];
  onSourcesChange?: (sources: string[]) => void;
  onNoteIdsChange?: (noteIds: string[]) => void;
}

export function ChatInterface({
  messages,
  onSendMessage,
  isLoading = false,
  streamingMessage = "",
  streamingSources = [],
  streamingUIComponents = [],
  streamingToolResults = [],
  streamingAgentSteps = [],
  placeholder,
  isThinking = false,
  notebookId,
  sessionId,
  selectedTools = [],
  onToolsChange,
  selectedSources = [],
  onSourcesChange,
  onNoteIdsChange,
}: ChatInterfaceProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  };

  useEffect(() => {
    // Longer delay to ensure charts are fully rendered
    const timer = setTimeout(() => {
      scrollToBottom();
    }, 500);
    return () => clearTimeout(timer);
  }, [messages, streamingMessage, streamingUIComponents, streamingAgentSteps, isThinking]);

  return (
    <div className="flex flex-col h-full w-full">
      {/* Messages - Scrollable Area */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {messages.length === 0 && !streamingMessage && !isThinking ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mb-3">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
              Start a conversation
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-md">
              Ask questions about your research sources
            </p>
          </div>
        ) : (
          <ScrollArea className="h-full">
            <div className="px-4 py-4 pb-8 space-y-6">
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} notebookId={notebookId} />
              ))}

              {/* Thinking State */}
              {isThinking && !streamingMessage && (
                <div className="flex gap-3 items-start">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <Brain className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1">
                    <div className="rounded-lg px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
                      <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                        <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                        <span className="text-sm">Analyzing sources...</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Streaming Message */}
              {(streamingMessage || streamingAgentSteps.length > 0) && (
                <ChatMessage
                  message={{
                    id: "streaming",
                    session_id: "",
                    role: "assistant",
                    content: streamingMessage,
                    created: new Date().toISOString(),
                    sources: streamingSources,
                    ui_components: streamingUIComponents.length > 0 ? JSON.stringify(streamingUIComponents) : undefined,
                    tool_results: streamingToolResults.length > 0 ? JSON.stringify(streamingToolResults) : undefined,
                    agent_steps: streamingAgentSteps.length > 0 ? JSON.stringify(streamingAgentSteps) : undefined,
                  }}
                  isStreaming
                  notebookId={notebookId}
                />
              )}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        )}
      </div>

      {/* Input - Always Visible at Bottom */}
      <div className="flex-shrink-0 px-4 pb-4">
        <ChatInput
          onSend={onSendMessage}
          disabled={isLoading}
          placeholder={placeholder}
          sessionId={sessionId}
          notebookId={notebookId}
          selectedTools={selectedTools}
          onToolsChange={onToolsChange}
          selectedSources={selectedSources}
          onSourcesChange={onSourcesChange}
          onNoteIdsChange={onNoteIdsChange}
        />
      </div>
    </div>
  );
}
