/**
 * Variable Reference Helper
 *
 * Popover component that shows available template variables from workflow context.
 * Users can reference these variables using {{variable_name}} syntax in node configurations.
 */

'use client';

import React from 'react';
import { HelpCircle, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useGraphStore } from '@/lib/stores/graph-store';

interface VariableReferenceHelperProps {
  currentNodeId?: string;
}

export function VariableReferenceHelper({ currentNodeId }: VariableReferenceHelperProps) {
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);

  // Get input node fields
  const inputNode = nodes.find((n) => n.data.type === 'input');
  const inputFields = inputNode?.data.config?.input_fields || [];

  // Get previous nodes (nodes that have edges leading to current node)
  const previousNodes = React.useMemo(() => {
    if (!currentNodeId) return [];

    // Find all nodes that connect to the current node
    const incomingEdges = edges.filter((e) => e.target === currentNodeId);
    const previousNodeIds = incomingEdges.map((e) => e.source);

    return nodes.filter((n) => previousNodeIds.includes(n.id));
  }, [nodes, edges, currentNodeId]);

  // Get all nodes before current node in execution order
  const allPreviousNodes = React.useMemo(() => {
    if (!currentNodeId) {
      // If no current node specified, show all nodes except output
      return nodes.filter((n) => n.data.type !== 'output');
    }

    // For now, show all nodes except current and output
    return nodes.filter((n) => n.id !== currentNodeId && n.data.type !== 'output');
  }, [nodes, currentNodeId]);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 gap-1">
          <HelpCircle className="h-4 w-4" />
          <span className="text-xs">Available Variables</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-96 max-h-[500px] overflow-y-auto" align="start">
        <div className="space-y-4">
          <div>
            <h4 className="font-semibold text-sm mb-2">Template Variable Syntax</h4>
            <p className="text-xs text-muted-foreground mb-2">
              Use <code className="bg-muted px-1 py-0.5 rounded">{'{{variable_name}}'}</code> to reference values from:
            </p>
          </div>

          {/* Input Fields */}
          {inputFields.length > 0 && (
            <div>
              <h5 className="font-medium text-sm mb-1.5 flex items-center gap-1.5">
                <span className="text-blue-600">Input Fields</span>
                <span className="text-xs text-muted-foreground">(from Input node)</span>
              </h5>
              <div className="space-y-1">
                {inputFields.map((field: any) => (
                  <div key={field.name} className="bg-muted/50 rounded p-2 text-xs">
                    <div className="flex items-center gap-2">
                      <code className="font-mono text-blue-700 dark:text-blue-400">
                        {'{{' + field.name + '}}'}
                      </code>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span className="text-muted-foreground">
                        {field.type}
                        {field.required && <span className="text-red-500 ml-1">*</span>}
                      </span>
                    </div>
                    {field.description && (
                      <p className="text-muted-foreground mt-1">{field.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Previous Node Outputs */}
          {allPreviousNodes.length > 0 && (
            <div>
              <h5 className="font-medium text-sm mb-1.5 flex items-center gap-1.5">
                <span className="text-purple-600">Previous Node Outputs</span>
                <span className="text-xs text-muted-foreground">(from upstream nodes)</span>
              </h5>
              <div className="space-y-2">
                {allPreviousNodes.map((node) => (
                  <div key={node.id} className="bg-muted/50 rounded p-2">
                    <div className="text-xs font-medium mb-1 flex items-center gap-2">
                      <span className="text-foreground">{node.data.label}</span>
                      <span className="text-muted-foreground">({node.data.type})</span>
                    </div>
                    <div className="space-y-1">
                      {/* Common output fields based on node type */}
                      {node.data.type === 'llm' && (
                        <div className="text-xs">
                          <code className="font-mono text-purple-700 dark:text-purple-400">
                            {'{{output}}'} or {'{{response}}'}
                          </code>
                          <span className="text-muted-foreground ml-2">- LLM response text</span>
                        </div>
                      )}
                      {node.data.type === 'agent' && (
                        <div className="text-xs">
                          <code className="font-mono text-purple-700 dark:text-purple-400">
                            {'{{output}}'} or {'{{result}}'}
                          </code>
                          <span className="text-muted-foreground ml-2">- Agent execution result</span>
                        </div>
                      )}
                      {node.data.type === 'tool' && (
                        <div className="text-xs">
                          <code className="font-mono text-purple-700 dark:text-purple-400">
                            {'{{result}}'} or {'{{output}}'}
                          </code>
                          <span className="text-muted-foreground ml-2">- Tool execution output</span>
                        </div>
                      )}
                      {node.data.type === 'notebook_generator' && (
                        <>
                          <div className="text-xs">
                            <code className="font-mono text-purple-700 dark:text-purple-400">
                              {'{{notebook_id}}'}
                            </code>
                            <span className="text-muted-foreground ml-2">- Created notebook ID</span>
                          </div>
                          <div className="text-xs">
                            <code className="font-mono text-purple-700 dark:text-purple-400">
                              {'{{name}}'}
                            </code>
                            <span className="text-muted-foreground ml-2">- Notebook name</span>
                          </div>
                        </>
                      )}
                      {node.data.type === 'microsite_generator' && (
                        <>
                          <div className="text-xs">
                            <code className="font-mono text-purple-700 dark:text-purple-400">
                              {'{{microsite_id}}'}
                            </code>
                            <span className="text-muted-foreground ml-2">- Created microsite ID</span>
                          </div>
                          <div className="text-xs">
                            <code className="font-mono text-purple-700 dark:text-purple-400">
                              {'{{preview_url}}'}
                            </code>
                            <span className="text-muted-foreground ml-2">- Preview URL</span>
                          </div>
                        </>
                      )}
                      {node.data.type === 'input' && (
                        <div className="text-xs text-muted-foreground">
                          See Input Fields section above
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Examples */}
          <div>
            <h5 className="font-medium text-sm mb-1.5">Examples</h5>
            <div className="space-y-1.5 text-xs">
              <div className="bg-muted/50 rounded p-2">
                <code className="font-mono">Analysis for {'{{quarter}}'} {'{{year}}'}</code>
                <p className="text-muted-foreground mt-1">→ "Analysis for Q1 2024"</p>
              </div>
              <div className="bg-muted/50 rounded p-2">
                <code className="font-mono">Created from notebook {'{{notebook_id}}'}</code>
                <p className="text-muted-foreground mt-1">→ "Created from notebook nb-123"</p>
              </div>
            </div>
          </div>

          {/* Notes */}
          <div className="text-xs text-muted-foreground border-t pt-3">
            <p className="mb-1">
              <strong>Note:</strong> Variables are resolved at execution time.
            </p>
            <p>
              If a variable is not found, it will remain as-is in the text.
            </p>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
