/**
 * Workflow Editor Page
 *
 * Visual workflow editor with graph canvas and property panel.
 */

import React from 'react';
import { useParams, useRouter } from '@/lib/routing/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { ArrowLeft, Save, Play, Settings, History, Loader2, Plus, FileText, Globe } from 'lucide-react';
import { GraphEditor, getCurrentGraphState } from '@/components/workflows/GraphEditor';
import { PropertyPanel } from '@/components/workflows/PropertyPanel';
import { useGraphStore } from '@/lib/stores/graph-store';
import { useSidebarStore } from '@/lib/stores/sidebar-store';
import { useAuthStore } from '@/lib/stores/auth-store';
import { workflowsApi } from '@/lib/api/workflows';
import { workflowTemplatesApi } from '@/lib/api/workflow-templates';
import type { WorkflowCreate, WorkflowUpdate } from '@/lib/api/workflows';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useLookupList } from "@/lib/hooks/use-lookup-list";

const FALLBACK_CATEGORIES = [
  { value: "custom", label: "Custom", sort_order: 99 },
  { value: "data_processing", label: "Data Processing", sort_order: 1 },
  { value: "automation", label: "Automation", sort_order: 2 },
  { value: "analytics", label: "Analytics", sort_order: 3 },
  { value: "integration", label: "Integration", sort_order: 4 },
  { value: "ai_ml", label: "AI/ML", sort_order: 5 },
];
import {
  InputFieldsPromptDialog,
  hasRequiredInputFields,
  getRequiredInputFields,
} from '@/components/workflows/InputFieldsPromptDialog';

// ============================================================================
// Workflow Editor Page
// ============================================================================

