"use client";

import { useState } from "react";
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
} from "lucide-react";
import type { AgentMessage } from "@/lib/types";

interface MessageTimelineProps {
  messages: AgentMessage[];
}

const messageTypeConfig: Record<
  string,
  { icon: React.ElementType; color: string; bgColor: string }
> = {
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
                    {messageType.replace(/_/g, " ")}
                  </Badge>
                </div>

                <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2">
                  {msg.content}
                </p>

                <div className="mt-1.5 flex items-center justify-between">
                  <div className="text-[10px] text-gray-400">
                    {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ""}
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
        <DialogContent className="max-w-4xl max-h-[85vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Message Details
            </DialogTitle>
            <DialogDescription>
              Complete message information with technical details
            </DialogDescription>
          </DialogHeader>
          {selectedMessage && (
            <ScrollArea className="max-h-[65vh] pr-4">
              <div className="space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between pb-4 border-b">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <User className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                      <div>
                        <p className="font-semibold text-base">{selectedMessage.from_agent_name || "System"}</p>
                        {selectedMessage.from_agent_id && (
                          <p className="text-xs text-gray-400 font-mono">{selectedMessage.from_agent_id}</p>
                        )}
                      </div>
                    </div>
                    {selectedMessage.to_agent_name && (
                      <>
                        <ArrowRight className="h-5 w-5 text-gray-400" />
                        <div className="flex items-center gap-2">
                          <User className="h-5 w-5 text-green-600 dark:text-green-400" />
                          <div>
                            <p className="font-semibold text-base">{selectedMessage.to_agent_name}</p>
                            {selectedMessage.to_agent_id && (
                              <p className="text-xs text-gray-400 font-mono">{selectedMessage.to_agent_id}</p>
                            )}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Badge variant="outline" className="text-xs">
                      {(selectedMessage.message_type || "message").replace(/_/g, " ")}
                    </Badge>
                    {selectedMessage.timestamp && (
                      <span className="text-xs text-gray-500">
                        {new Date(selectedMessage.timestamp).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>

                {/* Message Content */}
                <div>
                  <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" />
                    Message Content
                  </h4>
                  <Card className="bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800">
                    <CardContent className="p-4">
                      <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap leading-relaxed">
                        {selectedMessage.content}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {/* Technical Details - Metadata */}
                {selectedMessage.metadata && Object.keys(selectedMessage.metadata).length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" />
                      Technical Details
                    </h4>
                    <div className="space-y-3">
                      {/* Tool Calls */}
                      {selectedMessage.metadata.tool_name && (
                        <Card className="bg-purple-50 dark:bg-purple-950 border-purple-200 dark:border-purple-800">
                          <CardContent className="p-4 space-y-3">
                            <div className="flex items-center gap-2">
                              <Badge className="bg-purple-600 text-white">Tool Call</Badge>
                              <span className="font-mono text-sm font-semibold">{selectedMessage.metadata.tool_name}</span>
                            </div>

                            {selectedMessage.metadata.tool_input && (
                              <div>
                                <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">Input Parameters:</p>
                                <pre className="text-xs bg-white dark:bg-gray-900 p-3 rounded border overflow-x-auto">
                                  {JSON.stringify(selectedMessage.metadata.tool_input, null, 2)}
                                </pre>
                              </div>
                            )}

                            {selectedMessage.metadata.tool_output && (
                              <div>
                                <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">Output:</p>
                                <pre className="text-xs bg-white dark:bg-gray-900 p-3 rounded border overflow-x-auto max-h-48">
                                  {typeof selectedMessage.metadata.tool_output === 'string'
                                    ? selectedMessage.metadata.tool_output
                                    : JSON.stringify(selectedMessage.metadata.tool_output, null, 2)}
                                </pre>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      )}

                      {/* All Other Metadata */}
                      {Object.keys(selectedMessage.metadata).filter(key =>
                        !['tool_name', 'tool_input', 'tool_output'].includes(key)
                      ).length > 0 && (
                        <Card className="bg-gray-50 dark:bg-gray-900">
                          <CardContent className="p-4">
                            <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">Additional Metadata:</p>
                            <div className="space-y-2">
                              {Object.entries(selectedMessage.metadata)
                                .filter(([key]) => !['tool_name', 'tool_input', 'tool_output'].includes(key))
                                .map(([key, value]) => (
                                  <div key={key} className="text-xs">
                                    <span className="font-mono font-semibold text-gray-700 dark:text-gray-300">{key}:</span>
                                    {' '}
                                    <span className="text-gray-600 dark:text-gray-400">
                                      {typeof value === 'object'
                                        ? <pre className="mt-1 bg-white dark:bg-gray-800 p-2 rounded text-xs overflow-x-auto">{JSON.stringify(value, null, 2)}</pre>
                                        : String(value)}
                                    </span>
                                  </div>
                                ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </div>
                  </div>
                )}

                {/* Raw Message Object (for debugging) */}
                <details className="border-t pt-4">
                  <summary className="text-xs font-semibold text-gray-500 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                    View Raw Message Data (Debug)
                  </summary>
                  <pre className="mt-2 text-xs bg-gray-100 dark:bg-gray-900 p-3 rounded overflow-x-auto border">
                    {JSON.stringify(selectedMessage, null, 2)}
                  </pre>
                </details>
              </div>
            </ScrollArea>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
