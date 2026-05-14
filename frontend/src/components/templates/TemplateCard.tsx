"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Database,
  FileSearch,
  FileText,
  BarChart3,
  Bell,
  Workflow,
  Globe,
  Lock,
  TrendingUp,
  Calendar,
  Play,
  Eye,
  Folder,
  Loader2,
} from "lucide-react";
import type { WorkspaceTemplate } from "@/lib/api/templates";
import { Link } from 'react-router-dom';
import { useQuery } from "@tanstack/react-query";
import { workspacesApi } from "@/lib/api/workspaces";

interface TemplateCardProps {
  template: WorkspaceTemplate;
  onInstantiate?: (templateId: string) => void;
  onSchedule?: (templateId: string) => void;
  isExecuting?: boolean;
}

const categoryIcons: Record<string, React.ElementType> = {
  data_pipeline: Database,
  research: FileSearch,
  reporting: FileText,
  monitoring: Bell,
  analysis: BarChart3,
  automation: Workflow,
  other: Workflow,
};

const categoryColors: Record<string, string> = {
  data_pipeline: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  research: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  reporting: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  monitoring: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  analysis: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300",
  automation: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300",
  other: "bg-gray-100 text-gray-700 dark:bg-gray-900 dark:text-gray-300",
};

export function TemplateCard({ template, onInstantiate, onSchedule, isExecuting = false }: TemplateCardProps) {
  const CategoryIcon = categoryIcons[template.category || "other"] || Workflow;
  const categoryColor = categoryColors[template.category || "other"];

  // Fetch source workspace name
  const { data: sourceWorkspace } = useQuery({
    queryKey: ["workspaces", template.source_workspace_id],
    queryFn: () => template.source_workspace_id ? workspacesApi.get(template.source_workspace_id) : null,
    enabled: !!template.source_workspace_id,
  });

  return (
    <Card className="group hover:shadow-lg transition-all duration-200 hover:border-primary/50">
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className={`p-2 rounded-lg ${categoryColor}`}>
              <CategoryIcon className="h-5 w-5" />
            </div>
            <div className="flex items-center gap-2">
              {template.is_public ? (
                <Globe className="h-4 w-4 text-blue-500" />
              ) : (
                <Lock className="h-4 w-4 text-gray-400" />
              )}
            </div>
          </div>
          {template.usage_count > 0 && (
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              <TrendingUp className="h-4 w-4" />
              <span>{template.usage_count}</span>
            </div>
          )}
        </div>

        <div>
          <CardTitle className="text-lg line-clamp-1 group-hover:text-primary transition-colors">
            {template.name}
          </CardTitle>
          {template.description && (
            <CardDescription className="line-clamp-2 mt-1.5">
              {template.description}
            </CardDescription>
          )}
          {sourceWorkspace && (
            <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
              <Folder className="h-3 w-3" />
              <span>From: {sourceWorkspace.name}</span>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="space-y-1">
            <p className="text-2xl font-bold text-primary">{template.phase_count}</p>
            <p className="text-xs text-muted-foreground">Phases</p>
          </div>
          <div className="space-y-1">
            <p className="text-2xl font-bold text-primary">{template.task_count}</p>
            <p className="text-xs text-muted-foreground">Tasks</p>
          </div>
          <div className="space-y-1">
            <p className="text-2xl font-bold text-primary">{template.parameter_count}</p>
            <p className="text-xs text-muted-foreground">Params</p>
          </div>
        </div>

        {/* Tags */}
        {template.tags && template.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {template.tags.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
            {template.tags.length > 3 && (
              <Badge variant="secondary" className="text-xs">
                +{template.tags.length - 3}
              </Badge>
            )}
          </div>
        )}

        {/* Category Badge */}
        {template.category && (
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={categoryColor}>
              {template.category.replace("_", " ")}
            </Badge>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex gap-2 border-t pt-4">
        <Link to={`/templates/${template.id}`} className="flex-1">
          <Button variant="outline" size="sm" className="w-full" disabled={isExecuting}>
            <Eye className="h-4 w-4 mr-2" />
            View
          </Button>
        </Link>
        {onInstantiate && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onInstantiate(template.id)}
            className="flex-1"
            disabled={isExecuting}
          >
            {isExecuting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Executing...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Run
              </>
            )}
          </Button>
        )}
        {onSchedule && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSchedule(template.id)}
            className="flex-1"
            disabled={isExecuting}
          >
            <Calendar className="h-4 w-4 mr-2" />
            Schedule
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
