"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { MessageSquare, Send, Loader2, Sparkles, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api/client";

interface Message {
  role: "user" | "assistant";
  content: string;
  changes?: Array<{
    action: string;
    details: Record<string, any>;
    result: Record<string, any>;
  }>;
}

interface MicrositeChatProps {
  micrositeId: string;
  onChangesApplied?: () => void;
}

export function MicrositeChat({ micrositeId, onChangesApplied }: MicrositeChatProps) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm your AI assistant. I can help you edit this microsite. Try asking me to:\n\n• Change section content\n• Update colors or styling\n• Add or update a logo\n• Reorder or hide sections\n• Make any text changes\n\nWhat would you like to do?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const { data } = await apiClient.post(
        `/microsites/${micrositeId}/chat`,
        {
          message: userMessage,
          microsite_id: micrositeId,
        }
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          changes: data.changes_made,
        },
      ]);

      if (data.changes_made && data.changes_made.length > 0) {
        toast.success(`Applied ${data.changes_made.length} change(s)`);

        // Invalidate queries to refresh the UI
        queryClient.invalidateQueries({ queryKey: ["microsite-content", micrositeId] });
        queryClient.invalidateQueries({ queryKey: ["microsite", micrositeId] });

        // Trigger callback to refresh preview iframe
        console.log("Triggering preview refresh callback");
        if (onChangesApplied) {
          onChangesApplied();
        }
      }
    } catch (error: any) {
      console.error("Chat error:", error);
      toast.error(error.response?.data?.detail || "Failed to process request");
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Sorry, I encountered an error processing your request. Please try again.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Card className="flex flex-col h-[600px]">
      {/* Header */}
      <div className="flex items-center gap-2 p-4 border-b">
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-primary" />
        </div>
        <div>
          <h3 className="font-semibold text-sm">AI Editor</h3>
          <p className="text-xs text-muted-foreground">
            Edit with natural language
          </p>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.map((message, idx) => (
            <div
              key={idx}
              className={`flex gap-3 ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {message.role === "assistant" && (
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <MessageSquare className="w-4 h-4 text-primary" />
                </div>
              )}

              <div
                className={`max-w-[80%] space-y-2 ${
                  message.role === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`rounded-lg px-4 py-2 ${
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                </div>

                {/* Show changes made */}
                {message.changes && message.changes.length > 0 && (
                  <div className="space-y-1">
                    {message.changes.map((change, cidx) => (
                      <Badge
                        key={cidx}
                        variant="secondary"
                        className="text-xs gap-1"
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        {change.action.replace(/_/g, " ")}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {message.role === "user" && (
                <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                  <span className="text-xs text-primary-foreground font-semibold">
                    You
                  </span>
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <MessageSquare className="w-4 h-4 text-primary" />
              </div>
              <div className="bg-muted rounded-lg px-4 py-2">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your request... (e.g., 'Change the hero text to Welcome')"
            className="min-h-[60px] resize-none"
            disabled={isLoading}
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            size="icon"
            className="h-[60px] w-[60px]"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </Card>
  );
}