export default function WorkflowDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  const workflowId = params.id as string;
  const isNew = workflowId === 'new';

  const {
    metadata,
    setMetadata,
    selectedNodeId,
  } = useGraphStore();

  // Get sidebar state
  const sidebarOpen = useSidebarStore((state) => state.isOpen);

  // Load workflow if editing existing
  const { data: workflow, isLoading } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowsApi.get(workflowId),
    enabled: !isNew,
  });

  // Load workflow when data is available (only once per workflow ID)
  const loadedWorkflowIdRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    console.log('[WorkflowPage] Effect triggered');
    console.log('[WorkflowPage] - workflow:', workflow?.name);
    console.log('[WorkflowPage] - isNew:', isNew);
    console.log('[WorkflowPage] - workflow.graph.nodes:', workflow?.graph?.nodes?.length);
    console.log('[WorkflowPage] - loadedWorkflowIdRef:', loadedWorkflowIdRef.current);

    // Prevent re-loading the same workflow
    if (workflow && loadedWorkflowIdRef.current === workflow.id) {
      console.log('[WorkflowPage] Workflow already loaded, skipping');
      return;
    }

    if (workflow) {
      console.log('[WorkflowPage] Calling loadWorkflow for:', workflow.name);
      console.log('[WorkflowPage] Graph has', workflow.graph.nodes.length, 'nodes and', workflow.graph.edges.length, 'edges');

      // Debug: Check HANA node config from backend
      const hanaNode = workflow.graph.nodes.find((n: any) => n.type === 'hana_table');
      if (hanaNode) {
        console.log('[WorkflowPage] HANA node from backend:', hanaNode.id);
        console.log('[WorkflowPage] HANA node config from backend:', JSON.stringify(hanaNode.config, null, 2));
        console.log('[WorkflowPage] Conditions from backend:', (hanaNode.config as any)?.conditions);
      }

      useGraphStore.getState().loadWorkflow(workflow);
      loadedWorkflowIdRef.current = workflow.id;
      console.log('[WorkflowPage] loadWorkflow called');
    } else if (isNew && loadedWorkflowIdRef.current !== 'new') {
      console.log('[WorkflowPage] Clearing graph for new workflow');
      useGraphStore.getState().clearGraph();
      loadedWorkflowIdRef.current = 'new';
    }
  }, [workflow, isNew]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async () => {
      // Get current graph state from GraphEditor module
      const { nodes: currentNodes, edges: currentEdges } = getCurrentGraphState();

      console.log('[Save] Using', currentNodes.length, 'nodes and', currentEdges.length, 'edges');

      // Convert React Flow format to API format
      const workflowData = {
        name: metadata.name,
        description: metadata.description,
        graph: {
          nodes: currentNodes.map((n: any) => {
            // Debug log for HANA nodes
            if (n.data.type === 'hana_table') {
              console.log('[Save] HANA node config:', n.id);
              console.log('[Save] Full config:', JSON.stringify(n.data.config, null, 2));
              console.log('[Save] Conditions:', n.data.config.conditions);
              console.log('[Save] hana_connection_id:', n.data.config.hana_connection_id);
              console.log('[Save] hana_table_name:', n.data.config.hana_table_name);
            }
            return {
              id: n.id,
              type: n.data.type,
              label: n.data.label,
              position: n.position,
              config: n.data.config,
            };
          }),
          edges: currentEdges.map((e: any) => {
            // Extract label from edge ID if not explicitly set
            // React Flow generates IDs like "xy-edge__conditional-1true-output-123"
            let label = e.label;
            if (!label && e.id) {
              const idLower = e.id.toLowerCase();
              if (idLower.includes('true')) {
                label = 'true';
              } else if (idLower.includes('false')) {
                label = 'false';
              }
            }

            return {
              id: e.id,
              source: e.source,
              target: e.target,
              sourceHandle: e.sourceHandle,  // Preserve source handle for conditional nodes
              targetHandle: e.targetHandle,  // Preserve target handle
              label: label,
            };
          }),
          entry_node_id: currentNodes.find((n: any) => n.data.type === 'input')?.id || currentNodes[0]?.id || '',
        },
        tags: metadata.tags || [],
        created_by: user?.id || '00000000-0000-0000-0000-000000000001', // Fallback to admin user ID
      };

      if (isNew) {
        // For create, only send name, description, graph, tags, created_by
        return workflowsApi.create(workflowData as WorkflowCreate);
      } else {
        // For update, can include is_active
        return workflowsApi.update(workflowId, {
          ...workflowData,
          is_active: metadata.is_active,
        } as WorkflowUpdate);
      }
    },
    onSuccess: (data) => {
      toast.success(`Workflow ${isNew ? 'created' : 'updated'} successfully`);

      // Force the canvas to re-sync from the freshly persisted server state on
      // the next refetch (otherwise the load guard short-circuits and any
      // post-save divergence between RF state and the store would leave stale
      // visuals — e.g. a just-created edge briefly disappearing).
      loadedWorkflowIdRef.current = null;

      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });

      if (isNew && data) {
        // Redirect to edit page for newly created workflow
        const newWorkflowId = (data as any).workflow_id || data.id;
        if (newWorkflowId) {
          router.push(`/workflows/${newWorkflowId}`);
        }
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to save workflow');
    },
  });

  // Execute mutation with polling
  const executeMutation = useMutation({
    mutationFn: (inputData?: Record<string, any>) =>
      workflowsApi.execute(workflowId, inputData),
    onSuccess: (execution) => {
      toast.success('Workflow execution started');

      // Start polling for execution status
      setCurrentExecution(execution);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to execute workflow');
    },
  });

  // Poll for execution status
  const [currentExecution, setCurrentExecution] = React.useState<any>(null);

  // Template save dialog state
  const [showTemplateDialog, setShowTemplateDialog] = React.useState(false);
  const [templateName, setTemplateName] = React.useState('');
  const [templateDescription, setTemplateDescription] = React.useState('');
  const [templateCategory, setTemplateCategory] = React.useState('custom');
  const [templateIsPublic, setTemplateIsPublic] = React.useState(false);

  // Admin-managed category options with safe fallback
  const { options: categoryOptions } = useLookupList(
    'workflow_template_categories',
    FALLBACK_CATEGORIES
  );

  // Save as template mutation
  const saveTemplateMutation = useMutation({
    mutationFn: async () => {
      // If this is a new workflow, we need to save it first
      if (isNew) {
        toast.error('Please save the workflow before creating a template');
        throw new Error('Workflow must be saved first');
      }

      return workflowTemplatesApi.create({
        workflow_id: workflowId,
        name: templateName,
        description: templateDescription,
        category: templateCategory,
        parameters: [], // Templates can define parameters if needed
        is_public: templateIsPublic,
      });
    },
    onSuccess: () => {
      toast.success('Template created successfully');
      setShowTemplateDialog(false);
      setTemplateName('');
      setTemplateDescription('');
      setTemplateCategory('custom');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to create template');
    },
  });

  const handleSaveAsTemplate = () => {
    // Pre-fill template name from workflow name
    setTemplateName(metadata.name || 'Untitled Template');
    setTemplateIsPublic(false);
    setShowTemplateDialog(true);
  };

  const handleTemplateConfirm = () => {
    if (!templateName.trim()) {
      toast.error('Please enter a template name');
      return;
    }
    saveTemplateMutation.mutate();
  };

  // Track if workflow is executing (for UI blocking)
  const isExecuting = executeMutation.isPending || (currentExecution && currentExecution.status === 'running');

  const { data: executionStatus } = useQuery({
    queryKey: ['execution-status', workflowId, currentExecution?.id],
    queryFn: () => workflowsApi.getExecution(workflowId, currentExecution.id),
    enabled: !!currentExecution && currentExecution.status === 'running',
    refetchInterval: 2000, // Poll every 2 seconds
  });

  // Update current execution when status changes
  React.useEffect(() => {
    if (executionStatus) {
      setCurrentExecution(executionStatus);

      // Stop polling when execution completes
      if (executionStatus.status !== 'running' && executionStatus.status !== 'pending') {
        setTimeout(() => {
          setCurrentExecution(null);
        }, 5000); // Clear after 5 seconds
      }
    }
  }, [executionStatus]);

  const handleSave = () => {
    saveMutation.mutate();
  };

  const [showInputPrompt, setShowInputPrompt] = React.useState(false);

  const handleExecute = () => {
    if (isNew) {
      toast.error('Please save the workflow before executing');
      return;
    }

    if (hasRequiredInputFields(workflow)) {
      setShowInputPrompt(true);
      return;
    }

    executeMutation.mutate(undefined);
  };

  const handleSettings = () => {
    router.push(`/workflows/${workflowId}/settings`);
  };

  const handleViewExecutions = () => {
    router.push(`/workflows/${workflowId}/executions`);
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto" />
          <p className="mt-4 text-muted-foreground">Loading workflow...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 top-16 flex flex-col bg-background transition-all duration-300"
      style={{
        left: sidebarOpen ? '256px' : '64px'
      }}
    >
      {/* Header */}
      <div className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 p-3">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push('/workflows')}
            disabled={isExecuting}
            className="flex-shrink-0"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>

          <Input
            value={metadata.name}
            onChange={(e) => setMetadata({ name: e.target.value })}
            className="w-48"
            placeholder="Workflow name"
            disabled={isExecuting}
          />

          <div className="h-6 w-px bg-border" />

          {/* Add Nodes Toolbar - Scrollable Container */}
          <div className="flex items-center gap-2 flex-1 overflow-x-auto">
            <span className="text-xs font-medium text-muted-foreground shrink-0">Add Nodes:</span>
            <div className="flex items-center gap-1.5 flex-wrap">
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('input')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Input
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('llm')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                LLM
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('tool')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Tool
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('agent')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Agent
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('conditional')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Cond
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('output')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Output
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('notebook_generator')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Notebook
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('microsite_generator')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Microsite
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('human_approval')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Approval
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('workspace')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Workspace
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('template')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Template
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('delay')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Delay
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('webhook')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Webhook
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('email')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Email
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('hana_table')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Hana Table
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('api')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                API
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('compare')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                Compare
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('foreach')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                ForEach
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => (window as any).__workflowAddNode?.('jq')}
                disabled={isExecuting}
                className="h-7 px-2 text-xs shrink-0"
              >
                <Plus className="h-3 w-3 mr-1" />
                JQ
              </Button>
            </div>
          </div>

          <div className="h-6 w-px bg-border shrink-0" />

          <div className="flex items-center gap-1.5 ml-auto">
            {isNew && (
              <div className="text-xs text-muted-foreground bg-muted px-3 py-1.5 rounded-md mr-2">
                💡 Save workflow first to access more features
              </div>
            )}
            {!isNew && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSaveAsTemplate}
                  disabled={isExecuting || saveTemplateMutation.isPending}
                  title="Save as Template"
                  className="h-8 px-3"
                >
                  <FileText className="h-3.5 w-3.5 mr-1.5" />
                  Save as Template
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleViewExecutions}
                  disabled={isExecuting}
                  title="View Executions"
                  className="h-8 w-8"
                >
                  <History className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleSettings}
                  disabled={isExecuting}
                  title="Settings"
                  className="h-8 w-8"
                >
                  <Settings className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleExecute}
                  disabled={isExecuting}
                  title="Execute Workflow"
                  className="h-8 w-8"
                >
                  <Play className="h-4 w-4" />
                </Button>
              </>
            )}
            <Button
              size="icon"
              onClick={handleSave}
              disabled={saveMutation.isPending || isExecuting}
              title={saveMutation.isPending ? 'Saving...' : 'Save Workflow'}
              className="h-8 w-8"
            >
              {saveMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Editor Layout */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Execution Overlay - blocks canvas during execution */}
        {isExecuting && (
          <div className="absolute inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center">
            <div className="bg-card border rounded-lg p-8 shadow-2xl max-w-md">
              <div className="flex flex-col items-center gap-4">
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
                <div className="text-center">
                  <h3 className="text-lg font-semibold mb-2">Executing Workflow</h3>
                  <p className="text-sm text-muted-foreground">
                    Processing nodes in the backend...
                  </p>
                  {currentExecution && (
                    <div className="mt-4 text-xs text-muted-foreground">
                      <div>Execution ID: {currentExecution.id}</div>
                      <div className="mt-2">
                        Status: <span className="font-medium text-foreground">{currentExecution.status}</span>
                      </div>
                      {currentExecution.node_states && (
                        <div className="mt-2">
                          Nodes: {Object.keys(currentExecution.node_states).length} processed
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Graph Canvas */}
        <div className="flex-1 relative">
          <GraphEditor
            workflowId={workflowId}
            execution={currentExecution}
            showToolbar={!isExecuting}
          />
        </div>

        {/* Property Panel - Only show when a node is selected */}
        {selectedNodeId && (
          <div className="border-l">
            <PropertyPanel />
          </div>
        )}
      </div>

      {/* Required Input Fields Prompt Dialog */}
      <InputFieldsPromptDialog
        open={showInputPrompt}
        onOpenChange={setShowInputPrompt}
        fields={getRequiredInputFields(workflow)}
        title="Provide Workflow Inputs"
        description="This workflow requires input values before it can run."
        submitLabel="Execute"
        submitting={executeMutation.isPending}
        onSubmit={(values) => {
          setShowInputPrompt(false);
          executeMutation.mutate(values);
        }}
      />

      {/* Save as Template Dialog */}
      <Dialog open={showTemplateDialog} onOpenChange={setShowTemplateDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Save as Template</DialogTitle>
            <DialogDescription>
              Create a reusable template from this workflow. Templates can be used to quickly create new workflows.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="template-name">Template Name *</Label>
              <Input
                id="template-name"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="My Workflow Template"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="template-description">Description</Label>
              <Textarea
                id="template-description"
                value={templateDescription}
                onChange={(e) => setTemplateDescription(e.target.value)}
                placeholder="Describe what this template does..."
                rows={3}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="template-category">Category</Label>
              <select
                id="template-category"
                value={templateCategory}
                onChange={(e) => setTemplateCategory(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {categoryOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center space-x-2 pt-2 pb-2 px-3 bg-muted/50 rounded-lg border border-dashed">
              <Checkbox
                id="template-public"
                checked={templateIsPublic}
                onCheckedChange={(checked) => setTemplateIsPublic(checked as boolean)}
              />
              <div className="flex-1">
                <Label htmlFor="template-public" className="font-medium cursor-pointer flex items-center gap-2">
                  <Globe className="h-4 w-4 text-blue-500" />
                  Publish to Public Gallery
                </Label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Make this template available to all users in the template gallery
                </p>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowTemplateDialog(false)}
              disabled={saveTemplateMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleTemplateConfirm}
              disabled={saveTemplateMutation.isPending || !templateName.trim()}
            >
              {saveTemplateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Template'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
