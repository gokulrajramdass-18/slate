/**
 * Notebook Generator Properties Panel
 *
 * Configuration form for notebook_generator node type.
 * Allows users to configure notebook creation from workflow outputs.
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

interface NotebookGeneratorPropertiesProps {
  nodeId: string;
}

export function NotebookGeneratorProperties({ nodeId }: NotebookGeneratorPropertiesProps) {
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

  // Get previous nodes for content source selection
  const previousNodes = nodes.filter(
    (n) => n.id !== nodeId && n.data.type !== 'output'
  );

  // Handle tags
  const tags = config.tags || [];
  const [newTag, setNewTag] = React.useState('');

  const addTag = () => {
    if (newTag.trim() && !tags.includes(newTag.trim())) {
      updateConfig({ tags: [...tags, newTag.trim()] });
      setNewTag('');
    }
  };

  const removeTag = (tag: string) => {
    updateConfig({ tags: tags.filter((t: string) => t !== tag) });
  };

  // Handle existing source IDs
  const existingSourceIds = config.existing_source_ids || [];
  const [newSourceId, setNewSourceId] = React.useState('');

  const addSourceId = () => {
    if (newSourceId.trim() && !existingSourceIds.includes(newSourceId.trim())) {
      updateConfig({ existing_source_ids: [...existingSourceIds, newSourceId.trim()] });
      setNewSourceId('');
    }
  };

  const removeSourceId = (id: string) => {
    updateConfig({ existing_source_ids: existingSourceIds.filter((sid: string) => sid !== id) });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Notebook Generator Configuration</h3>
        <VariableReferenceHelper currentNodeId={nodeId} />
      </div>

      {/* Notebook Name */}
      <div className="space-y-1.5">
        <Label htmlFor="notebook-name">
          Notebook Name <span className="text-red-500">*</span>
        </Label>
        <Input
          id="notebook-name"
          value={config.notebook_name || ''}
          onChange={(e) => updateConfig({ notebook_name: e.target.value })}
          placeholder="e.g., Analysis for {{quarter}}"
        />
        <p className="text-xs text-muted-foreground">
          Supports {'{{variable}}'} syntax
        </p>
      </div>

      {/* Notebook Description */}
      <div className="space-y-1.5">
        <Label htmlFor="notebook-description">Notebook Description</Label>
        <Textarea
          id="notebook-description"
          value={config.notebook_description || ''}
          onChange={(e) => updateConfig({ notebook_description: e.target.value })}
          placeholder="Optional description"
          rows={3}
        />
      </div>

      {/* Folder ID */}
      <div className="space-y-1.5">
        <Label htmlFor="folder-id">Folder ID</Label>
        <Input
          id="folder-id"
          value={config.folder_id || ''}
          onChange={(e) => updateConfig({ folder_id: e.target.value })}
          placeholder="Optional folder ID"
        />
        <p className="text-xs text-muted-foreground">
          Leave empty for root folder
        </p>
      </div>

      {/* Tags */}
      <div className="space-y-1.5">
        <Label>Tags</Label>
        <div className="flex gap-2">
          <Input
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addTag();
              }
            }}
            placeholder="Add tag"
          />
          <Button onClick={addTag} size="sm" type="button">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {tags.map((tag: string) => (
              <div
                key={tag}
                className="bg-muted px-2 py-1 rounded text-xs flex items-center gap-1"
              >
                {tag}
                <button
                  onClick={() => removeTag(tag)}
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

      <div className="border-t pt-4" />

      {/* Source Mode */}
      <div className="space-y-1.5">
        <Label htmlFor="source-mode">Source Mode</Label>
        <Select
          value={config.source_mode || 'create_from_content'}
          onValueChange={(value) => updateConfig({ source_mode: value })}
        >
          <SelectTrigger id="source-mode">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="create_from_content">Create from Content</SelectItem>
            <SelectItem value="use_existing">Use Existing Sources</SelectItem>
            <SelectItem value="both">Both (Create + Link Existing)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Content Creation Fields */}
      {(config.source_mode === 'create_from_content' || config.source_mode === 'both') && (
        <>
          {/* Content Source Node */}
          <div className="space-y-1.5">
            <Label htmlFor="content-source-node">
              Content Source Node <span className="text-red-500">*</span>
            </Label>
            <Select
              value={config.content_source_node_id || ''}
              onValueChange={(value) => updateConfig({ content_source_node_id: value })}
            >
              <SelectTrigger id="content-source-node">
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
          </div>

          {/* Content Extraction Mode */}
          <div className="space-y-1.5">
            <Label htmlFor="extraction-mode">Content Extraction Mode</Label>
            <Select
              value={config.content_extraction_mode || 'full_output'}
              onValueChange={(value) => updateConfig({ content_extraction_mode: value })}
            >
              <SelectTrigger id="extraction-mode">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="full_output">Full Output</SelectItem>
                <SelectItem value="smart_parse">Smart Parse (JSON/Markdown)</SelectItem>
                <SelectItem value="json_path">JSONPath Expression</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {config.content_extraction_mode === 'full_output' && 'Extract entire node output as text'}
              {config.content_extraction_mode === 'smart_parse' && 'Intelligently parse JSON arrays and objects'}
              {config.content_extraction_mode === 'json_path' && 'Use JSONPath to extract specific fields'}
            </p>
          </div>

          {/* JSONPath Expression */}
          {config.content_extraction_mode === 'json_path' && (
            <div className="space-y-1.5">
              <Label htmlFor="extraction-path">
                JSONPath Expression <span className="text-red-500">*</span>
              </Label>
              <Input
                id="extraction-path"
                value={config.content_extraction_path || ''}
                onChange={(e) => updateConfig({ content_extraction_path: e.target.value })}
                placeholder="e.g., $.results[*].content"
              />
              <p className="text-xs text-muted-foreground">
                Example: $.results[*] extracts all items from results array
              </p>
            </div>
          )}

          {/* Source Title Template */}
          <div className="space-y-1.5">
            <Label htmlFor="source-title">Source Title Template</Label>
            <Input
              id="source-title"
              value={config.source_title_template || 'Generated Source'}
              onChange={(e) => updateConfig({ source_title_template: e.target.value })}
              placeholder="e.g., Analysis Result"
            />
          </div>

          {/* Source Type */}
          <div className="space-y-1.5">
            <Label htmlFor="source-type">Source Type</Label>
            <Select
              value={config.source_type || 'text'}
              onValueChange={(value) => updateConfig({ source_type: value })}
            >
              <SelectTrigger id="source-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text">Text</SelectItem>
                <SelectItem value="file">File</SelectItem>
                <SelectItem value="url">URL</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </>
      )}

      {/* Existing Source IDs */}
      {(config.source_mode === 'use_existing' || config.source_mode === 'both') && (
        <div className="space-y-1.5">
          <Label>Existing Source IDs</Label>
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
          {existingSourceIds.length > 0 && (
            <div className="space-y-1 mt-2">
              {existingSourceIds.map((id: string, idx: number) => (
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

      <div className="border-t pt-4" />

      {/* Output Format */}
      <div className="space-y-1.5">
        <Label htmlFor="output-format">Output Format</Label>
        <Select
          value={config.output_format || 'summary'}
          onValueChange={(value) => updateConfig({ output_format: value })}
        >
          <SelectTrigger id="output-format">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="summary">Summary (notebook_id, name, source_count, status)</SelectItem>
            <SelectItem value="id_only">ID Only (notebook_id)</SelectItem>
            <SelectItem value="full_object">Full Object (all details)</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
