"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Brain,
  Search,
  PenTool,
  Eye,
  Lightbulb,
  Cog,
  Loader2,
  CheckCircle2,
  Clock,
  XCircle,
  Database,
  Code,
  TestTube,
  Palette,
  Network,
  Award,
} from "lucide-react";
import type { Agent, AgentRole, AgentStatus } from "@/lib/types";

interface AgentCardProps {
  agent: Agent;
  isActive?: boolean;
  currentTask?: string;
  progress?: number;
}

const roleIcons: Record<AgentRole, React.ElementType> = {
  planner: Lightbulb,
  researcher: Search,
  analyst: Brain,
  data_scientist: Database,
  writer: PenTool,
  developer: Code,
  tester: TestTube,
  designer: Palette,
  reviewer: Eye,
  judge: Award,
  coordinator: Network,
  custom: Cog,
};

const roleColors: Record<AgentRole, string> = {
  planner: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  researcher: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  analyst: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  data_scientist: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300",
  writer: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  developer: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300",
  tester: "bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300",
  designer: "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300",
  reviewer: "bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-300",
  judge: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  coordinator: "bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300",
  custom: "bg-gray-100 text-gray-700 dark:bg-gray-900 dark:text-gray-300",
};

const statusConfig: Record<AgentStatus, { icon: React.ElementType; color: string; label: string }> = {
  idle: { icon: Clock, color: "text-gray-400", label: "Idle" },
  working: { icon: Loader2, color: "text-blue-500", label: "Working" },
  waiting: { icon: Clock, color: "text-amber-500", label: "Waiting" },
  completed: { icon: CheckCircle2, color: "text-green-500", label: "Done" },
  error: { icon: XCircle, color: "text-red-500", label: "Error" },
};

export function AgentCard({ agent, isActive, currentTask, progress }: AgentCardProps) {
  const RoleIcon = roleIcons[agent.role] || Cog;
  const statusInfo = statusConfig[agent.status];
  const StatusIcon = statusInfo.icon;

  return (
    <Card
      className={`transition-all duration-200 ${
        isActive
          ? "ring-2 ring-blue-500 dark:ring-blue-400 shadow-md"
          : "hover:shadow-sm"
      } ${agent.status === "error" ? "border-red-300 dark:border-red-700" : ""}`}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className={`p-2 rounded-lg ${roleColors[agent.role]}`}>
              <RoleIcon className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-sm">{agent.name}</CardTitle>
              <p className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                {agent.role}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <StatusIcon
              className={`h-4 w-4 ${statusInfo.color} ${
                agent.status === "working" ? "animate-spin" : ""
              }`}
            />
            <span className={`text-xs font-medium ${statusInfo.color}`}>
              {statusInfo.label}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2">
          {agent.description}
        </p>

        {currentTask && (
          <div className="text-xs bg-blue-50 dark:bg-blue-950 p-2 rounded-md border border-blue-100 dark:border-blue-900">
            <span className="font-medium text-blue-700 dark:text-blue-300">
              Current:
            </span>{" "}
            <span className="text-blue-600 dark:text-blue-400">{currentTask}</span>
          </div>
        )}

        {progress !== undefined && agent.status === "working" && (
          <Progress value={progress} className="h-1.5" />
        )}

        {agent.tools && agent.tools.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {agent.tools.slice(0, 3).map((tool) => (
              <Badge key={tool} variant="outline" className="text-[10px] px-1.5 py-0">
                {tool}
              </Badge>
            ))}
            {agent.tools.length > 3 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                +{agent.tools.length - 3}
              </Badge>
            )}
          </div>
        )}

        {agent.model && (
          <p className="text-[10px] text-gray-400 dark:text-gray-500">
            Model: {agent.model}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
