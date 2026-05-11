/**
 * My Templates Component - Redesigned
 *
 * Fancy template list with search and filtering
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
  Sparkles,
  Clock,
  Filter,
  ChevronDown,
  Eye,
  Globe,
  Lock,
  Users,
  Settings,
  TrendingUp,
  Workflow as WorkflowIcon,
  Calendar,
  FileText,
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

interface WorkflowTemplate {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  category?: string;
  source_workflow_id?: string;
  node_count: number;
  edge_count: number;
  parameter_count: number;
  version: number;
  is_public: boolean;
  tags: string[];
  usage_count: number;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// Template Card Component
// ============================================================================

interface TemplateCardProps {
  template: WorkflowTemplate;
  onExecute: (template: WorkflowTemplate) => void;
  onView: (template: WorkflowTemplate) => void;
  onSchedule: (template: WorkflowTemplate) => void;
}

function FancyMyTemplateCard({ template, onExecute, onView, onSchedule }: TemplateCardProps) {
  const visibilityColor = template.is_public
    ? 'from-purple-500 to-pink-500'
    : 'from-gray-500 to-slate-500';

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
        "bg-gradient-to-br transition-opacity duration-300",
        visibilityColor
      )} />

      {/* Visibility badge - top right */}
      <div className="absolute top-3 right-3 z-10">
        <Badge
          variant="secondary"
          className={cn(
            "bg-gradient-to-r shadow-lg backdrop-blur-sm",
            "border border-white/20 text-white font-semibold",
            visibilityColor
          )}
        >
          {template.is_public ? (
            <>
              <Globe className="h-3 w-3 mr-1" />
              Public
            </>
          ) : (
            <>
              <Lock className="h-3 w-3 mr-1" />
              Private
            </>
          )}
        </Badge>
      </div>

      <CardHeader className="space-y-3 pb-3 relative z-10">
        <CardTitle className="text-xl font-bold leading-tight line-clamp-2 group-hover:text-primary transition-colors">
          {template.name}
        </CardTitle>
        <CardDescription className="line-clamp-2 text-sm leading-relaxed">
          {template.description || "No description available"}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 relative z-10">
        {/* Stats grid */}
        <div className="grid grid-cols-3 gap-3">
          <div className="flex flex-col items-center p-2 rounded-lg bg-muted/50 backdrop-blur-sm">
            <WorkflowIcon className="h-4 w-4 mb-1 text-blue-500" />
            <span className="text-xs font-semibold">{template.node_count}</span>
            <span className="text-[10px] text-muted-foreground">Nodes</span>
          </div>
          <div className="flex flex-col items-center p-2 rounded-lg bg-muted/50 backdrop-blur-sm">
            <Users className="h-4 w-4 mb-1 text-purple-500" />
            <span className="text-xs font-semibold">{template.usage_count}</span>
            <span className="text-[10px] text-muted-foreground">Uses</span>
          </div>
          <div className="flex flex-col items-center p-2 rounded-lg bg-muted/50 backdrop-blur-sm">
            <Settings className="h-4 w-4 mb-1 text-orange-500" />
            <span className="text-xs font-semibold">{template.parameter_count}</span>
            <span className="text-[10px] text-muted-foreground">Params</span>
          </div>
        </div>

        {/* Tags */}
        {template.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {template.tags.slice(0, 4).map((tag) => (
              <Badge
                key={tag}
                variant="outline"
                className="text-xs px-2 py-0.5 bg-background/50 backdrop-blur-sm hover:bg-primary/10 transition-colors"
              >
                {tag}
              </Badge>
            ))}
            {template.tags.length > 4 && (
              <Badge
                variant="outline"
                className="text-xs px-2 py-0.5 bg-background/50 backdrop-blur-sm"
              >
                +{template.tags.length - 4}
              </Badge>
            )}
          </div>
        )}

        {/* Metadata */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground pt-2 border-t">
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            <span>v{template.version}</span>
          </div>
          <div className="flex items-center gap-1">
            <FileText className="h-3 w-3" />
            <span>Updated {new Date(template.updated_at).toLocaleDateString()}</span>
          </div>
        </div>
      </CardContent>

      <CardFooter className="flex gap-2 pt-4 relative z-10">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              className={cn(
                "flex-1 font-semibold shadow-md text-white",
                "hover:shadow-lg transition-all duration-200",
                "bg-gradient-to-r hover:scale-105",
                visibilityColor,
                template.is_public
                  ? "hover:from-purple-600 hover:to-pink-600"
                  : "hover:from-gray-600 hover:to-slate-600"
              )}
            >
              <Play className="h-4 w-4 mr-2" />
              Execute
              <ChevronDown className="h-4 w-4 ml-2" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={() => onExecute(template)}>
              <Play className="h-4 w-4 mr-2" />
              Execute Now
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onSchedule(template)}>
              <Calendar className="h-4 w-4 mr-2" />
              Schedule
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Button
          variant="outline"
          onClick={() => onView(template)}
          className="hover:bg-primary/10 hover:border-primary transition-all"
        >
          <Eye className="h-4 w-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}

