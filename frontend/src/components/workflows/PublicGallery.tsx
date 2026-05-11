/**
 * Public Gallery Component - Redesigned
 *
 * Fancy template gallery with category segmentation and search
 */

'use client';

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Play,
  Eye,
  Search,
  Users,
  Sparkles,
  Zap,
  Brain,
  Database,
  FileText,
  Settings,
  TrendingUp,
  Star,
  Clock,
  ChevronDown,
  Filter,
  Calendar,
  Copy,
  Workflow as WorkflowIcon,
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
  consumed_by_user?: boolean;
}

// ============================================================================
// Category Configuration
// ============================================================================

const categories = [
  { id: 'all', name: 'All Templates', icon: Sparkles, color: 'from-purple-500 to-pink-500' },
  { id: 'data', name: 'Data Processing', icon: Database, color: 'from-blue-500 to-cyan-500' },
  { id: 'research', name: 'Research', icon: Brain, color: 'from-green-500 to-emerald-500' },
  { id: 'automation', name: 'Automation', icon: Zap, color: 'from-yellow-500 to-orange-500' },
  { id: 'content', name: 'Content Generation', icon: FileText, color: 'from-indigo-500 to-purple-500' },
  { id: 'analysis', name: 'Analysis', icon: TrendingUp, color: 'from-red-500 to-pink-500' },
  { id: 'other', name: 'Other', icon: Settings, color: 'from-gray-500 to-slate-500' },
];

// ============================================================================
// Template Card Component
// ============================================================================

interface TemplateCardProps {
  template: WorkflowTemplate;
  onExecute: (template: WorkflowTemplate) => void;
  onView: (template: WorkflowTemplate) => void;
  onSchedule: (template: WorkflowTemplate) => void;
}

function FancyTemplateCard({ template, onExecute, onView, onSchedule }: TemplateCardProps) {
  const category = categories.find(c => c.id === template.category) || categories[categories.length - 1];
  const CategoryIcon = category.icon;

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
        category.color
      )} />

      {/* Badges container - top right */}
      <div className="absolute top-3 right-3 z-10 flex flex-col items-end gap-2">
        {/* Category badge */}
        <Badge
          variant="secondary"
          className={cn(
            "bg-gradient-to-r shadow-lg backdrop-blur-sm",
            "border border-white/20",
            category.color,
            "text-white font-semibold"
          )}
        >
          <CategoryIcon className="h-3 w-3 mr-1" />
          {category.name}
        </Badge>

        {/* Consumed badge */}
        {template.consumed_by_user && (
          <Badge
            variant="secondary"
            className="bg-green-500/90 text-white border border-green-400/50 shadow-lg backdrop-blur-sm"
          >
            <Star className="h-3 w-3 mr-1 fill-white" />
            Used
          </Badge>
        )}
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
            <span>Updated {new Date(template.updated_at).toLocaleDateString()}</span>
          </div>
        </div>
      </CardContent>

      <CardFooter className="flex gap-2 pt-4 relative z-10">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              className={cn(
                "flex-1 font-semibold shadow-md",
                "hover:shadow-lg transition-all duration-200",
                "bg-gradient-to-r hover:scale-105",
                category.color
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
// Public Gallery Component
// ============================================================================

interface PublicGalleryProps {
  templates: WorkflowTemplate[];
  isLoading: boolean;
  onExecute: (template: WorkflowTemplate) => void;
  onView: (template: WorkflowTemplate) => void;
  onSchedule: (template: WorkflowTemplate) => void;
}

export function PublicGallery({
  templates,
  isLoading,
  onExecute,
  onView,
  onSchedule
}: PublicGalleryProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [sortBy, setSortBy] = useState<'popular' | 'recent' | 'name'>('popular');

  // Filter and sort templates
  const filteredTemplates = useMemo(() => {
    let filtered = templates;

    // Category filter
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(t => t.category === selectedCategory);
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
  }, [templates, selectedCategory, searchQuery, sortBy]);

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-purple-100 via-pink-100 to-rose-100 dark:from-purple-900/30 dark:via-pink-900/30 dark:to-rose-900/30 p-8 shadow-lg border border-purple-200 dark:border-purple-800">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative z-10">
          <h2 className="text-3xl font-bold mb-2 flex items-center gap-2 text-gray-800 dark:text-gray-100">
            <Sparkles className="h-8 w-8 text-purple-600 dark:text-purple-400" />
            Template Gallery
          </h2>
          <p className="text-gray-700 dark:text-gray-300 text-lg">
            Discover and use pre-built workflow templates from the community
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

        {/* Sort */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="h-12 px-4 min-w-[140px] border-2">
              <Filter className="h-4 w-4 mr-2" />
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

      {/* Category Pills */}
      <div className="flex flex-wrap gap-2">
        {categories.map((category) => {
          const Icon = category.icon;
          const isSelected = selectedCategory === category.id;

          return (
            <button
              key={category.id}
              onClick={() => setSelectedCategory(category.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 rounded-full font-medium transition-all duration-200",
                "border-2 hover:scale-105 hover:shadow-md",
                isSelected
                  ? cn(
                      "bg-gradient-to-r text-white shadow-lg border-transparent",
                      category.color
                    )
                  : "bg-background border-border hover:border-primary/50"
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{category.name}</span>
              <Badge
                variant="secondary"
                className={cn(
                  "ml-1",
                  isSelected ? "bg-white/20 text-white" : ""
                )}
              >
                {category.id === 'all'
                  ? templates.length
                  : templates.filter(t => t.category === category.id).length
                }
              </Badge>
            </button>
          );
        })}
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
            <FancyTemplateCard
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
              <Search className="h-12 w-12 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-xl font-semibold mb-2">No templates found</h3>
              <p className="text-muted-foreground">
                {searchQuery
                  ? `No templates match "${searchQuery}". Try different keywords.`
                  : "No templates available in this category yet."}
              </p>
            </div>
            {searchQuery && (
              <Button
                variant="outline"
                onClick={() => setSearchQuery('')}
                className="mt-2"
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
