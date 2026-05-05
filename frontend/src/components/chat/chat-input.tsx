"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Wrench, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ToolsPopoverSelector } from "./tools-popover-selector";
import { SourcesPopoverSelector } from "./sources-popover-selector";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  // Props for selectors
  sessionId?: string;
  notebookId?: string;
  selectedTools?: string[];
  onToolsChange?: (tools: string[]) => void;
  selectedSources?: string[];
  onSourcesChange?: (sources: string[]) => void;
  onNoteIdsChange?: (noteIds: string[]) => void;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Type your message...",
  sessionId,
  notebookId,
  selectedTools = [],
  onToolsChange,
  selectedSources = [],
  onSourcesChange,
  onNoteIdsChange,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      onSend(message.trim());
      setMessage("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [message]);

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="relative flex items-center gap-3 px-4 py-4 rounded-2xl border-2 border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-lg hover:shadow-xl hover:border-blue-400 dark:hover:border-blue-500 transition-all duration-200">
        {/* Left side - Action buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Tools Selector */}
          {sessionId && notebookId && onToolsChange && (
            <ToolsPopoverSelector
              sessionId={sessionId}
              notebookId={notebookId}
              selectedToolIds={selectedTools}
              onSelectionChange={onToolsChange}
              disabled={disabled}
            />
          )}

          {/* Sources Selector */}
          {onSourcesChange && (
            <SourcesPopoverSelector
              selectedSources={selectedSources}
              onSelectionChange={onSourcesChange}
              onNoteIdsChange={onNoteIdsChange}
              notebookId={notebookId}
              disabled={disabled}
            />
          )}
        </div>

        {/* Vertical divider */}
        {((sessionId && notebookId && onToolsChange) || onSourcesChange) && (
          <div className="w-px h-8 bg-gray-300 dark:bg-gray-600 flex-shrink-0" />
        )}

        {/* Center - Textarea */}
        <div className="flex-1 min-w-0">
          <Textarea
            ref={textareaRef}
            placeholder={placeholder}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            className="min-h-[56px] max-h-[200px] resize-none w-full border-0 focus-visible:ring-0 focus-visible:ring-offset-0 p-0 bg-transparent placeholder:text-gray-500 dark:placeholder:text-gray-400 text-base leading-relaxed"
            rows={2}
          />
        </div>

        {/* Right side - Send button */}
        <div className="flex-shrink-0">
          <Button
            type="submit"
            disabled={disabled || !message.trim()}
            size="lg"
            className="h-12 w-12 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 disabled:opacity-40 disabled:cursor-not-allowed shadow-md hover:shadow-lg transition-all duration-200"
          >
            {disabled ? (
              <Loader2 className="w-5 h-5 animate-spin text-white" />
            ) : (
              <Send className="w-5 h-5 text-white" />
            )}
          </Button>
        </div>
      </div>

      {/* Helper text when disabled */}
      {disabled && (
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-3 flex items-center gap-2 px-4">
          <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
          <span className="font-medium">Processing your message...</span>
        </p>
      )}
    </form>
  );
}
