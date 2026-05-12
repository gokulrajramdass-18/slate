/**
 * My Workflows Component - Redesigned
 *
 * Fancy workflow list with search and filtering
 */

'use client';

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Play,
  Search,
  Calendar,
  Sparkles,
  Clock,
  Filter,
  ChevronDown,
  Pencil,
  Trash2,
  Copy,
  MoreVertical,
  Workflow as WorkflowIcon,
  TrendingUp,
  Globe,
  CheckCircle2,
  Circle,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

interface WorkflowSummary {
  id: string;
  name: string;
  description?: string;
  node_count: number;
  edge_count: number;
  is_active: boolean;
  tags: string[];
  created_by: string;
  updated_at?: string;
  source_template?: {
    template_id: string;
    template_name: string;
    template_is_public: boolean;
  };
}

// ============================================================================
// Workflow Card Component
// ============================================================================

interface WorkflowCardProps {
  workflow: WorkflowSummary;
  onEdit: (id: string) => void;
  onExecute: (id: string) => void;
  onSchedule: (id: string) => void;
  onSaveAsTemplate: (id: string) => void;
  onDelete: (id: string) => void;
}

function FancyWorkflowCard({
  workflow,
  onEdit,
  onExecute,
  onSchedule,
  onSaveAsTemplate,
  onDelete
}: WorkflowCardProps) {
  return (
    <Card className={cn(
      "group relative overflow-hidden",
      "hover:shadow-2xl hover:scale-[1.02]",
      "transition-all duration-300 ease-out",
      "border-2 hover:border-primary/50",
      "bg-gradient-to-br from-background via-background to-muted/20"
    )}>
      {/* Gradient overlay on hover */}
      <div className={cn(
        "absolute inset-0 opacity-0 group-hover:opacity-10",
        "bg-gradient-to-br from-blue-500 to-purple-500 transition-opacity duration-300"
      )} />

      {/* Status badge - top right */}
      <div className="absolute top-3 right-3 z-10 flex flex-col items-end gap-2 max-w-[40%]">
        <Badge
          variant="secondary"
          className={cn(
            "shadow-lg backdrop-blur-sm border text-xs",
            workflow.is_active
              ? "bg-green-500/90 text-white border-green-400/50"
              : "bg-gray-500/90 text-white border-gray-400/50"
          )}
        >
          {workflow.is_active ? (
            <>
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Active
            </>
          ) : (
            <>
              <Circle className="h-3 w-3 mr-1" />
              Inactive
            </>
          )}
        </Badge>

        {/* From Gallery badge */}
        {workflow.source_template?.template_is_public && (
          <Badge
            variant="secondary"
            className="bg-purple-500/90 text-white border-purple-400/50 shadow-lg backdrop-blur-sm text-xs"
          >
            <Globe className="h-3 w-3 mr-1" />
            Gallery
          </Badge>
        )}
      </div>

      {/* Actions dropdown - top left */}
      <div className="absolute top-3 left-3 z-20">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="secondary"
              size="icon"
              className="h-8 w-8 shadow-lg"
              onClick={(e) => e.stopPropagation()}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-48">
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                onEdit(workflow.id);
              }}
            >
              <Pencil className="h-4 w-4 mr-2" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                onSchedule(workflow.id);
              }}
            >
              <Calendar className="h-4 w-4 mr-2" />
              Schedules
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                onSaveAsTemplate(workflow.id);
              }}
            >
              <Copy className="h-4 w-4 mr-2" />
              Save as Template
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                onDelete(workflow.id);
              }}
              className="text-destructive focus:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <CardHeader className="space-y-3 pb-3 relative z-10 pt-16 pr-20">
        <CardTitle className="text-xl font-bold leading-tight line-clamp-2 group-hover:text-primary transition-colors">
          {workflow.name}
        </CardTitle>
        {workflow.description && (
          <CardDescription className="line-clamp-2 text-sm leading-relaxed">
            {workflow.description}
          </CardDescription>
        )}
      </CardHeader>

      <CardContent className="space-y-4 relative z-10">
        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col items-center p-2 rounded-lg bg-muted/50 backdrop-blur-sm">
            <WorkflowIcon className="h-4 w-4 mb-1 text-blue-500" />
            <span className="text-xs font-semibold">{workflow.node_count}</span>
            <span className="text-[10px] text-muted-foreground">Nodes</span>
          </div>
          <div className="flex flex-col items-center p-2 rounded-lg bg-muted/50 backdrop-blur-sm">
            <TrendingUp className="h-4 w-4 mb-1 text-purple-500" />
            <span className="text-xs font-semibold">{workflow.edge_count}</span>
            <span className="text-[10px] text-muted-foreground">Edges</span>
          </div>
        </div>

        {/* Tags */}
        {workflow.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {workflow.tags.slice(0, 4).map((tag) => (
              <Badge
                key={tag}
                variant="outline"
                className="text-xs px-2 py-0.5 bg-background/50 backdrop-blur-sm hover:bg-primary/10 transition-colors"
              >
                {tag}
              </Badge>
            ))}
            {workflow.tags.length > 4 && (
              <Badge
                variant="outline"
                className="text-xs px-2 py-0.5 bg-background/50 backdrop-blur-sm"
              >
                +{workflow.tags.length - 4}
              </Badge>
            )}
          </div>
        )}

        {/* Metadata */}
        {workflow.source_template && (
          <div className="text-xs text-muted-foreground truncate pt-2 border-t">
            From: <span className="font-medium">{workflow.source_template.template_name}</span>
          </div>
        )}

        {workflow.updated_at && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>Updated {new Date(workflow.updated_at).toLocaleDateString()}</span>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex gap-2 pt-4 relative z-10">
        <Button
          onClick={() => onEdit(workflow.id)}
          className={cn(
            "flex-1 font-semibold shadow-md",
            "hover:shadow-lg transition-all duration-200",
            "bg-gradient-to-r from-gray-500 to-slate-500 hover:scale-105",
            "hover:from-gray-600 hover:to-slate-600",
            "text-white"
          )}
        >
          <Pencil className="h-4 w-4 mr-2" />
          Edit
        </Button>

        <Button
          variant="outline"
          onClick={() => onExecute(workflow.id)}
          className="hover:bg-primary/10 hover:border-primary transition-all"
        >
          <Play className="h-4 w-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}

// ============================================================================
// My Workflows Component
// ============================================================================

interface MyWorkflowsProps {
  workflows: WorkflowSummary[];
  isLoading: boolean;
  onEdit: (id: string) => void;
  onExecute: (id: string) => void;
  onSchedule: (id: string) => void;
  onSaveAsTemplate: (id: string) => void;
  onDelete: (id: string) => void;
  onCreateNew: () => void;
}

export function MyWorkflows({
  workflows,
  isLoading,
  onEdit,
  onExecute,
  onSchedule,
  onSaveAsTemplate,
  onDelete,
  onCreateNew
}: MyWorkflowsProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'inactive'>('all');
  const [sortBy, setSortBy] = useState<'recent' | 'name' | 'nodes'>('recent');

  // Filter and sort workflows
  const filteredWorkflows = useMemo(() => {
    let filtered = workflows;

    // Status filter
    if (filterStatus === 'active') {
      filtered = filtered.filter(w => w.is_active);
    } else if (filterStatus === 'inactive') {
      filtered = filtered.filter(w => !w.is_active);
    }

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(w =>
        w.name.toLowerCase().includes(query) ||
        w.description?.toLowerCase().includes(query) ||
        w.tags.some(tag => tag.toLowerCase().includes(query))
      );
    }

    // Sort
    filtered = [...filtered].sort((a, b) => {
      switch (sortBy) {
        case 'recent':
          return new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime();
        case 'name':
          return a.name.localeCompare(b.name);
        case 'nodes':
          return b.node_count - a.node_count;
        default:
          return 0;
      }
    });

    return filtered;
  }, [workflows, filterStatus, searchQuery, sortBy]);

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-blue-100 via-indigo-100 to-purple-100 dark:from-blue-900/30 dark:via-indigo-900/30 dark:to-purple-900/30 p-8 shadow-lg border border-blue-200 dark:border-blue-800">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative z-10">
          <h2 className="text-3xl font-bold mb-2 flex items-center gap-2 text-gray-800 dark:text-gray-100">
            <Sparkles className="h-8 w-8 text-blue-600 dark:text-blue-400" />
            My Workflows
          </h2>
          <p className="text-gray-700 dark:text-gray-300 text-lg">
            Manage and execute your custom workflow automations
          </p>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
          <Input
            placeholder="Search workflows by name, description, or tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 h-12 text-base border-2 focus:border-primary transition-all"
          />
        </div>

        {/* Filter Status */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="h-12 px-4 min-w-[140px] border-2">
              <Filter className="h-4 w-4 mr-2" />
              {filterStatus === 'all' ? 'All' : filterStatus === 'active' ? 'Active' : 'Inactive'}
              <ChevronDown className="h-4 w-4 ml-2" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setFilterStatus('all')}>
              All Workflows
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFilterStatus('active')}>
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Active Only
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFilterStatus('inactive')}>
              <Circle className="h-4 w-4 mr-2" />
              Inactive Only
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Sort */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="h-12 px-4 min-w-[140px] border-2">
              <TrendingUp className="h-4 w-4 mr-2" />
              Sort: {sortBy === 'recent' ? 'Recent' : sortBy === 'name' ? 'Name' : 'Size'}
              <ChevronDown className="h-4 w-4 ml-2" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setSortBy('recent')}>
              <Clock className="h-4 w-4 mr-2" />
              Most Recent
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setSortBy('name')}>
              <WorkflowIcon className="h-4 w-4 mr-2" />
              Name (A-Z)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setSortBy('nodes')}>
              <TrendingUp className="h-4 w-4 mr-2" />
              By Size
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing <strong className="text-foreground">{filteredWorkflows.length}</strong> workflow
          {filteredWorkflows.length !== 1 ? 's' : ''}
          {searchQuery && <span> matching "<strong className="text-foreground">{searchQuery}</strong>"</span>}
        </span>
      </div>

      {/* Workflows Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="h-[400px] animate-pulse">
              <CardHeader>
                <div className="h-6 bg-muted rounded w-3/4 mb-2" />
                <div className="h-4 bg-muted rounded w-full" />
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    {[...Array(2)].map((_, j) => (
                      <div key={j} className="h-16 bg-muted rounded" />
                    ))}
                  </div>
                  <div className="h-4 bg-muted rounded w-2/3" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredWorkflows.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredWorkflows.map((workflow) => (
            <FancyWorkflowCard
              key={workflow.id}
              workflow={workflow}
              onEdit={onEdit}
              onExecute={onExecute}
              onSchedule={onSchedule}
              onSaveAsTemplate={onSaveAsTemplate}
              onDelete={onDelete}
            />
          ))}
        </div>
      ) : (
        <Card className="p-12 text-center border-2 border-dashed">
          <div className="flex flex-col items-center gap-4">
            <div className="rounded-full bg-muted p-6">
              <WorkflowIcon className="h-12 w-12 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-xl font-semibold mb-2">
                {searchQuery ? 'No workflows found' : 'No workflows yet'}
              </h3>
              <p className="text-muted-foreground">
                {searchQuery
                  ? `No workflows match "${searchQuery}". Try different keywords.`
                  : 'Create your first workflow to get started'}
              </p>
            </div>
            <Button
              onClick={searchQuery ? () => setSearchQuery('') : onCreateNew}
              className={cn(
                "mt-2 text-white font-semibold shadow-md",
                "bg-gradient-to-r from-gray-500 to-slate-500",
                "hover:from-gray-600 hover:to-slate-600",
                "hover:shadow-lg transition-all duration-200 hover:scale-105"
              )}
            >
              {searchQuery ? 'Clear Search' : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Create Workflow
                </>
              )}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
