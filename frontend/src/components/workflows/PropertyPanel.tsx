/**
 * Property Panel Component
 *
 * Displays and edits properties of selected node.
 */

'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Checkbox } from '@/components/ui/checkbox';
import { Trash2, X, Sparkles, Code, List } from 'lucide-react';
import { useGraphStore, useSelectedNode } from '@/lib/stores/graph-store';
import { agentsApi } from '@/lib/api/agents';
import { listStandaloneAgents } from '@/lib/api/standalone-agents';
import { InputFieldVisualEditor } from './InputFieldVisualEditor';
import { InputFieldJsonEditor } from './InputFieldJsonEditor';
import { InputFieldAutoSuggestions } from './InputFieldAutoSuggestions';
import { NotebookGeneratorProperties } from './NotebookGeneratorProperties';
import { MicrositeGeneratorProperties } from './MicrositeGeneratorProperties';
import { HanaTablePropertyPanel } from './HanaTablePropertyPanel';
import { APINodePropertyPanel } from './APINodePropertyPanel';
import { CompareNodeWatchColumns } from './CompareNodeWatchColumns';
import { getCurrentGraphState } from './GraphEditor';

// ============================================================================
// Property Panel Component
// ============================================================================

export function PropertyPanel() {
  // Get selectedNodeId from store
  const selectedNodeId = useGraphStore((state) => state.selectedNodeId);

  // Get the selected node directly from store state when needed
  // Use a selector that only returns when the specific node changes
  const selectedNode = useGraphStore(
    React.useCallback(
      (state) => state.nodes.find((n) => n.id === selectedNodeId),
      [selectedNodeId]
    )
  );

  // Check if node is agent type
  const isAgentNode = selectedNode?.data.type === 'agent';

  console.log('[PropertyPanel] Render - selectedNode:', selectedNode?.id, selectedNode?.data.type);
  console.log('[PropertyPanel] isAgentNode:', isAgentNode);

  // Fetch standalone agents
  const { data: standaloneAgentsData, isLoading: isLoadingAgents, error: agentsError } = useQuery({
    queryKey: ['standalone-agents'],
    queryFn: async () => {
      console.log('[PropertyPanel] Fetching standalone agents...');
      const result = await listStandaloneAgents();
      console.log('[PropertyPanel] Standalone agents result:', result);
      return result;
    },
    enabled: isAgentNode,
  });

  // Fetch agent teams
  const { data: teamsData, isLoading: isLoadingTeams, error: teamsError } = useQuery({
    queryKey: ['agent-teams'],
    queryFn: async () => {
      console.log('[PropertyPanel] Fetching agent teams...');
      const result = await agentsApi.listTeams();
      console.log('[PropertyPanel] Agent teams result:', result);
      return result;
    },
    enabled: isAgentNode,
  });

  const standaloneAgents = standaloneAgentsData?.agents || [];
  const agentTeams = teamsData || [];

  if (isAgentNode) {
    console.log('[PropertyPanel] Agent type:', selectedNode?.data.config.agent_type);
    console.log('[PropertyPanel] Standalone agents:', standaloneAgents);
    console.log('[PropertyPanel] Agent teams:', agentTeams);
    console.log('[PropertyPanel] Loading agents:', isLoadingAgents);
    console.log('[PropertyPanel] Loading teams:', isLoadingTeams);
    console.log('[PropertyPanel] Agents error:', agentsError);
    console.log('[PropertyPanel] Teams error:', teamsError);
  }

  // Hide panel completely when no node is selected
  if (!selectedNode) {
    return null;
  }

  const handleUpdate = (field: string, value: any) => {
    if (!selectedNode) return;

    console.log('[PropertyPanel] handleUpdate called - field:', field, 'value:', value);

    // Get the setNodes function from React Flow (stored in store by GraphEditor)
    const setNodesFromReactFlow = (useGraphStore.getState() as any).__setNodesFromReactFlow;

    if (setNodesFromReactFlow) {
      console.log('[PropertyPanel] Calling setNodesFromReactFlow');
      setNodesFromReactFlow((nds: any[]) => {
        const updatedNodes = nds.map((node: any) => {
          if (node.id === selectedNode.id) {
            // Build updated data from the CURRENT node state, not selectedNode
            const currentData = node.data;
            console.log('[PropertyPanel] Current node data from React Flow:', currentData);
            console.log('[PropertyPanel] Current config:', currentData.config);

            const updatedData = {
              ...currentData,
              [field === 'label' ? 'label' : 'config']:
                field === 'label'
                  ? value
                  : { ...currentData.config, [field]: value },
            };

            console.log('[PropertyPanel] Updated data:', updatedData);
            console.log('[PropertyPanel] Updated config:', updatedData.config);

            return { ...node, data: updatedData };
          }
          return node;
        });

        // Also update Zustand store immediately
        requestAnimationFrame(() => {
          useGraphStore.getState().setNodes(updatedNodes);
        });

        return updatedNodes;
      });
    } else {
      console.error('[PropertyPanel] setNodesFromReactFlow not available!');
    }
  };

  const handleDelete = () => {
    if (confirm('Are you sure you want to delete this node?')) {
      useGraphStore.getState().deleteNode(selectedNode.id);
    }
  };

  const handleClose = () => {
    useGraphStore.getState().setSelectedNode(null);
  };

  return (
    <Card className="w-80 h-full overflow-y-auto">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Node Properties</CardTitle>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDelete}
              className="text-destructive hover:text-destructive"
              title="Delete node"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleClose}
              title="Close panel"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Common Properties */}
        <div className="space-y-2">
          <Label htmlFor="label">Label</Label>
          <Input
            id="label"
            value={selectedNode.data.label}
            onChange={(e) => handleUpdate('label', e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label>Type</Label>
          <Input value={selectedNode.data.type} disabled className="bg-muted" />
        </div>

        {/* LLM Node Properties */}
        {selectedNode.data.type === 'llm' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="model">Model</Label>
              <Select
                value={selectedNode.data.config.model_name || ''}
                onValueChange={(value) => handleUpdate('model_name', value)}
              >
                <SelectTrigger id="model">
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gpt-4">GPT-4</SelectItem>
                  <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                  <SelectItem value="anthropic--claude-4.6-sonnet">Claude 4.6 Sonnet</SelectItem>
                  <SelectItem value="anthropic--claude-4.6-opus">Claude 4.6 Opus</SelectItem>
                  <SelectItem value="gemini-pro">Gemini Pro</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="system-prompt">System Prompt</Label>
              <Textarea
                id="system-prompt"
                value={selectedNode.data.config.system_prompt || ''}
                onChange={(e) => handleUpdate('system_prompt', e.target.value)}
                rows={6}
                placeholder="Enter system prompt..."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="user-prompt">User Prompt (Input Message)</Label>
              <Textarea
                id="user-prompt"
                value={selectedNode.data.config.prompt || ''}
                onChange={(e) => handleUpdate('prompt', e.target.value)}
                rows={4}
                placeholder="Enter user message... Use {{node-id.field}} to reference previous nodes"
              />
              <p className="text-xs text-muted-foreground">
                Tip: Use variables like {"{{approval-node.compare-node.changed_rows.modified}}"} to access data
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="temperature">Temperature</Label>
              <Input
                id="temperature"
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={selectedNode.data.config.temperature || 0.7}
                onChange={(e) => handleUpdate('temperature', parseFloat(e.target.value))}
              />
            </div>
          </>
        )}

        {/* Tool Node Properties */}
        {selectedNode.data.type === 'tool' && (
          <div className="space-y-2">
            <Label htmlFor="tool">Tool</Label>
            <Select
              value={selectedNode.data.config.tool_name || ''}
              onValueChange={(value) => handleUpdate('tool_name', value)}
            >
              <SelectTrigger id="tool">
                <SelectValue placeholder="Select tool" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="web_search">Web Search</SelectItem>
                <SelectItem value="calculator">Calculator</SelectItem>
                <SelectItem value="datetime">Date/Time</SelectItem>
                <SelectItem value="json_parser">JSON Parser</SelectItem>
                <SelectItem value="text_analyzer">Text Analyzer</SelectItem>
                <SelectItem value="url_fetch">URL Fetch</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Conditional Node Properties */}
        {selectedNode.data.type === 'conditional' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="condition-type">Condition Type</Label>
              <Select
                value={selectedNode.data.config.condition_type || ''}
                onValueChange={(value) => handleUpdate('condition_type', value)}
              >
                <SelectTrigger id="condition-type">
                  <SelectValue placeholder="Select condition" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="equals">Equals</SelectItem>
                  <SelectItem value="contains">Contains</SelectItem>
                  <SelectItem value="greater_than">Greater Than</SelectItem>
                  <SelectItem value="less_than">Less Than</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="field-path">Field Path (JSONPath)</Label>
              <Input
                id="field-path"
                value={selectedNode.data.config.field_path || ''}
                onChange={(e) => handleUpdate('field_path', e.target.value)}
                placeholder="$.status"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="comparison-value">Comparison Value</Label>
              <Input
                id="comparison-value"
                value={selectedNode.data.config.comparison_value || ''}
                onChange={(e) => handleUpdate('comparison_value', e.target.value)}
                placeholder="active"
              />
            </div>
          </>
        )}

        {/* Agent Node Properties */}
        {selectedNode.data.type === 'agent' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="agent-type">Agent Type</Label>
              <Select
                value={selectedNode.data.config.agent_type || ''}
                onValueChange={(value) => {
                  console.log('[PropertyPanel] Agent type selected:', value);
                  console.log('[PropertyPanel] About to call handleUpdate for agent_type');
                  handleUpdate('agent_type', value);
                  console.log('[PropertyPanel] handleUpdate for agent_type completed');

                  console.log('[PropertyPanel] About to call handleUpdate for agent_id (clear)');
                  handleUpdate('agent_id', '');
                  console.log('[PropertyPanel] handleUpdate for agent_id completed');

                  console.log('[PropertyPanel] About to call handleUpdate for agent_name (clear)');
                  handleUpdate('agent_name', '');
                  console.log('[PropertyPanel] handleUpdate for agent_name completed');
                }}
              >
                <SelectTrigger id="agent-type">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="standalone">Standalone Agent</SelectItem>
                  <SelectItem value="team">Agent Team</SelectItem>
                </SelectContent>
              </Select>
              {!selectedNode.data.config.agent_type && (
                <p className="text-xs text-muted-foreground">
                  Select a type to choose an agent or team
                </p>
              )}
            </div>

            {selectedNode.data.config.agent_type === 'standalone' && (
              <div className="space-y-2">
                <Label htmlFor="standalone-agent">Standalone Agent</Label>
                <Select
                  value={selectedNode.data.config.agent_id || ''}
                  onValueChange={(value) => {
                    console.log('[PropertyPanel] Standalone agent selected:', value);
                    const agent = standaloneAgents.find((a) => a.id === value);
                    console.log('[PropertyPanel] Found agent:', agent);
                    handleUpdate('agent_id', value);
                    handleUpdate('agent_name', agent?.name || '');
                  }}
                  disabled={isLoadingAgents}
                >
                  <SelectTrigger id="standalone-agent">
                    <SelectValue placeholder={isLoadingAgents ? "Loading..." : "Select agent"} />
                  </SelectTrigger>
                  <SelectContent>
                    {isLoadingAgents && (
                      <div className="p-2 text-sm text-muted-foreground">
                        Loading agents...
                      </div>
                    )}
                    {!isLoadingAgents && standaloneAgents.length === 0 && (
                      <div className="p-2 text-sm text-muted-foreground">
                        No standalone agents available
                      </div>
                    )}
                    {standaloneAgents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        {agent.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedNode.data.config.agent_id && (
                  <p className="text-xs text-muted-foreground">
                    {standaloneAgents.find((a) => a.id === selectedNode.data.config.agent_id)?.role || 'No role specified'}
                  </p>
                )}
              </div>
            )}

            {selectedNode.data.config.agent_type === 'team' && (
              <div className="space-y-2">
                <Label htmlFor="agent-team">Agent Team</Label>
                <Select
                  value={selectedNode.data.config.agent_id || ''}
                  onValueChange={(value) => {
                    console.log('[PropertyPanel] Agent team selected:', value);
                    const team = agentTeams.find((t) => t.id === value);
                    console.log('[PropertyPanel] Found team:', team);
                    handleUpdate('agent_id', value);
                    handleUpdate('agent_name', team?.name || '');
                  }}
                  disabled={isLoadingTeams}
                >
                  <SelectTrigger id="agent-team">
                    <SelectValue placeholder={isLoadingTeams ? "Loading..." : "Select team"} />
                  </SelectTrigger>
                  <SelectContent>
                    {isLoadingTeams && (
                      <div className="p-2 text-sm text-muted-foreground">
                        Loading teams...
                      </div>
                    )}
                    {!isLoadingTeams && agentTeams.length === 0 && (
                      <div className="p-2 text-sm text-muted-foreground">
                        No agent teams available
                      </div>
                    )}
                    {agentTeams.map((team) => (
                      <SelectItem key={team.id} value={team.id}>
                        {team.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedNode.data.config.agent_id && (
                  <p className="text-xs text-muted-foreground">
                    {agentTeams.find((t) => t.id === selectedNode.data.config.agent_id)?.agents?.length || 0} agents in team
                  </p>
                )}
              </div>
            )}

            {/* Prompt field - shown after agent is selected */}
            {selectedNode.data.config.agent_id && (
              <div className="space-y-2">
                <Label htmlFor="agent-prompt">
                  Prompt <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="agent-prompt"
                  value={selectedNode.data.config.prompt || ''}
                  onChange={(e) => handleUpdate('prompt', e.target.value)}
                  rows={6}
                  placeholder="Enter the prompt to send to the agent. You can use {{variable_name}} to reference values from connected input nodes."
                />
                <p className="text-xs text-muted-foreground">
                  This prompt will be sent to the agent at runtime. Use template variables like <code className="bg-muted px-1 py-0.5 rounded">{'{{prompt}}'}</code> or <code className="bg-muted px-1 py-0.5 rounded">{'{{context}}'}</code> to reference input fields.
                </p>
              </div>
            )}
          </>
        )}

        {/* Input Node */}
        {selectedNode.data.type === 'input' && (
          <div className="space-y-4">
            {/* Show quick suggestion banner if connected to nodes */}
            {(() => {
              const graphState = getCurrentGraphState();
              const outgoingEdges = graphState.edges?.filter((e: any) => e.source === selectedNode.id) || [];
              const connectedCount = outgoingEdges.length;

              if (connectedCount > 0) {
                return (
                  <Card className="bg-primary/5 border-primary/20">
                    <CardContent className="pt-4 pb-3">
                      <div className="flex items-start gap-2">
                        <Sparkles className="h-4 w-4 text-primary mt-0.5" />
                        <div className="flex-1">
                          <p className="text-xs font-medium">
                            {connectedCount} node{connectedCount !== 1 ? 's' : ''} connected
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Switch to the <strong>Auto</strong> tab to see suggested input fields
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              }
              return null;
            })()}

            <Tabs defaultValue="visual" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="visual">
                  <List className="h-4 w-4 mr-2" />
                  Visual
                </TabsTrigger>
                <TabsTrigger value="json">
                  <Code className="h-4 w-4 mr-2" />
                  JSON
                </TabsTrigger>
                <TabsTrigger value="auto">
                  <Sparkles className="h-4 w-4 mr-2" />
                  Auto
                  <Badge variant="secondary" className="ml-2">
                    {/* Count will be updated by auto-suggestions component */}
                  </Badge>
                </TabsTrigger>
              </TabsList>

              {/* Visual Editor Tab */}
              <TabsContent value="visual" className="space-y-4">
                <InputFieldVisualEditor
                  fields={selectedNode.data.config.input_fields || []}
                  onChange={(fields) => handleUpdate('input_fields', fields)}
                />
              </TabsContent>

              {/* JSON Editor Tab */}
              <TabsContent value="json" className="space-y-4">
                <InputFieldJsonEditor
                  schemaJson={selectedNode.data.config.input_schema_json || ''}
                  onChange={(json) => handleUpdate('input_schema_json', json)}
                />
              </TabsContent>

              {/* Auto-Suggested Tab */}
              <TabsContent value="auto" className="space-y-4">
                <InputFieldAutoSuggestions
                  nodeId={selectedNode.id}
                  currentFields={selectedNode.data.config.input_fields || []}
                  onApply={(fields) => handleUpdate('input_fields', fields)}
                />
              </TabsContent>
            </Tabs>
          </div>
        )}

        {/* Output Node */}
        {selectedNode.data.type === 'output' && (
          <p className="text-sm text-muted-foreground">
            Output nodes mark the workflow exit point.
          </p>
        )}

        {/* Notebook Generator Node */}
        {selectedNode.data.type === 'notebook_generator' && (
          <NotebookGeneratorProperties nodeId={selectedNode.id} />
        )}

        {/* Microsite Generator Node */}
        {selectedNode.data.type === 'microsite_generator' && (
          <MicrositeGeneratorProperties nodeId={selectedNode.id} />
        )}

        {/* Human Approval Node */}
        {selectedNode.data.type === 'human_approval' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="approval-prompt">Approval Prompt</Label>
              <Textarea
                id="approval-prompt"
                value={selectedNode.data.config.approval_prompt || ''}
                onChange={(e) => handleUpdate('approval_prompt', e.target.value)}
                rows={4}
                placeholder="Enter the approval request message..."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="approval-options">Approval Options (comma-separated)</Label>
              <Input
                id="approval-options"
                value={selectedNode.data.config.approval_options?.join(', ') || 'approve, reject'}
                onChange={(e) => handleUpdate('approval_options', e.target.value.split(',').map((s) => s.trim()))}
                placeholder="approve, reject"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="timeout-seconds">Timeout (seconds)</Label>
              <Input
                id="timeout-seconds"
                type="number"
                value={selectedNode.data.config.timeout_seconds || ''}
                onChange={(e) => handleUpdate('timeout_seconds', parseInt(e.target.value))}
                placeholder="Optional timeout"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="timeout-action">Timeout Action</Label>
              <Select
                value={selectedNode.data.config.timeout_action || 'fail'}
                onValueChange={(value) => handleUpdate('timeout_action', value)}
              >
                <SelectTrigger id="timeout-action">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="approve">Auto-Approve</SelectItem>
                  <SelectItem value="reject">Auto-Reject</SelectItem>
                  <SelectItem value="fail">Fail Workflow</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </>
        )}

        {/* Workspace Node */}
        {selectedNode.data.type === 'workspace' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="workspace-template-id">Workspace Template ID</Label>
              <Input
                id="workspace-template-id"
                value={selectedNode.data.config.workspace_template_id || ''}
                onChange={(e) => handleUpdate('workspace_template_id', e.target.value)}
                placeholder="Enter template ID"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="workspace-parameters">Parameters (JSON)</Label>
              <Textarea
                id="workspace-parameters"
                value={JSON.stringify(selectedNode.data.config.workspace_parameters || {}, null, 2)}
                onChange={(e) => {
                  try {
                    handleUpdate('workspace_parameters', JSON.parse(e.target.value));
                  } catch (err) {
                    // Invalid JSON - don't update
                  }
                }}
                rows={6}
                placeholder='{"key": "value"}'
                className="font-mono text-xs"
              />
            </div>

            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selectedNode.data.config.wait_for_completion ?? true}
                  onChange={(e) => handleUpdate('wait_for_completion', e.target.checked)}
                />
                Wait for completion
              </Label>
            </div>
          </>
        )}

        {/* Template Node */}
        {selectedNode.data.type === 'template' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="template-id">Workflow Template ID</Label>
              <Input
                id="template-id"
                value={selectedNode.data.config.template_id || ''}
                onChange={(e) => handleUpdate('template_id', e.target.value)}
                placeholder="Enter template ID"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-parameters">Parameters (JSON)</Label>
              <Textarea
                id="template-parameters"
                value={JSON.stringify(selectedNode.data.config.template_parameters || {}, null, 2)}
                onChange={(e) => {
                  try {
                    handleUpdate('template_parameters', JSON.parse(e.target.value));
                  } catch (err) {
                    // Invalid JSON - don't update
                  }
                }}
                rows={6}
                placeholder='{"key": "value"}'
                className="font-mono text-xs"
              />
            </div>

            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selectedNode.data.config.wait_for_completion ?? true}
                  onChange={(e) => handleUpdate('wait_for_completion', e.target.checked)}
                />
                Wait for completion
              </Label>
            </div>
          </>
        )}

        {/* Delay Node */}
        {selectedNode.data.type === 'delay' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="delay-seconds">Delay (seconds)</Label>
              <Input
                id="delay-seconds"
                type="number"
                value={selectedNode.data.config.delay_seconds || ''}
                onChange={(e) => handleUpdate('delay_seconds', parseInt(e.target.value))}
                placeholder="Enter delay in seconds"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="delay-expression">Or use JSONPath Expression</Label>
              <Input
                id="delay-expression"
                value={selectedNode.data.config.delay_expression || ''}
                onChange={(e) => handleUpdate('delay_expression', e.target.value)}
                placeholder="$.delay_duration"
              />
              <p className="text-xs text-muted-foreground">
                Extract delay value from workflow data using JSONPath
              </p>
            </div>
          </>
        )}

        {/* Webhook Node */}
        {selectedNode.data.type === 'webhook' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="webhook-url">Webhook URL</Label>
              <Input
                id="webhook-url"
                value={selectedNode.data.config.webhook_url || ''}
                onChange={(e) => handleUpdate('webhook_url', e.target.value)}
                placeholder="https://api.example.com/webhook"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhook-method">HTTP Method</Label>
              <Select
                value={selectedNode.data.config.webhook_method || 'POST'}
                onValueChange={(value) => handleUpdate('webhook_method', value)}
              >
                <SelectTrigger id="webhook-method">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="GET">GET</SelectItem>
                  <SelectItem value="POST">POST</SelectItem>
                  <SelectItem value="PUT">PUT</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhook-headers">Headers (JSON)</Label>
              <Textarea
                id="webhook-headers"
                value={JSON.stringify(selectedNode.data.config.webhook_headers || {}, null, 2)}
                onChange={(e) => {
                  try {
                    handleUpdate('webhook_headers', JSON.parse(e.target.value));
                  } catch (err) {
                    // Invalid JSON - don't update
                  }
                }}
                rows={4}
                placeholder='{"Content-Type": "application/json"}'
                className="font-mono text-xs"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhook-body">Body Template (Jinja2)</Label>
              <Textarea
                id="webhook-body"
                value={selectedNode.data.config.webhook_body_template || ''}
                onChange={(e) => handleUpdate('webhook_body_template', e.target.value)}
                rows={6}
                placeholder='{"data": "{{ state.result }}"}'
                className="font-mono text-xs"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhook-auth-type">Authentication Type</Label>
              <Select
                value={selectedNode.data.config.webhook_auth_type || 'none'}
                onValueChange={(value) => handleUpdate('webhook_auth_type', value)}
              >
                <SelectTrigger id="webhook-auth-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  <SelectItem value="bearer">Bearer Token</SelectItem>
                  <SelectItem value="basic">Basic Auth</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {selectedNode.data.config.webhook_auth_type !== 'none' && (
              <div className="space-y-2">
                <Label htmlFor="webhook-auth-token">
                  {selectedNode.data.config.webhook_auth_type === 'bearer' ? 'Bearer Token' : 'Credentials (user:pass)'}
                </Label>
                <Input
                  id="webhook-auth-token"
                  type="password"
                  value={selectedNode.data.config.webhook_auth_token || ''}
                  onChange={(e) => handleUpdate('webhook_auth_token', e.target.value)}
                  placeholder={selectedNode.data.config.webhook_auth_type === 'bearer' ? 'token' : 'username:password'}
                />
              </div>
            )}
          </>
        )}

        {/* Hana Table Node */}
        {selectedNode.data.type === 'hana_table' && (
          <HanaTablePropertyPanel
            selectedNode={selectedNode}
            handleUpdate={handleUpdate}
          />
        )}

        {/* API Node */}
        {selectedNode.data.type === 'api' && (
          <APINodePropertyPanel selectedNode={selectedNode} handleUpdate={handleUpdate} />
        )}

        {/* Snapshot Node */}
        {selectedNode.data.type === 'snapshot' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="source-node-id">Source Node ID</Label>
              <Input
                id="source-node-id"
                value={selectedNode.data.config.source_node_id || ''}
                onChange={(e) => handleUpdate('source_node_id', e.target.value)}
                placeholder="node-id"
              />
              <p className="text-xs text-muted-foreground">
                ID of the API/HANA node whose data to snapshot
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="snapshot-label">Snapshot Label</Label>
              <Input
                id="snapshot-label"
                value={selectedNode.data.config.snapshot_label || ''}
                onChange={(e) => handleUpdate('snapshot_label', e.target.value)}
                placeholder="today"
              />
              <p className="text-xs text-muted-foreground">
                Unique label for this snapshot (e.g., "today", "baseline")
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="retention-days">Retention Days</Label>
              <Input
                id="retention-days"
                type="number"
                value={selectedNode.data.config.retention_days || 30}
                onChange={(e) => handleUpdate('retention_days', parseInt(e.target.value))}
                placeholder="30"
              />
              <p className="text-xs text-muted-foreground">
                Number of days to keep this snapshot (default: 30)
              </p>
            </div>

            <Card className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800">
              <CardContent className="pt-4 pb-3">
                <p className="text-xs text-muted-foreground">
                  <strong>Snapshot Storage:</strong> Data is automatically stored using tiered strategy:
                  inline (&lt;10MB), file (10-100MB), or chunked (&gt;100MB). Context includes user ID and query parameters
                  for multi-tenant isolation.
                </p>
              </CardContent>
            </Card>
          </>
        )}

        {/* Compare Node */}
        {selectedNode.data.type === 'compare' && (
          <>
            <Card className="bg-purple-50 border-purple-200 dark:bg-purple-950 dark:border-purple-800">
              <CardContent className="pt-4 pb-3 space-y-3">
                <p className="text-sm font-semibold text-purple-900 dark:text-purple-100">
                  Automatic Snapshot Comparison
                </p>
                <p className="text-xs text-muted-foreground">
                  This node automatically detects snapshots from the connected source node (HANA, API, etc.).
                  It compares the baseline (first run) with the current data and returns changed rows.
                </p>
                <div className="text-xs bg-white/50 dark:bg-black/20 p-2 rounded space-y-1">
                  <div><strong>Output includes:</strong></div>
                  <ul className="list-disc list-inside space-y-0.5 ml-2">
                    <li><code>changed_rows.added</code> - New rows</li>
                    <li><code>changed_rows.removed</code> - Deleted rows</li>
                    <li><code>changed_rows.modified</code> - Updated rows</li>
                    <li><code>has_changes</code> - Boolean flag</li>
                    <li><code>change_percentage</code> - Percent changed</li>
                  </ul>
                </div>
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  <strong>Note:</strong> Connect this node to a source node (HANA, API, etc.) with "Enable Snapshots" checked.
                  Run the workflow at least twice to generate comparison data.
                </p>
              </CardContent>
            </Card>

            {/* Watch Columns Configuration */}
            <CompareNodeWatchColumns
              selectedNode={selectedNode}
              handleUpdate={handleUpdate}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
}
