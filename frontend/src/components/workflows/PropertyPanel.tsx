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
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Trash2, X, Sparkles, Code, List, Copy, Check, Maximize2 } from 'lucide-react';
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
import { RichTextEditor } from '@/components/microsites/RichTextEditor';
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

  // Find the immediate upstream node id (single inbound edge); used to prefill
  // conditional field_path. If multiple inbound edges exist, we don't guess.
  const upstreamNodeId = useGraphStore(
    React.useCallback(
      (state) => {
        if (!selectedNodeId) return undefined;
        const inbound = state.edges.filter((e: any) => e.target === selectedNodeId);
        if (inbound.length !== 1) return undefined;
        return inbound[0].source as string;
      },
      [selectedNodeId]
    )
  );

  // Track "Copied!" feedback for the Node ID copy button
  const [copiedId, setCopiedId] = React.useState(false);
  const [emailBodyExpanded, setEmailBodyExpanded] = React.useState(false);
  const handleCopyId = React.useCallback(async () => {
    if (!selectedNode?.id) return;
    try {
      await navigator.clipboard.writeText(selectedNode.id);
    } catch {
      // Older browsers / non-secure contexts: fall back to a temp textarea.
      const ta = document.createElement('textarea');
      ta.value = selectedNode.id;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 1500);
  }, [selectedNode?.id]);

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

  // Auto-prefill conditional field_path with "<upstreamNodeId>." when blank.
  // Only fires for conditional nodes that have exactly one inbound edge and
  // no field_path set. The user can still edit or clear it freely.
  React.useEffect(() => {
    if (selectedNode.data.type !== 'conditional') return;
    if (!upstreamNodeId) return;
    const current = selectedNode.data.config?.field_path;
    if (current && current.length > 0) return;
    handleUpdate('field_path', `${upstreamNodeId}.`);
    // handleUpdate intentionally omitted: it reads from refs/store, not props
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNode.id, selectedNode.data.type, upstreamNodeId]);

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
          <Label htmlFor="node-id">Node ID</Label>
          <div className="flex gap-2">
            <Input
              id="node-id"
              value={selectedNode.id}
              readOnly
              className="bg-muted font-mono text-xs"
              onFocus={(e) => e.currentTarget.select()}
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={handleCopyId}
              title={copiedId ? 'Copied!' : 'Copy Node ID'}
              aria-label="Copy Node ID"
            >
              {copiedId ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Use this ID in conditional or template field paths, e.g. <code>{`${selectedNode.id}.row_count`}</code>
          </p>
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
              <Label htmlFor="field-path">Field Path</Label>
              <Input
                id="field-path"
                value={selectedNode.data.config.field_path || ''}
                onChange={(e) => handleUpdate('field_path', e.target.value)}
                placeholder={upstreamNodeId ? `${upstreamNodeId}.fieldName` : 'nodeId.fieldName'}
              />
              <p className="text-xs text-muted-foreground">
                Format: <code>nodeId.fieldName</code> reads from another node's output. A name without a dot reads from workflow input.
                {upstreamNodeId && (
                  <>
                    {' '}
                    <button
                      type="button"
                      className="underline underline-offset-2 hover:text-foreground"
                      onClick={() => handleUpdate('field_path', `${upstreamNodeId}.`)}
                    >
                      Use upstream node
                    </button>
                  </>
                )}
              </p>
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

        {/* Notify Node — fire-and-forget user notification, does NOT pause workflow */}
        {selectedNode.data.type === 'notify' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="notify-title">Title</Label>
              <Input
                id="notify-title"
                value={selectedNode.data.config.notify_title || ''}
                onChange={(e) => handleUpdate('notify_title', e.target.value)}
                placeholder="e.g. Account brief ready: {{input.company_name}}"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notify-message">Message</Label>
              <Textarea
                id="notify-message"
                value={selectedNode.data.config.notify_message || ''}
                onChange={(e) => handleUpdate('notify_message', e.target.value)}
                rows={3}
                placeholder="Body shown in inbox + toast. Supports {{node-id.field}}."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notify-priority">Priority</Label>
              <Select
                value={selectedNode.data.config.notify_priority || 'normal'}
                onValueChange={(value) => handleUpdate('notify_priority', value)}
              >
                <SelectTrigger id="notify-priority">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notify-action-url">Action URL (optional)</Label>
              <Input
                id="notify-action-url"
                value={selectedNode.data.config.notify_action_url || ''}
                onChange={(e) => handleUpdate('notify_action_url', e.target.value)}
                placeholder="/workspaces/{{notebook-save.notebook_id}}"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notify-action-label">Action Label (optional)</Label>
              <Input
                id="notify-action-label"
                value={selectedNode.data.config.notify_action_label || ''}
                onChange={(e) => handleUpdate('notify_action_label', e.target.value)}
                placeholder="Open workspace"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="notify-user-ids">User IDs (optional, comma-separated)</Label>
              <Input
                id="notify-user-ids"
                value={selectedNode.data.config.notify_user_ids?.join(', ') || ''}
                onChange={(e) => handleUpdate(
                  'notify_user_ids',
                  e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
                )}
                placeholder="Defaults to the workflow's running user"
              />
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

        {/* JQ Node */}
        {selectedNode.data.type === 'jq' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="jq-expression">jq Expression</Label>
              <Textarea
                id="jq-expression"
                value={selectedNode.data.config.jq_expression || ''}
                onChange={(e) => handleUpdate('jq_expression', e.target.value)}
                rows={4}
                placeholder=".items | map(select(.active)) | .[].name"
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                Standard jq syntax. Examples: <code className="font-mono">.</code>,{' '}
                <code className="font-mono">.users[].email</code>,{' '}
                <code className="font-mono">{'{name, count: (.items | length)}'}</code>
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="jq-input-source">Input Source (optional)</Label>
              <Input
                id="jq-input-source"
                value={selectedNode.data.config.jq_input_source || ''}
                onChange={(e) => handleUpdate('jq_input_source', e.target.value)}
                placeholder="{{hana_table-XXX.data}}"
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                Template selecting which JSON to feed in. Leave empty to use the most recent upstream node output.
              </p>
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Tip: HANA / API nodes return an envelope like{' '}
                <code className="font-mono">{'{data: [...], row_count, ...}'}</code>. To run filters
                like <code className="font-mono">group_by</code> or <code className="font-mono">map</code>{' '}
                on the rows, point at the array directly:{' '}
                <code className="font-mono">{'{{node-id.data}}'}</code>.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="jq-output-mode">Output Mode</Label>
              <Select
                value={selectedNode.data.config.jq_output_mode || 'first'}
                onValueChange={(value) => handleUpdate('jq_output_mode', value)}
              >
                <SelectTrigger id="jq-output-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="first">First result</SelectItem>
                  <SelectItem value="all">All results (array)</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                jq filters can yield multiple values. Pick one or collect them all.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="jq-on-error">On Error</Label>
              <Select
                value={selectedNode.data.config.jq_on_error || 'fail'}
                onValueChange={(value) => handleUpdate('jq_on_error', value)}
              >
                <SelectTrigger id="jq-on-error">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fail">Fail the workflow</SelectItem>
                  <SelectItem value="null">Return null and continue</SelectItem>
                </SelectContent>
              </Select>
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

        {/* Email Node */}
        {selectedNode.data.type === 'email' && (
          <>
            <div className="rounded-md bg-muted/50 border border-dashed p-2 text-xs text-muted-foreground">
              Uses the SMTP server configured under <span className="font-medium">Settings → SMTP</span>.
              Make sure it is set and tested before running this workflow.
            </div>

            <div className="space-y-2">
              <Label htmlFor="email-to">To</Label>
              <Input
                id="email-to"
                value={(selectedNode.data.config.email_to || []).join(', ')}
                onChange={(e) =>
                  handleUpdate(
                    'email_to',
                    e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean)
                  )
                }
                placeholder="user@example.com, {{input-1.email}}"
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated. Supports <code>{'{{node-id.field}}'}</code> templates.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email-cc">CC (optional)</Label>
              <Input
                id="email-cc"
                value={(selectedNode.data.config.email_cc || []).join(', ')}
                onChange={(e) =>
                  handleUpdate(
                    'email_cc',
                    e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean)
                  )
                }
                placeholder="cc@example.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email-bcc">BCC (optional)</Label>
              <Input
                id="email-bcc"
                value={(selectedNode.data.config.email_bcc || []).join(', ')}
                onChange={(e) =>
                  handleUpdate(
                    'email_bcc',
                    e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean)
                  )
                }
                placeholder="bcc@example.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email-subject">Subject</Label>
              <Input
                id="email-subject"
                value={selectedNode.data.config.email_subject || ''}
                onChange={(e) => handleUpdate('email_subject', e.target.value)}
                placeholder="Hello {{input-1.name}}"
              />
            </div>

            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Checkbox
                  checked={selectedNode.data.config.email_is_html !== false}
                  onCheckedChange={(checked) => handleUpdate('email_is_html', checked === true)}
                />
                Send as HTML
              </Label>
              <p className="text-xs text-muted-foreground">
                When off, the body is sent as plain text.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Body</Label>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-xs"
                  onClick={() => setEmailBodyExpanded(true)}
                >
                  <Maximize2 className="h-3 w-3 mr-1" />
                  Expand
                </Button>
              </div>
              <div className="border rounded-md overflow-hidden">
                {emailBodyExpanded ? (
                  <div className="p-4 text-xs text-muted-foreground italic">
                    Editing in expanded view…
                  </div>
                ) : (
                  <RichTextEditor
                    content={selectedNode.data.config.email_body || ''}
                    onChange={(html) => handleUpdate('email_body', html)}
                    placeholder="Compose your email…"
                  />
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Supports <code>{'{{node-id.field}}'}</code> templates inline.
              </p>
            </div>

            <Dialog open={emailBodyExpanded} onOpenChange={setEmailBodyExpanded}>
              <DialogContent className="max-w-5xl w-[90vw] h-[85vh] flex flex-col p-0 gap-0">
                <DialogHeader className="px-6 pt-5 pb-3 border-b">
                  <DialogTitle>Email Body</DialogTitle>
                </DialogHeader>
                <div className="flex-1 overflow-auto px-6 py-4">
                  <div className="border rounded-md overflow-hidden h-full">
                    <RichTextEditor
                      content={selectedNode.data.config.email_body || ''}
                      onChange={(html) => handleUpdate('email_body', html)}
                      placeholder="Compose your email…"
                    />
                  </div>
                </div>
                <DialogFooter className="px-6 py-3 border-t">
                  <p className="text-xs text-muted-foreground mr-auto">
                    Supports <code>{'{{node-id.field}}'}</code> templates inline.
                  </p>
                  <Button onClick={() => setEmailBodyExpanded(false)}>Done</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
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

        {/* ForEach Node */}
        {selectedNode.data.type === 'foreach' && (
          <>
            <div className="space-y-2">
              <Label htmlFor="foreach-source">Source (template referencing a list)</Label>
              <Input
                id="foreach-source"
                value={selectedNode.data.config.foreach_source || ''}
                onChange={(e) => handleUpdate('foreach_source', e.target.value)}
                placeholder="{{hana-NODE-ID.rows}}"
                className="font-mono text-xs"
              />
              <p className="text-[11px] text-muted-foreground">
                Must resolve to a list. Example: <code>{'{{hana-NODE-ID.rows}}'}</code> or <code>{'{{api-NODE-ID.data}}'}</code>.
              </p>
            </div>

            <div className="rounded border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/30 p-2 text-[11px] space-y-1">
              <div className="font-semibold text-emerald-700 dark:text-emerald-300">Wiring</div>
              <p className="text-muted-foreground">
                Connect the <strong className="text-emerald-600 dark:text-emerald-400">each</strong> handle to the chain that should run once per item, and the <strong className="text-sky-600 dark:text-sky-400">done</strong> handle to whatever runs after all items finish.
              </p>
              <p className="text-muted-foreground">
                Inside the each-chain, templates can use <code>{'{{item.FIELD}}'}</code>, <code>{'{{index}}'}</code>, <code>{'{{total}}'}</code>.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="foreach-on-error">On iteration error</Label>
              <Select
                value={selectedNode.data.config.foreach_on_error || 'continue'}
                onValueChange={(value) => handleUpdate('foreach_on_error', value)}
              >
                <SelectTrigger id="foreach-on-error">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="continue">Continue (record error, keep going)</SelectItem>
                  <SelectItem value="fail">Fail (stop the whole node)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="foreach-max">Max items</Label>
              <Input
                id="foreach-max"
                type="number"
                min={1}
                value={selectedNode.data.config.foreach_max_items ?? 1000}
                onChange={(e) => handleUpdate('foreach_max_items', parseInt(e.target.value || '0', 10) || 0)}
              />
              <p className="text-[11px] text-muted-foreground">Hard cap on iterations. Extra rows are dropped.</p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
