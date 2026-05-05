/**
 * Resource Selection Modal
 *
 * Modal for browsing and selecting existing resources (sources, tools, agents, teams)
 * to add to the guided workspace creation wizard.
 */

'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Search, Database, Wrench, Bot, Users } from 'lucide-react';
import { toast } from 'sonner';

type ResourceType = 'sources' | 'tools' | 'agents' | 'teams';

interface ResourceSelectionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  resourceType: ResourceType;
  selectedIds: string[];
  onConfirm: (selectedIds: string[]) => void;
}

export function ResourceSelectionModal({
  open,
  onOpenChange,
  resourceType,
  selectedIds,
  onConfirm,
}: ResourceSelectionModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [localSelectedIds, setLocalSelectedIds] = useState<string[]>(selectedIds);
  const [resources, setResources] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Load resources when modal opens
  useEffect(() => {
    if (open) {
      setLocalSelectedIds(selectedIds);
      loadResources();
    }
  }, [open, resourceType, selectedIds]);

  const loadResources = async () => {
    setIsLoading(true);
    try {
      let data: any[] = [];

      if (resourceType === 'sources') {
        const response = await fetch('/api/sources');
        if (response.ok) {
          const json = await response.json();
          // API returns array directly, not wrapped
          data = Array.isArray(json) ? json : [];
        }
      } else if (resourceType === 'tools') {
        // Fetch from tool registry and MCP tools
        const [registryResponse, mcpResponse] = await Promise.all([
          fetch('/api/tools/registry'),
          fetch('/api/tools/mcp'),
        ]);

        if (registryResponse.ok) {
          const registry = await registryResponse.json();
          data = [
            ...data,
            ...(registry.tools || []).map((t: any) => ({
              ...t,
              id: `registry:${t.id}`,
            })),
          ];
        }

        if (mcpResponse.ok) {
          const mcp = await mcpResponse.json();
          data = [
            ...data,
            ...(mcp.tools || []).map((t: any) => ({
              ...t,
              id: `mcp:${t.id}`,
            })),
          ];
        }
      } else if (resourceType === 'agents') {
        const response = await fetch('/api/standalone-agents');
        if (response.ok) {
          const json = await response.json();
          data = json.agents || [];
        }
      } else if (resourceType === 'teams') {
        const response = await fetch('/api/agent-teams');
        if (response.ok) {
          const json = await response.json();
          data = json.teams || [];
        }
      }

      setResources(data);
    } catch (error) {
      console.error(`Failed to load ${resourceType}:`, error);
      toast.error(`Failed to load ${resourceType}`);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredResources = resources.filter((resource) => {
    const searchableText = `${resource.name || resource.title || ''} ${resource.description || ''}`.toLowerCase();
    return searchableText.includes(searchQuery.toLowerCase());
  });

  const toggleSelection = (id: string) => {
    setLocalSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleConfirm = () => {
    onConfirm(localSelectedIds);
    onOpenChange(false);
  };

  const getResourceIcon = () => {
    switch (resourceType) {
      case 'sources':
        return Database;
      case 'tools':
        return Wrench;
      case 'agents':
        return Bot;
      case 'teams':
        return Users;
    }
  };

  const getResourceTitle = () => {
    switch (resourceType) {
      case 'sources':
        return 'Select Data Sources';
      case 'tools':
        return 'Select Tools';
      case 'agents':
        return 'Select Agents';
      case 'teams':
        return 'Select Teams';
    }
  };

  const Icon = getResourceIcon();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon className="h-5 w-5" />
            {getResourceTitle()}
          </DialogTitle>
          <DialogDescription>
            Browse and select {resourceType} to add to your workspace
          </DialogDescription>
        </DialogHeader>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={`Search ${resourceType}...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Resource List */}
        <ScrollArea className="h-[400px] pr-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-40">
              <p className="text-muted-foreground">Loading...</p>
            </div>
          ) : filteredResources.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40">
              <Icon className="h-12 w-12 text-muted-foreground mb-2" />
              <p className="text-muted-foreground">
                {searchQuery ? `No ${resourceType} found` : `No ${resourceType} available`}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredResources.map((resource) => {
                const id = resource.id;
                const isSelected = localSelectedIds.includes(id);
                const name = resource.name || resource.title || 'Untitled';
                const description = resource.description || resource.role || '';

                return (
                  <div
                    key={id}
                    className={`p-4 border rounded-lg cursor-pointer transition-all hover:border-primary/50 ${
                      isSelected ? 'border-primary bg-primary/5' : 'border-border'
                    }`}
                    onClick={() => toggleSelection(id)}
                  >
                    <div className="flex items-start gap-3">
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => toggleSelection(id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <div className="flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <h4 className="font-medium">{name}</h4>
                            {description && (
                              <p className="text-sm text-muted-foreground mt-1">
                                {description.length > 150
                                  ? `${description.slice(0, 150)}...`
                                  : description}
                              </p>
                            )}
                          </div>
                          {/* Type badges */}
                          <div className="flex gap-1">
                            {resourceType === 'sources' && resource.source_type && (
                              <Badge variant="secondary" className="text-xs">
                                {resource.source_type}
                              </Badge>
                            )}
                            {resourceType === 'tools' && resource.tool_type && (
                              <Badge variant="secondary" className="text-xs">
                                {resource.tool_type}
                              </Badge>
                            )}
                            {resourceType === 'tools' && resource.source && (
                              <Badge variant="outline" className="text-xs">
                                {resource.source}
                              </Badge>
                            )}
                            {resourceType === 'agents' && resource.status && (
                              <Badge
                                variant={resource.status === 'active' ? 'default' : 'secondary'}
                                className="text-xs"
                              >
                                {resource.status}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>

        <DialogFooter className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {localSelectedIds.length} selected
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleConfirm}>
              Add Selected ({localSelectedIds.length})
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
