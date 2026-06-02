"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  MessageSquare,
  ArrowRight,
  CheckCircle2,
  HelpCircle,
  AlertCircle,
  Radio,
  ClipboardList,
  MessageCircle,
  User,
  Wrench,
} from "lucide-react";
import type { AgentMessage } from "@/lib/types";

interface MessageTimelineProps {
  messages: AgentMessage[];
}

const messageTypeConfig: Record<
  string,
  { icon: React.ElementType; color: string; bgColor: string; label?: string }
> = {
  // Pattern-executor message kinds (backend emits these via
  // PatternContext.emit). Aliases for the legacy names follow.
  task_assign: {
    icon: ClipboardList,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-50 dark:bg-purple-950 border-purple-200 dark:border-purple-800",
    label: "task assigned",
  },
  task_result: {
    icon: CheckCircle2,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800",
    label: "task result",
  },
  control: {
    icon: AlertCircle,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800",
    label: "control",
  },
  tool_call: {
    icon: Wrench,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-50 dark:bg-purple-950 border-purple-200 dark:border-purple-800",
    label: "tool call",
  },
  tool_result: {
    icon: Wrench,
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-50 dark:bg-emerald-950 border-emerald-200 dark:border-emerald-800",
    label: "tool result",
  },
  chat: {
    icon: MessageCircle,
    color: "text-indigo-600 dark:text-indigo-400",
    bgColor: "bg-indigo-50 dark:bg-indigo-950 border-indigo-200 dark:border-indigo-800",
    label: "chat",
  },
  // Legacy (pre-pattern) names — keep for back-compat with older executions.
  task_assignment: {
    icon: ClipboardList,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-50 dark:bg-purple-950 border-purple-200 dark:border-purple-800",
  },
  result: {
    icon: CheckCircle2,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800",
  },
  question: {
    icon: HelpCircle,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800",
  },
  feedback: {
    icon: MessageCircle,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-50 dark:bg-amber-950 border-amber-200 dark:border-amber-800",
  },
  status_update: {
    icon: AlertCircle,
    color: "text-gray-600 dark:text-gray-400",
    bgColor: "bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-800",
  },
  broadcast: {
    icon: Radio,
    color: "text-indigo-600 dark:text-indigo-400",
    bgColor: "bg-indigo-50 dark:bg-indigo-950 border-indigo-200 dark:border-indigo-800",
  },
};

