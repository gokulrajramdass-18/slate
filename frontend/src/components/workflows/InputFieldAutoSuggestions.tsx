import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Sparkles, Check } from 'lucide-react';
import { toolSchemaApi } from '@/lib/api/workflows';
import { getCurrentGraphState } from '@/components/workflows/GraphEditor';
import type { InputFieldDefinition } from '@/lib/stores/graph-store';

interface InputFieldAutoSuggestionsProps {
  nodeId: string;
  currentFields: InputFieldDefinition[];
  onApply: (fields: InputFieldDefinition[]) => void;
}

export function InputFieldAutoSuggestions({ nodeId, currentFields, onApply }: InputFieldAutoSuggestionsProps) {
  const [suggestedFields, setSuggestedFields] = useState<InputFieldDefinition[]>([]);
  const [connectedNodes, setConnectedNodes] = useState<any[]>([]);

  // Detect connected nodes when component mounts or nodeId changes
  useEffect(() => {
    const graphState = getCurrentGraphState();

    // Find outgoing edges from this input node
    const outgoingEdges = graphState.edges.filter((e: any) => e.source === nodeId);

    // Get target nodes
    const targets = outgoingEdges.map((edge: any) => {
      return graphState.nodes.find((n: any) => n.id === edge.target);
    }).filter(Boolean);

    setConnectedNodes(targets);

    // Subscribe to graph changes to detect when connected nodes are updated
    // We need to re-run this when nodes change
    const interval = setInterval(() => {
      const updatedGraphState = getCurrentGraphState();
      const updatedTargets = outgoingEdges.map((edge: any) => {
        return updatedGraphState.nodes.find((n: any) => n.id === edge.target);
      }).filter(Boolean);

      // Check if any node config changed
      const hasChanges = updatedTargets.some((target: any, index: number) => {
        const oldTarget = targets[index];
        return JSON.stringify(target?.data?.config) !== JSON.stringify(oldTarget?.data?.config);
      });

      if (hasChanges) {
        setConnectedNodes(updatedTargets);
      }
    }, 1000); // Check every second

    return () => clearInterval(interval);
  }, [nodeId]);

  // Fetch tool schemas for connected tool nodes
  const toolNodes = connectedNodes.filter((n) => n.data.type === 'tool');

  const toolSchemaQueries = useQuery({
    queryKey: ['tool-schemas', toolNodes.map((n) => n.data.config.tool_name).join(',')],
    queryFn: async () => {
      const schemas = await Promise.all(
        toolNodes
          .filter((n) => n.data.config.tool_name)
          .map((n) => toolSchemaApi.getToolSchema(n.data.config.tool_name))
      );
      return schemas;
    },
    enabled: toolNodes.length > 0,
  });

  // Generate suggestions when tool schemas are loaded or connected nodes change
  useEffect(() => {
    const suggestions: InputFieldDefinition[] = [];

    // Extract fields from tool schemas
    if (toolSchemaQueries.data) {
      toolSchemaQueries.data.forEach((schema) => {
        schema.fields.forEach((field) => {
          // Don't suggest if field already exists
          if (!currentFields.find((f) => f.name === field.name)) {
            suggestions.push(field);
          }
        });
      });
    }

    // Add suggestions for conditional nodes
    const conditionalNodes = connectedNodes.filter((n) => n.data.type === 'conditional');
    conditionalNodes.forEach((node) => {
      const fieldPath = node.data.config.field_path;
      if (fieldPath) {
        // Extract field name from JSONPath (e.g., "$.status" -> "status")
        const fieldName = fieldPath.replace(/^\$\./, '');
        if (!suggestions.find((f) => f.name === fieldName) && !currentFields.find((f) => f.name === fieldName)) {
          suggestions.push({
            name: fieldName,
            type: 'string',
            required: false,
            description: `Field used by conditional: ${node.data.label}`,
          });
        }
      }
    });

    // Add suggestions for agent nodes
    const agentNodes = connectedNodes.filter((n) => n.data.type === 'agent');
    console.log('[InputFieldAutoSuggestions] Agent nodes found:', agentNodes.length);

    agentNodes.forEach((node) => {
      console.log('[InputFieldAutoSuggestions] Processing agent node:', node.data.label);
      console.log('[InputFieldAutoSuggestions] Agent config:', node.data.config);

      // Check if agent has a prompt template configured
      const promptTemplate = node.data.config?.prompt;
      console.log('[InputFieldAutoSuggestions] Prompt template:', promptTemplate);

      if (promptTemplate) {
        // Parse template variables from {{variable}} patterns
        const variablePattern = /\{\{([^}]+)\}\}/g;
        const matches = promptTemplate.matchAll(variablePattern);

        for (const match of matches) {
          const varName = match[1].trim();
          console.log('[InputFieldAutoSuggestions] Found variable:', varName);

          // Don't suggest if already exists
          if (!suggestions.find((f) => f.name === varName) && !currentFields.find((f) => f.name === varName)) {
            suggestions.push({
              name: varName,
              type: 'string',
              required: true,
              description: `Required by agent prompt template: ${node.data.label}`,
            });
          }
        }
      } else {
        console.log('[InputFieldAutoSuggestions] No prompt template, suggesting defaults');
        // Agent doesn't have prompt configured yet - suggest default fields
        if (!suggestions.find((f) => f.name === 'prompt') && !currentFields.find((f) => f.name === 'prompt')) {
          console.log('[InputFieldAutoSuggestions] Adding default prompt field');
          suggestions.push({
            name: 'prompt',
            type: 'string',
            required: true,
            description: `User query or prompt for agent: ${node.data.label}`,
          });
        }

        // Also suggest optional context field
        if (!suggestions.find((f) => f.name === 'context') && !currentFields.find((f) => f.name === 'context')) {
          console.log('[InputFieldAutoSuggestions] Adding default context field');
          suggestions.push({
            name: 'context',
            type: 'string',
            required: false,
            description: `Additional context for agent: ${node.data.label}`,
          });
        }
      }
    });

    // Add suggestions for LLM nodes
    const llmNodes = connectedNodes.filter((n) => n.data.type === 'llm');
    llmNodes.forEach((node) => {
      // LLM nodes typically need a user_message field
      if (!suggestions.find((f) => f.name === 'user_message') && !currentFields.find((f) => f.name === 'user_message')) {
        suggestions.push({
          name: 'user_message',
          type: 'string',
          required: true,
          description: `User message for LLM: ${node.data.label}`,
        });
      }
    });

    console.log('[InputFieldAutoSuggestions] Final suggestions:', suggestions);
    setSuggestedFields(suggestions);
  }, [toolSchemaQueries.data, connectedNodes, currentFields]);

  if (connectedNodes.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">No Connections</CardTitle>
          <CardDescription>
            Connect this input node to other nodes to see suggested fields.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (toolSchemaQueries.isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Analyzing connections...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          Suggested Fields
        </h3>
        <p className="text-xs text-muted-foreground mt-1">
          Based on {connectedNodes.length} connected node{connectedNodes.length !== 1 ? 's' : ''}
        </p>
      </div>

      {suggestedFields.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground text-center">
              No additional fields suggested. Connected nodes don't require specific inputs.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="space-y-3">
            {suggestedFields.map((field, index) => (
              <Card key={index}>
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <div className="font-medium text-sm flex items-center gap-2">
                        {field.name}
                        <Badge variant="outline" className="text-xs">
                          {field.type}
                        </Badge>
                        {field.required && (
                          <Badge variant="destructive" className="text-xs">
                            Required
                          </Badge>
                        )}
                      </div>
                      {field.description && (
                        <p className="text-xs text-muted-foreground">{field.description}</p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Button
            onClick={() => onApply([...currentFields, ...suggestedFields])}
            className="w-full"
          >
            <Check className="h-4 w-4 mr-2" />
            Apply All Suggestions
          </Button>
        </>
      )}

      <div className="pt-2 border-t">
        <h4 className="text-xs font-medium text-muted-foreground mb-2">Connected Nodes:</h4>
        <div className="flex flex-wrap gap-2">
          {connectedNodes.map((node) => (
            <Badge key={node.id} variant="secondary" className="text-xs">
              {node.data.label} ({node.data.type})
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}
