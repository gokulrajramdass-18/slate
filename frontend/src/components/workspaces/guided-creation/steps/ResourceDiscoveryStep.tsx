/**
 * Resource Discovery Step
 *
 * Shows discovered resources of a specific type and allows user to select which ones to include.
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from '@/lib/routing/navigation';
import { useGuidedCreationStore } from '@/lib/stores/guided-creation-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Database, Wrench, Bot, Users, CheckCircle, Sparkles, Plus, Link as LinkIcon, X } from 'lucide-react';
import { ResourceSelectionModal } from '../ResourceSelectionModal';
import { apiClient } from '@/lib/api/client';

type ResourceType = 'sources' | 'tools' | 'agents' | 'teams';

interface ResourceDiscoveryStepProps {
  resourceType: ResourceType;
}

export function ResourceDiscoveryStep({ resourceType }: ResourceDiscoveryStepProps) {
  const router = useRouter();
  const { discoveredResources, selectedResources, toggleResourceSelection } =
    useGuidedCreationStore();

  const [modalOpen, setModalOpen] = useState(false);
  const [modalResourceType, setModalResourceType] = useState<ResourceType>('sources');
  const [manuallySelectedResources, setManuallySelectedResources] = useState<{
    sources: any[];
    tools: any[];
    agents: any[];
    teams: any[];
  }>({
    sources: [],
    tools: [],
    agents: [],
    teams: [],
  });

  // Fetch details of manually selected resources
  useEffect(() => {
    fetchManuallySelectedResources();
  }, [selectedResources]);

  const fetchManuallySelectedResources = async () => {
    const newManual: typeof manuallySelectedResources = {
      sources: [],
      tools: [],
      agents: [],
      teams: [],
    };

    // Fetch sources
    if (selectedResources.source_ids.length > 0) {
      try {
        const response = await apiClient.get('/sources');
        const allSources = response.data;
        newManual.sources = allSources.filter((s: any) =>
          selectedResources.source_ids.includes(s.id) &&
          !discoveredResources.sources.find((d) => d.id === s.id)
        );
      } catch (error) {
        console.error('Failed to fetch sources:', error);
      }
    }

    // Fetch tools
    if (selectedResources.tool_ids.length > 0) {
      try {
        const [regResponse, mcpResponse] = await Promise.all([
          apiClient.get('/tools/registry'),
          apiClient.get('/tools/mcp'),
        ]);

        const allTools = [];
        const reg = regResponse.data;
        allTools.push(...reg.tools.map((t: any) => ({ ...t, id: `registry:${t.id}` })));

        const mcp = mcpResponse.data;
        allTools.push(...mcp.tools.map((t: any) => ({ ...t, id: `mcp:${t.id}` })));

        newManual.tools = allTools.filter((t: any) =>
          selectedResources.tool_ids.includes(t.id) &&
          !discoveredResources.tools.find((d) => d.id === t.id)
        );
      } catch (error) {
        console.error('Failed to fetch tools:', error);
      }
    }

    setManuallySelectedResources(newManual);
  };

  const handleAddNewSource = () => {
    // Open sources page in new tab
    window.open('/sources/new', '_blank');
  };

  const handleBrowseResources = (type: ResourceType) => {
    setModalResourceType(type);
    setModalOpen(true);
  };

  const handleModalConfirm = (selectedIds: string[]) => {
    // Map resource type to store key
    const typeMap: Record<ResourceType, 'source' | 'tool' | 'agent' | 'team'> = {
      sources: 'source',
      tools: 'tool',
      agents: 'agent',
      teams: 'team',
    };
    const storeType = typeMap[modalResourceType];

    // Update store - directly set the array
    const key = `${storeType}_ids` as keyof typeof selectedResources;
    useGuidedCreationStore.setState((state) => ({
      selectedResources: {
        ...state.selectedResources,
        [key]: selectedIds,
      },
    }));
  };

  const getCurrentSelectedIds = () => {
    const typeMap = {
      sources: 'source_ids',
      tools: 'tool_ids',
      agents: 'agent_ids',
      teams: 'team_ids',
    };
    const key = typeMap[modalResourceType] as keyof typeof selectedResources;
    return selectedResources[key];
  };

  const renderManualResourceCard = (
    resource: any,
    type: 'source' | 'tool' | 'agent' | 'team'
  ) => {
    const isSelected = selectedResources[`${type}_ids`].includes(resource.id);
    const name = resource.name || resource.title || 'Untitled';

    return (
      <Card
        key={resource.id}
        className="border-primary shadow-md"
      >
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Checkbox checked={true} disabled />
                <CardTitle className="text-base">{name}</CardTitle>
                <CheckCircle className="h-4 w-4 text-primary" />
                <Badge variant="outline" className="text-xs">Manually Added</Badge>
              </div>
              {resource.description && (
                <CardDescription className="mt-2 text-sm">
                  {resource.description.length > 150
                    ? `${resource.description.slice(0, 150)}...`
                    : resource.description}
                </CardDescription>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => toggleResourceSelection(type, resource.id)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Additional metadata */}
          {type === 'source' && resource.source_type && (
            <Badge variant="secondary" className="text-xs">
              {resource.source_type}
            </Badge>
          )}
          {type === 'tool' && resource.tool_type && (
            <Badge variant="secondary" className="text-xs">
              {resource.tool_type}
            </Badge>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderResourceCard = (
    resource: any,
    type: 'source' | 'tool' | 'agent' | 'team'
  ) => {
    const isSelected = selectedResources[`${type}_ids`].includes(resource.id);
    const scoreColor =
      resource.relevance_score >= 0.8
        ? 'text-green-600'
        : resource.relevance_score >= 0.6
        ? 'text-yellow-600'
        : 'text-gray-600';

    return (
      <Card
        key={resource.id}
        className={`cursor-pointer transition-all ${
          isSelected ? 'border-primary shadow-md' : 'border-border hover:border-primary/50'
        }`}
        onClick={() => toggleResourceSelection(type, resource.id)}
      >
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Checkbox checked={isSelected} />
                <CardTitle className="text-base">
                  {resource.name || resource.title || 'Untitled'}
                </CardTitle>
                {isSelected && <CheckCircle className="h-4 w-4 text-primary" />}
                {/* Type indicator for agents/teams */}
                {type === 'agent' && (
                  <Badge variant="outline" className="text-xs bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800">
                    <Bot className="w-3 h-3 mr-1" />
                    Agent
                  </Badge>
                )}
                {type === 'team' && (
                  <Badge variant="outline" className="text-xs bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800">
                    <Users className="w-3 h-3 mr-1" />
                    Team
                  </Badge>
                )}
              </div>
              {resource.description && (
                <CardDescription className="mt-2 text-sm">
                  {resource.description}
                </CardDescription>
              )}
            </div>
            <Badge variant="outline" className={scoreColor}>
              {Math.round(resource.relevance_score * 100)}%
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-2 text-sm">
            <Sparkles className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
            <p className="text-muted-foreground">{resource.relevance_reason}</p>
          </div>

          {/* Additional metadata */}
          {type === 'source' && resource.source_type && (
            <Badge variant="secondary" className="mt-3 text-xs">
              {resource.source_type}
            </Badge>
          )}
          {type === 'tool' && resource.tool_type && (
            <Badge variant="secondary" className="mt-3 text-xs">
              {resource.tool_type}
            </Badge>
          )}
          {type === 'agent' && resource.capabilities && (
            <div className="flex flex-wrap gap-1 mt-3">
              {resource.capabilities.slice(0, 3).map((cap: string, i: number) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {cap}
                </Badge>
              ))}
            </div>
          )}
          {type === 'team' && resource.member_count && (
            <p className="text-xs text-muted-foreground mt-3">
              {resource.member_count} members
            </p>
          )}
        </CardContent>
      </Card>
    );
  };

  // Get resources and config based on resource type
  const getResourceConfig = () => {
    switch (resourceType) {
      case 'sources':
        return {
          title: 'Select Data Sources',
          description: 'Choose the data sources you want to include in your workspace.',
          icon: Database,
          resources: discoveredResources.sources,
          manualResources: manuallySelectedResources.sources,
          selectedIds: selectedResources.source_ids,
          storeType: 'source' as const,
          emptyMessage: 'No data sources found matching your goal.',
          emptyHelp: 'You can add new sources or browse existing ones. Resources can be linked to your workspace later.',
          addNewAction: handleAddNewSource,
          addNewLabel: 'Add New Source',
          browseLabel: 'Browse Existing Sources',
        };
      case 'tools':
        return {
          title: 'Select Tools',
          description: 'Choose the tools and capabilities you want available in your workspace.',
          icon: Wrench,
          resources: discoveredResources.tools,
          manualResources: manuallySelectedResources.tools,
          selectedIds: selectedResources.tool_ids,
          storeType: 'tool' as const,
          emptyMessage: 'No tools found matching your goal.',
          emptyHelp: 'Tools provide capabilities like web search, data queries, and more. You can configure tools later.',
          addNewAction: () => window.open('/settings/mcp-servers', '_blank'),
          addNewLabel: 'Add New Tool',
          browseLabel: 'Browse Tools',
        };
      case 'agents':
        return {
          title: 'Select Agents or Teams',
          description: 'Choose AI agents or agent teams to help execute tasks in your workspace.',
          icon: Bot,
          resources: [...discoveredResources.agents, ...discoveredResources.teams],
          manualResources: [],
          selectedIds: [...selectedResources.agent_ids, ...selectedResources.team_ids],
          storeType: 'agent' as const,
          emptyMessage: 'No agents or teams found matching your goal.',
          emptyHelp: 'Agents can automate tasks and provide specialized capabilities. You can configure agents later.',
          addNewAction: () => window.open('/agents', '_blank'),
          addNewLabel: 'Create New Agent',
          browseLabel: 'Browse Agents',
        };
      default:
        return null;
    }
  };

  const config = getResourceConfig();
  if (!config) return null;

  const Icon = config.icon;
  const totalForType = config.resources.length;
  const selectedForType = config.selectedIds.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="p-3 bg-primary/10 rounded-lg">
          <Icon className="h-6 w-6 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold mb-2">{config.title}</h2>
          <p className="text-muted-foreground">{config.description}</p>
          {totalForType > 0 && (
            <p className="text-sm text-muted-foreground mt-2">
              We've found {totalForType} resource{totalForType !== 1 ? 's' : ''} that can help you achieve your goal.
            </p>
          )}
          {selectedForType > 0 && (
            <p className="text-sm font-medium text-primary mt-2">
              {selectedForType} selected
            </p>
          )}
        </div>
      </div>

      {/* Browse More Button */}
      {(config.resources.length > 0 || config.manualResources.length > 0) && (
        <div className="flex justify-end">
          <Button onClick={() => handleBrowseResources(resourceType)} variant="outline" size="sm">
            <LinkIcon className="h-4 w-4 mr-2" />
            {config.browseLabel}
          </Button>
        </div>
      )}

      {/* Resource List */}
      <div className="space-y-3">
        {/* Manually selected resources */}
        {config.manualResources.map((resource: any) =>
          renderManualResourceCard(resource, config.storeType)
        )}

        {/* Auto-discovered resources */}
        {config.resources.length > 0 ? (
          config.resources.map((resource: any) => {
            // Determine type for rendering
            const type = resource.type === 'team' ? 'team' : config.storeType;
            return renderResourceCard(resource, type);
          })
        ) : config.manualResources.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Icon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground mb-2">{config.emptyMessage}</p>
              <p className="text-sm text-muted-foreground mb-4">{config.emptyHelp}</p>
              <div className="flex gap-3 justify-center">
                <Button onClick={config.addNewAction} variant="default">
                  <Plus className="h-4 w-4 mr-2" />
                  {config.addNewLabel}
                </Button>
                <Button onClick={() => handleBrowseResources(resourceType)} variant="outline">
                  <LinkIcon className="h-4 w-4 mr-2" />
                  {config.browseLabel}
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}
      </div>

      {/* Skip Option */}
      {config.resources.length === 0 && config.manualResources.length === 0 && (
        <div className="text-center py-4">
          <p className="text-sm text-muted-foreground">
            You can skip this step and add {resourceType} later.
          </p>
        </div>
      )}

      {/* Resource Selection Modal */}
      <ResourceSelectionModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        resourceType={modalResourceType}
        selectedIds={getCurrentSelectedIds()}
        onConfirm={handleModalConfirm}
      />
    </div>
  );
}
