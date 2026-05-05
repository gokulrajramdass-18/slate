"use client";

import { formatRelativeTime } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MessageSquare, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatSession } from "@/lib/types";

interface ChatSessionListProps {
  sessions: ChatSession[];
  selectedId?: string;
  onSelect: (id: string) => void;
  onDelete?: (id: string) => void;
}

export function ChatSessionList({ sessions, selectedId, onSelect, onDelete }: ChatSessionListProps) {
  const handleDelete = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (onDelete) {
      onDelete(sessionId);
    }
  };

  if (sessions.length === 0) {
    return (
      <Card className="h-full">
        <CardContent className="flex flex-col items-center justify-center h-full py-12">
          <MessageSquare className="w-12 h-12 text-gray-400 mb-3" />
          <p className="text-gray-500 text-center">No chat sessions yet</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {sessions.map((session) => (
        <Card
          key={session.id}
          className={cn(
            "cursor-pointer transition-all hover:shadow-md",
            selectedId === session.id
              ? "border-primary-600 ring-2 ring-primary-600 ring-opacity-50"
              : ""
          )}
          onClick={() => onSelect(session.id)}
        >
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0" onClick={() => onSelect(session.id)}>
                <h3 className="font-medium truncate">
                  {session.title || "New Chat"}
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  {formatRelativeTime(session.updated)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {session.workspace_name && (
                  <Badge variant="outline" className="text-xs">
                    {session.workspace_name}
                  </Badge>
                )}
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => handleDelete(e, session.id)}
                    className="h-8 w-8 p-0 hover:bg-red-100 hover:text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