// ============================================================================
// My Templates Component
// ============================================================================

interface MyTemplatesProps {
  templates: WorkflowTemplate[];
  isLoading: boolean;
  onExecute: (template: WorkflowTemplate) => void;
  onView: (template: WorkflowTemplate) => void;
  onSchedule: (template: WorkflowTemplate) => void;
}

export function MyTemplates({
  templates,
  isLoading,
  onExecute,
  onView,
  onSchedule
}: MyTemplatesProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterVisibility, setFilterVisibility] = useState<'all' | 'public' | 'private'>('all');
  const [sortBy, setSortBy] = useState<'popular' | 'recent' | 'name'>('recent');

  // Filter and sort templates
  const filteredTemplates = useMemo(() => {
    let filtered = templates;

    // Visibility filter
    if (filterVisibility === 'public') {
      filtered = filtered.filter(t => t.is_public);
    } else if (filterVisibility === 'private') {
      filtered = filtered.filter(t => !t.is_public);
    }

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(t =>
        t.name.toLowerCase().includes(query) ||
        t.description?.toLowerCase().includes(query) ||
        t.tags.some(tag => tag.toLowerCase().includes(query))
      );
    }

    // Sort
    filtered = [...filtered].sort((a, b) => {
      switch (sortBy) {
        case 'popular':
          return b.usage_count - a.usage_count;
        case 'recent':
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        case 'name':
          return a.name.localeCompare(b.name);
        default:
          return 0;
      }
    });

    return filtered;
  }, [templates, filterVisibility, searchQuery, sortBy]);

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-100 via-violet-100 to-purple-100 dark:from-indigo-900/30 dark:via-violet-900/30 dark:to-purple-900/30 p-8 shadow-lg border border-indigo-200 dark:border-indigo-800">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative z-10">
          <h2 className="text-3xl font-bold mb-2 flex items-center gap-2 text-gray-800 dark:text-gray-100">
            <Sparkles className="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
            My Templates
          </h2>
          <p className="text-gray-700 dark:text-gray-300 text-lg">
            Manage your reusable workflow templates
          </p>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
          <Input
            placeholder="Search templates by name, description, or tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 h-12 text-base border-2 focus:border-primary transition-all"
          />
        </div>

        {/* Filter Visibility */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="h-12 px-4 min-w-[140px] border-2">
              <Filter className="h-4 w-4 mr-2" />
              {filterVisibility === 'all' ? 'All' : filterVisibility === 'public' ? 'Public' : 'Private'}
              <ChevronDown className="h-4 w-4 ml-2" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setFilterVisibility('all')}>
              All Templates
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFilterVisibility('public')}>
              <Globe className="h-4 w-4 mr-2" />
              Public Only
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setFilterVisibility('private')}>
              <Lock className="h-4 w-4 mr-2" />
              Private Only
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Sort */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="h-12 px-4 min-w-[140px] border-2">
              <TrendingUp className="h-4 w-4 mr-2" />
              Sort: {sortBy === 'popular' ? 'Popular' : sortBy === 'recent' ? 'Recent' : 'Name'}
              <ChevronDown className="h-4 w-4 ml-2" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setSortBy('popular')}>
              <TrendingUp className="h-4 w-4 mr-2" />
              Most Popular
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setSortBy('recent')}>
              <Clock className="h-4 w-4 mr-2" />
              Most Recent
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setSortBy('name')}>
              <FileText className="h-4 w-4 mr-2" />
              Name (A-Z)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing <strong className="text-foreground">{filteredTemplates.length}</strong> template
          {filteredTemplates.length !== 1 ? 's' : ''}
          {searchQuery && <span> matching "<strong className="text-foreground">{searchQuery}</strong>"</span>}
        </span>
      </div>

      {/* Templates Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="h-[420px] animate-pulse">
              <CardHeader>
                <div className="h-6 bg-muted rounded w-3/4 mb-2" />
                <div className="h-4 bg-muted rounded w-full" />
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-2">
                    {[...Array(3)].map((_, j) => (
                      <div key={j} className="h-16 bg-muted rounded" />
                    ))}
                  </div>
                  <div className="h-4 bg-muted rounded w-2/3" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredTemplates.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map((template) => (
            <FancyMyTemplateCard
              key={template.id}
              template={template}
              onExecute={onExecute}
              onView={onView}
              onSchedule={onSchedule}
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
                {searchQuery ? 'No templates found' : 'No templates yet'}
              </h3>
              <p className="text-muted-foreground">
                {searchQuery
                  ? `No templates match "${searchQuery}". Try different keywords.`
                  : 'Create workflows and save them as templates'}
              </p>
            </div>
            {searchQuery && (
              <Button
                onClick={() => setSearchQuery('')}
                className={cn(
                  "mt-2 text-white font-semibold shadow-md",
                  "bg-gradient-to-r from-indigo-500 to-purple-500",
                  "hover:from-indigo-600 hover:to-purple-600",
                  "hover:shadow-lg transition-all duration-200 hover:scale-105"
                )}
              >
                Clear Search
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
