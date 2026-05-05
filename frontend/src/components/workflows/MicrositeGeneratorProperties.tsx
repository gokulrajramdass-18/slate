/**
 * Microsite Generator Properties Panel
 *
 * Configuration form for microsite_generator node type.
 * Allows users to configure microsite creation from notebook sources.
 */

'use client';

import React from 'react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { X, Plus } from 'lucide-react';
import { VariableReferenceHelper } from './VariableReferenceHelper';
import { useGraphStore } from '@/lib/stores/graph-store';

interface MicrositeGeneratorPropertiesProps {
  nodeId: string;
}

export function MicrositeGeneratorProperties({ nodeId }: MicrositeGeneratorPropertiesProps) {
  const nodes = useGraphStore((state) => state.nodes);
  const node = nodes.find((n) => n.id === nodeId);

  if (!node) return null;

  const config = node.data.config || {};

  const updateConfig = (updates: Record<string, any>) => {
    // Get the setNodes function from React Flow (stored in store by GraphEditor)
    const setNodesFromReactFlow = (useGraphStore.getState() as any).__setNodesFromReactFlow;

    if (setNodesFromReactFlow) {
      setNodesFromReactFlow((nds: any[]) => {
        const updatedNodes = nds.map((n: any) => {
          if (n.id === nodeId) {
            // Build updated data from the CURRENT node state
            const currentData = n.data;
            const updatedData = {
              ...currentData,
              config: { ...currentData.config, ...updates },
            };
            return { ...n, data: updatedData };
          }
          return n;
        });

        // Also update Zustand store immediately
        requestAnimationFrame(() => {
          useGraphStore.getState().setNodes(updatedNodes);
        });

        return updatedNodes;
      });
    }
  };

  // Get previous nodes for source selection
  const previousNodes = nodes.filter(
    (n) => n.id !== nodeId && n.data.type !== 'output'
  );

  // Handle microsite source IDs
  const micrositeSourceIds = config.microsite_source_ids || [];
  const [newSourceId, setNewSourceId] = React.useState('');

  const addSourceId = () => {
    if (newSourceId.trim() && !micrositeSourceIds.includes(newSourceId.trim())) {
      updateConfig({ microsite_source_ids: [...micrositeSourceIds, newSourceId.trim()] });
      setNewSourceId('');
    }
  };

  const removeSourceId = (id: string) => {
    updateConfig({ microsite_source_ids: micrositeSourceIds.filter((sid: string) => sid !== id) });
  };

  // Available templates (hardcoded for now, could be fetched from API)
  const templates = [
    { id: 'landing-page', name: 'Landing Page' },
    { id: 'documentation', name: 'Documentation' },
    { id: 'dashboard', name: 'Dashboard' },
    { id: 'blog', name: 'Blog' },
    { id: 'portfolio', name: 'Portfolio' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Microsite Generator Configuration</h3>
        <VariableReferenceHelper currentNodeId={nodeId} />
      </div>

      {/* Microsite Title */}
      <div className="space-y-1.5">
        <Label htmlFor="microsite-title">
          Microsite Title <span className="text-red-500">*</span>
        </Label>
        <Input
          id="microsite-title"
          value={config.microsite_title || ''}
          onChange={(e) => updateConfig({ microsite_title: e.target.value })}
          placeholder="e.g., Dashboard for {{quarter}}"
        />
        <p className="text-xs text-muted-foreground">
          Supports {'{{variable}}'} syntax
        </p>
      </div>

      {/* Microsite Description */}
      <div className="space-y-1.5">
        <Label htmlFor="microsite-description">Microsite Description</Label>
        <Textarea
          id="microsite-description"
          value={config.microsite_description || ''}
          onChange={(e) => updateConfig({ microsite_description: e.target.value })}
          placeholder="Optional description"
          rows={3}
        />
      </div>

      {/* Template */}
      <div className="space-y-1.5">
        <Label htmlFor="template-id">
          Template <span className="text-red-500">*</span>
        </Label>
        <Select
          value={config.template_id || ''}
          onValueChange={(value) => updateConfig({ template_id: value })}
        >
          <SelectTrigger id="template-id">
            <SelectValue placeholder="Select template" />
          </SelectTrigger>
          <SelectContent>
            {templates.map((template) => (
              <SelectItem key={template.id} value={template.id}>
                {template.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="border-t pt-4" />

      {/* Auto-Create Notebook */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="auto-create-notebook">Auto-Create Notebook</Label>
          <Select
            value={config.auto_create_notebook === false ? 'false' : 'true'}
            onValueChange={(value) => updateConfig({ auto_create_notebook: value === 'true' })}
          >
            <SelectTrigger id="auto-create-notebook" className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">Yes</SelectItem>
              <SelectItem value="false">No</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <p className="text-xs text-muted-foreground">
          Create notebook automatically if notebook_id not provided or doesn't exist
        </p>
      </div>

      {/* Notebook ID Template */}
      <div className="space-y-1.5">
        <Label htmlFor="notebook-id">Notebook ID</Label>
        <Input
          id="notebook-id"
          value={config.notebook_id_template || ''}
          onChange={(e) => updateConfig({ notebook_id_template: e.target.value })}
          placeholder="e.g., {{notebook_id}} or leave empty for auto-create"
        />
        <p className="text-xs text-muted-foreground">
          Reference previous notebook or leave empty to auto-create
        </p>
      </div>

      {/* Auto Notebook Description */}
      {config.auto_create_notebook !== false && (
        <div className="space-y-1.5">
          <Label htmlFor="auto-notebook-desc">Auto-Created Notebook Description</Label>
          <Textarea
            id="auto-notebook-desc"
            value={config.auto_notebook_description || ''}
            onChange={(e) => updateConfig({ auto_notebook_description: e.target.value })}
            placeholder="Description for auto-created notebook"
            rows={2}
          />
        </div>
      )}

      <div className="border-t pt-4" />

      {/* Source Mode */}
      <div className="space-y-1.5">
        <Label htmlFor="source-mode">Source Resolution Mode</Label>
        <Select
          value={config.microsite_source_mode || 'from_notebook'}
          onValueChange={(value) => updateConfig({ microsite_source_mode: value })}
        >
          <SelectTrigger id="source-mode">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="from_notebook">From Notebook</SelectItem>
            <SelectItem value="explicit_ids">Explicit Source IDs</SelectItem>
            <SelectItem value="from_node">From Previous Node</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          {config.microsite_source_mode === 'from_notebook' && 'Use sources linked to the notebook'}
          {config.microsite_source_mode === 'explicit_ids' && 'Specify source IDs manually'}
          {config.microsite_source_mode === 'from_node' && 'Extract source IDs from previous node output'}
        </p>
      </div>

      {/* Explicit Source IDs */}
      {config.microsite_source_mode === 'explicit_ids' && (
        <div className="space-y-1.5">
          <Label>Source IDs</Label>
          <div className="flex gap-2">
            <Input
              value={newSourceId}
              onChange={(e) => setNewSourceId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addSourceId();
                }
              }}
              placeholder="Add source ID or {{variable}}"
            />
            <Button onClick={addSourceId} size="sm" type="button">
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          {micrositeSourceIds.length > 0 && (
            <div className="space-y-1 mt-2">
              {micrositeSourceIds.map((id: string, idx: number) => (
                <div
                  key={idx}
                  className="bg-muted px-2 py-1.5 rounded text-xs flex items-center justify-between"
                >
                  <code className="font-mono">{id}</code>
                  <button
                    onClick={() => removeSourceId(id)}
                    className="hover:text-destructive"
                    type="button"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Source Node */}
      {config.microsite_source_mode === 'from_node' && (
        <div className="space-y-1.5">
          <Label htmlFor="source-node">
            Source Node <span className="text-red-500">*</span>
          </Label>
          <Select
            value={config.source_node_id || ''}
            onValueChange={(value) => updateConfig({ source_node_id: value })}
          >
            <SelectTrigger id="source-node">
              <SelectValue placeholder="Select previous node" />
            </SelectTrigger>
            <SelectContent>
              {previousNodes.map((n) => (
                <SelectItem key={n.id} value={n.id}>
                  {n.data.label} ({n.data.type})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Node output should contain source_ids array
          </p>
        </div>
      )}

      <div className="border-t pt-4" />

      {/* User Prompt */}
      <div className="space-y-1.5">
        <Label htmlFor="user-prompt">AI Generation Prompt</Label>
        <Textarea
          id="user-prompt"
          value={config.user_prompt || ''}
          onChange={(e) => updateConfig({ user_prompt: e.target.value })}
          placeholder="Optional prompt to guide content generation"
          rows={3}
        />
        <p className="text-xs text-muted-foreground">
          Provide context or style guidance for the AI
        </p>
      </div>

      {/* Auto Publish */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="auto-publish">Auto-Publish</Label>
          <Select
            value={config.auto_publish ? 'true' : 'false'}
            onValueChange={(value) => updateConfig({ auto_publish: value === 'true' })}
          >
            <SelectTrigger id="auto-publish" className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">Yes</SelectItem>
              <SelectItem value="false">No</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <p className="text-xs text-muted-foreground">
          Publish microsite immediately after generation (if moderation passes)
        </p>
      </div>

      {/* Fail on Moderation Block */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="fail-on-moderation">Fail on Moderation Block</Label>
          <Select
            value={config.fail_on_moderation_block === false ? 'false' : 'true'}
            onValueChange={(value) => updateConfig({ fail_on_moderation_block: value === 'true' })}
          >
            <SelectTrigger id="fail-on-moderation" className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">Yes</SelectItem>
              <SelectItem value="false">No</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <p className="text-xs text-muted-foreground">
          Stop workflow execution if moderation returns 'blocked' status
        </p>
      </div>

      <div className="border-t pt-4" />

      {/* Output Format */}
      <div className="space-y-1.5">
        <Label htmlFor="output-format">Output Format</Label>
        <Select
          value={config.microsite_output_format || 'summary'}
          onValueChange={(value) => updateConfig({ microsite_output_format: value })}
        >
          <SelectTrigger id="output-format">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="summary">
              Summary (id, version, preview_url, status)
            </SelectItem>
            <SelectItem value="preview_url">
              Preview URL Only (id, url, status)
            </SelectItem>
            <SelectItem value="full_response">
              Full Response (complete generation details)
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