export function MessageTimeline({ messages }: MessageTimelineProps) {
  const [selectedMessage, setSelectedMessage] = useState<AgentMessage | null>(null);

  if (messages.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-gray-500">
        <MessageSquare className="h-8 w-8 mx-auto mb-2 text-gray-300 dark:text-gray-700" />
        No messages yet
      </div>
    );
  }

  return (
    <>
      <div className="relative space-y-0">
        {/* Timeline line */}
        <div className="absolute left-5 top-0 bottom-0 w-px bg-gray-200 dark:bg-gray-700" />

        {messages.map((msg, index) => {
        const messageType = msg.message_type || "message";
        const config = messageTypeConfig[messageType] || messageTypeConfig.status_update;
        const Icon = config.icon;

        return (
          <div
            key={msg.id || index}
            className="relative flex gap-3 py-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900 rounded-lg px-2 -mx-2 transition-colors"
            onClick={() => setSelectedMessage(msg)}
          >
            {/* Timeline dot */}
            <div className="relative z-10 flex-shrink-0 w-10 flex items-center justify-center">
              <div className={`p-1.5 rounded-full bg-white dark:bg-gray-950 border-2 ${
                config.bgColor.includes("border")
                  ? config.bgColor.split(" ").filter(c => c.startsWith("border")).join(" ")
                  : "border-gray-200 dark:border-gray-700"
              }`}>
                <Icon className={`h-3.5 w-3.5 ${config.color}`} />
              </div>
            </div>

            {/* Message content */}
            <Card className={`flex-1 border ${config.bgColor}`}>
              <CardContent className="p-3">
                <div className="flex items-center gap-2 mb-1">
                  <User className="h-3 w-3 text-gray-500" />
                  <span className="text-xs font-semibold text-gray-900 dark:text-gray-100">
                    {msg.from_agent_name || "System"}
                  </span>
                  {msg.to_agent_name && (
                    <>
                      <ArrowRight className="h-3 w-3 text-gray-400" />
                      <User className="h-3 w-3 text-gray-500" />
                      <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                        {msg.to_agent_name}
                      </span>
                    </>
                  )}
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 ml-auto">
                    {config.label || messageType.replace(/_/g, " ")}
                  </Badge>
                </div>

                <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2">
                  {msg.content}
                </p>

                <div className="mt-1.5 flex items-center justify-between">
                  <div className="text-[10px] text-gray-400">
                    {(() => {
                      const ts = msg.timestamp || (msg as any).created;
                      return ts ? new Date(ts).toLocaleTimeString() : "";
                    })()}
                  </div>
                  <span className="text-[10px] text-blue-600 dark:text-blue-400">Click to view full message</span>
                </div>
              </CardContent>
            </Card>
          </div>
        );
      })}
      </div>

      {/* Message Details Dialog */}
      <Dialog open={!!selectedMessage} onOpenChange={(open) => !open && setSelectedMessage(null)}>
        <DialogContent className="max-w-5xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Message Details
            </DialogTitle>
            <DialogDescription>
              Full agent output, sender / recipient, and execution metadata.
            </DialogDescription>
          </DialogHeader>
          {selectedMessage && (() => {
            // Metadata may arrive as an object (live SSE) or as a JSON
            // string (older execution rows pulled from the DB directly).
            // Normalize once so the rest of the dialog can read keys
            // confidently.
            const meta: Record<string, any> = (() => {
              const m = (selectedMessage as any).metadata;
              if (!m) return {};
              if (typeof m === "string") {
                try { return JSON.parse(m) || {}; } catch { return {}; }
              }
              return m;
            })();

            // Surface the fields the backend always tags on agent steps.
            const senderRole = meta.role || (selectedMessage as any).from_agent_role;
            const senderAgentName = meta.agent_name || selectedMessage.from_agent_name;
            const isClarification = !!meta.is_clarification;
            const isAutoAnswer = !!meta.auto_answer;
            const ts = selectedMessage.timestamp || (selectedMessage as any).created;
            const messageType = selectedMessage.message_type || "message";
            const config = messageTypeConfig[messageType] || messageTypeConfig.status_update;

            // Hide noise from the "additional metadata" block — these are
            // already rendered above as headers / chips.
            const HIDDEN_META = new Set([
              "agent_name", "role", "is_clarification", "question",
              "auto_answer", "tool_name", "tool_input", "tool_output",
            ]);
            const extraMeta = Object.entries(meta).filter(([k]) => !HIDDEN_META.has(k));

            return (
              <ScrollArea className="max-h-[75vh] pr-4">
                <div className="space-y-5">
                  {/* Header */}
                  <div className="flex items-start justify-between pb-4 border-b">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex items-center gap-2 min-w-0">
                        <User className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-base truncate">
                              {senderAgentName || "System"}
                            </p>
                            {senderRole && (
                              <Badge variant="outline" className="text-[10px] py-0">
                                {senderRole}
                              </Badge>
                            )}
                          </div>
                          {selectedMessage.from_agent_id && selectedMessage.from_agent_id !== "system" && (
                            <p className="text-xs text-gray-400 font-mono truncate">
                              {selectedMessage.from_agent_id}
                            </p>
                          )}
                        </div>
                      </div>
                      {selectedMessage.to_agent_name && (
                        <>
                          <ArrowRight className="h-5 w-5 text-gray-400 shrink-0" />
                          <div className="flex items-center gap-2 min-w-0">
                            <User className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0" />
                            <div className="min-w-0">
                              <p className="font-semibold text-base truncate">{selectedMessage.to_agent_name}</p>
                              {selectedMessage.to_agent_id && (
                                <p className="text-xs text-gray-400 font-mono truncate">
                                  {selectedMessage.to_agent_id}
                                </p>
                              )}
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0 ml-4">
                      <Badge className={`${config.color} ${config.bgColor} text-xs`}>
                        {config.label || messageType.replace(/_/g, " ")}
                      </Badge>
                      {isClarification && (
                        <Badge variant="outline" className="text-[10px] text-amber-700 border-amber-300 bg-amber-50 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-800">
                          Clarification request
                        </Badge>
                      )}
                      {isAutoAnswer && (
                        <Badge variant="outline" className="text-[10px] text-purple-700 border-purple-300 bg-purple-50 dark:bg-purple-950 dark:text-purple-200 dark:border-purple-800">
                          Auto-answered
                        </Badge>
                      )}
                      {ts && (
                        <span className="text-xs text-gray-500">
                          {new Date(ts).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* If this message is a paused clarification, surface the
                      paraphrased question first — it's why we paused. */}
                  {isClarification && meta.question && (
                    <Card className="bg-amber-50 dark:bg-amber-950 border-amber-200 dark:border-amber-800">
                      <CardContent className="p-4">
                        <p className="text-xs font-semibold text-amber-700 dark:text-amber-200 mb-1">
                          Question to user
                        </p>
                        <p className="text-sm text-gray-800 dark:text-gray-100 whitespace-pre-wrap leading-relaxed">
                          {meta.question}
                        </p>
                      </CardContent>
                    </Card>
                  )}

                  {/* Message Content — rendered as Markdown so headings,
                      lists, and citations look like the result tab. */}
                  <div>
                    <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                      <MessageSquare className="h-4 w-4" />
                      {messageType === "task_assign" ? "Prompt" : "Output"}
                    </h4>
                    <Card className="bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                      <CardContent className="p-4">
                        <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                          <ReactMarkdown
                            components={{
                              h1: ({node, ...props}) => <h1 className="text-xl font-bold mt-4 mb-2" {...props} />,
                              h2: ({node, ...props}) => <h2 className="text-lg font-semibold mt-3 mb-2" {...props} />,
                              h3: ({node, ...props}) => <h3 className="text-base font-semibold mt-3 mb-2" {...props} />,
                              p: ({node, ...props}) => <p className="mb-2 leading-relaxed" {...props} />,
                              ul: ({node, ...props}) => <ul className="list-disc list-outside ml-5 mb-2 space-y-1" {...props} />,
                              ol: ({node, ...props}) => <ol className="list-decimal list-outside ml-5 mb-2 space-y-1" {...props} />,
                              li: ({node, ...props}) => <li className="leading-relaxed" {...props} />,
                              code: ({node, className, children, ...props}: any) => {
                                const inline = !(className || "").includes("language-");
                                return inline
                                  ? <code className="px-1 py-0.5 bg-gray-200 dark:bg-gray-800 rounded text-xs font-mono" {...props}>{children}</code>
                                  : <code className={className} {...props}>{children}</code>;
                              },
                              pre: ({node, ...props}) => <pre className="bg-gray-100 dark:bg-gray-950 p-3 rounded text-xs overflow-x-auto" {...props} />,
                              blockquote: ({node, ...props}) => <blockquote className="border-l-2 border-gray-400 pl-3 italic my-2 text-gray-700 dark:text-gray-300" {...props} />,
                            }}
                          >
                            {selectedMessage.content || ""}
                          </ReactMarkdown>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Tool call (legacy chat-flow metadata, kept for back-compat) */}
                  {meta.tool_name && (
                    <Card className="bg-purple-50 dark:bg-purple-950 border-purple-200 dark:border-purple-800">
                      <CardContent className="p-4 space-y-3">
                        <div className="flex items-center gap-2">
                          <Badge className="bg-purple-600 text-white">Tool Call</Badge>
                          <span className="font-mono text-sm font-semibold">{meta.tool_name}</span>
                        </div>
                        {meta.tool_input && (
                          <div>
                            <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">Input:</p>
                            <pre className="text-xs bg-white dark:bg-gray-900 p-3 rounded border overflow-x-auto">
                              {JSON.stringify(meta.tool_input, null, 2)}
                            </pre>
                          </div>
                        )}
                        {meta.tool_output && (
                          <div>
                            <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">Output:</p>
                            <pre className="text-xs bg-white dark:bg-gray-900 p-3 rounded border overflow-x-auto max-h-48">
                              {typeof meta.tool_output === "string"
                                ? meta.tool_output
                                : JSON.stringify(meta.tool_output, null, 2)}
                            </pre>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )}

                  {/* Other metadata, if any — kept compact, only shown when
                      the executor attached extra hints (e.g. order_index,
                      pattern). */}
                  {extraMeta.length > 0 && (
                    <details className="bg-gray-50 dark:bg-gray-900 border rounded p-3">
                      <summary className="text-xs font-semibold cursor-pointer">
                        More metadata
                      </summary>
                      <div className="mt-2 space-y-1">
                        {extraMeta.map(([key, value]) => (
                          <div key={key} className="text-xs">
                            <span className="font-mono font-semibold text-gray-700 dark:text-gray-300">{key}:</span>{" "}
                            <span className="text-gray-600 dark:text-gray-400">
                              {typeof value === "object"
                                ? <pre className="mt-1 bg-white dark:bg-gray-800 p-2 rounded text-xs overflow-x-auto">{JSON.stringify(value, null, 2)}</pre>
                                : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </ScrollArea>
            );
          })()}
        </DialogContent>
      </Dialog>
    </>
  );
}
