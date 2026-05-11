/**
 * Custom Node Components for React Flow
 *
 * Beautiful, professional visual representations of workflow nodes.
 */

import React from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Bot, Wrench, Split, ArrowDownCircle, ArrowUpCircle, Loader2, CheckCircle, XCircle, Sparkles, Users, BookOpen, Globe, Clock, Webhook, GitBranch, FileStack, Database } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { NodeData } from '@/lib/stores/graph-store';

// ============================================================================
// Helper Functions
// ============================================================================

const getStatusBadge = (status?: NodeData['status']) => {
  if (!status) return null;

  const variants = {
    pending: { variant: 'secondary' as const, icon: null, label: 'Pending' },
    running: { variant: 'default' as const, icon: Loader2, label: 'Running' },
    completed: { variant: 'default' as const, icon: CheckCircle, label: 'Done' },
    failed: { variant: 'destructive' as const, icon: XCircle, label: 'Failed' },
  };

  const config = variants[status];
  const Icon = config.icon;

  return (
    <Badge variant={config.variant} className="text-[10px] px-1.5 py-0 h-4 flex-shrink-0">
      {Icon && <Icon className={cn("h-2.5 w-2.5 mr-0.5", status === 'running' && "animate-spin")} />}
      {config.label}
    </Badge>
  );
};

// Custom handle style - smaller for compact nodes
const handleStyle = {
  width: '10px',
  height: '10px',
  border: '2px solid white',
  boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
};

// ============================================================================
// Input Node
// ============================================================================

export function InputNode({ data, selected }: any) {
  const inputFields = data.config.input_fields || [];

  return (
    // Use a wrapper with a fixed width that matches your card - COMPACT
    <div className="relative w-[220px] h-auto">
      <Card className={cn(
        "w-full transition-all duration-200", // Card takes full width of wrapper
        "bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-950 dark:to-cyan-950",
        "border",
        selected ? "ring-2 ring-blue-500/50 border-blue-500 shadow-lg" : "border-blue-200 dark:border-blue-800 hover:border-blue-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-primary text-primary-foreground shadow-sm flex-shrink-0">
                <ArrowDownCircle className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">
                  {inputFields.length > 0
                    ? `${inputFields.length} field${inputFields.length !== 1 ? 's' : ''}`
                    : 'Entry point'}
                </p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>
      </Card>

      {/* Output Handle - Positioned correctly on the right edge */}
      <Handle
        type="source"
        position={Position.Right}
        id="output"
        isConnectable={true}
        className="!bg-blue-500"
        style={{ ...handleStyle, right: '-5px' }} // Pull it slightly out so it sits ON the border
      />
    </div>
  );
}
// ============================================================================
// Output Node
// ============================================================================

export function OutputNode({ data, selected }: any) {
  return (
    <>
      {/* Input Handle - Left side, centered vertically */}
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-blue-500"
        style={handleStyle}
      />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-950 dark:to-cyan-950",
        "border",
        selected ? "ring-2 ring-blue-500/50 border-blue-500 shadow-lg" : "border-blue-200 dark:border-blue-800 hover:border-blue-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-primary text-primary-foreground shadow-sm flex-shrink-0">
                <ArrowUpCircle className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Exit point</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>
      </Card>
    </>
  );
}

// ============================================================================
// LLM Node
// ============================================================================

export function LLMNode({ data, selected }: any) {
  return (
    <>
      {/* Input Handle - Left side, centered vertically */}
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-purple-500"
        style={handleStyle}
      />

      <Card className={cn(
        "min-w-[240px] transition-all duration-200",
        "bg-gradient-to-br from-purple-50 via-violet-50 to-fuchsia-50 dark:from-purple-950 dark:via-violet-950 dark:to-fuchsia-950",
        "border",
        selected ? "ring-2 ring-purple-500/50 border-purple-500 shadow-lg" : "border-purple-200 dark:border-purple-800 hover:border-purple-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-gradient-to-br from-purple-500 to-fuchsia-500 text-white shadow-sm flex-shrink-0">
                <Sparkles className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">AI model</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {data.config.model_name && (
            <div className="flex items-center gap-1.5">
              <Bot className="h-3 w-3 text-purple-500 flex-shrink-0" />
              <span className="text-[10px] font-medium truncate">{data.config.model_name}</span>
            </div>
          )}
          {data.config.temperature !== undefined && (
            <div className="text-[10px] text-muted-foreground">
              Temp: {data.config.temperature}
            </div>
          )}
          {!data.config.model_name && (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Not configured
            </div>
          )}
        </CardContent>
      </Card>

      {/* Output Handle - Right side, centered vertically */}
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-purple-500"
        style={handleStyle}
      />
    </>
  );
}

// ============================================================================
// Tool Node
// ============================================================================

export function ToolNode({ data, selected }: any) {
  return (
    <>
      {/* Input Handle - Left side, centered vertically */}
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-orange-500"
        style={handleStyle}
      />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950 dark:to-amber-950",
        "border",
        selected ? "ring-2 ring-orange-500/50 border-orange-500 shadow-lg" : "border-orange-200 dark:border-orange-800 hover:border-orange-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-orange-500 text-white shadow-sm flex-shrink-0">
                <Wrench className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Tool</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3">
          {data.config.tool_name ? (
            <div className="flex items-center gap-1.5 bg-white/50 dark:bg-black/20 p-1.5 rounded">
              <Wrench className="h-3 w-3 text-orange-500 flex-shrink-0" />
              <span className="text-[10px] font-medium truncate">{data.config.tool_name}</span>
            </div>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Not selected
            </div>
          )}
        </CardContent>
      </Card>

      {/* Output Handle - Right side, centered vertically */}
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-orange-500"
        style={handleStyle}
      />
    </>
  );
}

// ============================================================================
// Conditional Node
// ============================================================================

export function ConditionalNode({ data, selected }: any) {
  return (
    <>
      {/* Input handle - Left side */}
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-yellow-500"
        style={handleStyle}
      />

      <div className="relative w-[140px] h-[140px]">
        {/* Diamond shape using transform */}
        <div className={cn(
          "absolute inset-0 transform rotate-45 transition-all duration-200",
          "bg-gradient-to-br from-yellow-50 to-amber-50 dark:from-yellow-950 dark:to-amber-950",
          "border rounded-xl shadow",
          selected ? "ring-2 ring-yellow-500/50 border-yellow-500 shadow-lg" : "border-yellow-200 dark:border-yellow-800 hover:border-yellow-400"
        )} />

        {/* Content (counter-rotated to be readable) */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="transform -rotate-0 text-center px-2 max-w-[120px]">
            <div className="flex flex-col items-center gap-1">
              <div className="p-1.5 rounded bg-yellow-500 text-white shadow-sm">
                <Split className="h-3.5 w-3.5" />
              </div>
              <div>
                <div className="font-semibold text-xs mb-0.5 line-clamp-2">{data.label}</div>
                {data.config.condition_type && (
                  <div className="text-[9px] text-muted-foreground uppercase tracking-wide">
                    {data.config.condition_type.replace('_', ' ')}
                  </div>
                )}
              </div>
              {getStatusBadge(data.status)}
            </div>
          </div>
        </div>
      </div>

      {/* Output handles for true/false branches */}
      <Handle
        type="source"
        position={Position.Top}
        id="true"
        className="!bg-green-500"
        style={{ ...handleStyle, top: '-5px' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        className="!bg-red-500"
        style={{ ...handleStyle, bottom: '-5px' }}
      />
    </>
  );
}

// ============================================================================
// Agent Node
// ============================================================================

export function AgentNode({ data, selected }: any) {
  return (
    <>
      {/* Input Handle - Left side, centered vertically */}
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-teal-500"
        style={handleStyle}
      />

      <Card className={cn(
        "min-w-[240px] transition-all duration-200",
        "bg-gradient-to-br from-teal-50 via-cyan-50 to-sky-50 dark:from-teal-950 dark:via-cyan-950 dark:to-sky-950",
        "border",
        selected ? "ring-2 ring-teal-500/50 border-teal-500 shadow-lg" : "border-teal-200 dark:border-teal-800 hover:border-teal-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-gradient-to-br from-teal-500 to-cyan-500 text-white shadow-sm flex-shrink-0">
                <Users className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Agent</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {data.config.agent_name && data.config.agent_type && (
            <>
              <div className="flex items-center gap-1.5">
                <Users className="h-3 w-3 text-teal-500 flex-shrink-0" />
                <span className="text-[10px] font-medium truncate">{data.config.agent_name}</span>
              </div>
              <div className="text-[10px] text-muted-foreground">
                Type: <span className="capitalize">{data.config.agent_type}</span>
              </div>
            </>
          )}
          {!data.config.agent_name && (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Not selected
            </div>
          )}
        </CardContent>
      </Card>

      {/* Output Handle - Right side, centered vertically */}
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-teal-500"
        style={handleStyle}
      />
    </>
  );
}

// ============================================================================
// Notebook Generator Node
// ============================================================================

export function NotebookGeneratorNode({ data, selected }: any) {
  const sourceMode = data.config.source_mode || 'create_from_content';
  const notebookName = data.config.notebook_name || 'Generated Notebook';

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-purple-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[240px] transition-all duration-200",
        "bg-gradient-to-br from-purple-50 via-violet-50 to-indigo-50 dark:from-purple-950 dark:via-violet-950 dark:to-indigo-950",
        "border",
        selected ? "ring-2 ring-purple-500/50 border-purple-500 shadow-lg" : "border-purple-200 dark:border-purple-800 hover:border-purple-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-gradient-to-br from-purple-500 to-indigo-500 text-white shadow-sm flex-shrink-0">
                <BookOpen className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Create notebook</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {notebookName && (
            <div className="flex items-center gap-1.5 bg-white/50 dark:bg-black/20 p-1.5 rounded">
              <BookOpen className="h-3 w-3 text-purple-500 flex-shrink-0" />
              <span className="text-[10px] font-medium truncate">{notebookName}</span>
            </div>
          )}
          <div className="text-[10px] text-muted-foreground">
            Mode: <span className="capitalize font-medium">{sourceMode.replace(/_/g, ' ')}</span>
          </div>
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-purple-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Microsite Generator Node
// ============================================================================

export function MicrositeGeneratorNode({ data, selected }: any) {
  const micrositeTitle = data.config.microsite_title || 'Generated Microsite';
  const templateId = data.config.template_id;
  const autoPublish = data.config.auto_publish;

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-pink-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[240px] transition-all duration-200",
        "bg-gradient-to-br from-pink-50 via-rose-50 to-fuchsia-50 dark:from-pink-950 dark:via-rose-950 dark:to-fuchsia-950",
        "border",
        selected ? "ring-2 ring-pink-500/50 border-pink-500 shadow-lg" : "border-pink-200 dark:border-pink-800 hover:border-pink-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-gradient-to-br from-pink-500 to-fuchsia-500 text-white shadow-sm flex-shrink-0">
                <Globe className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Microsite</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {micrositeTitle && (
            <div className="flex items-center gap-1.5 bg-white/50 dark:bg-black/20 p-1.5 rounded">
              <Globe className="h-3 w-3 text-pink-500 flex-shrink-0" />
              <span className="text-[10px] font-medium truncate">{micrositeTitle}</span>
            </div>
          )}
          {templateId ? (
            <div className="text-[10px] text-muted-foreground">
              Template: <span className="font-medium">{templateId}</span>
            </div>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Not selected
            </div>
          )}
          {autoPublish && (
            <div className="text-[10px] text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30 p-1 rounded flex items-center gap-1">
              <CheckCircle className="h-2.5 w-2.5" />
              Auto-publish
            </div>
          )}
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-pink-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Human Approval Node
// ============================================================================

export function HumanApprovalNode({ data, selected }: any) {
  const approvalPrompt = data.config.approval_prompt || 'Please review and approve';
  const timeoutSeconds = data.config.timeout_seconds;
  const requiredApprovers = data.config.required_approvers || [];

  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-amber-500"
        style={handleStyle}
      />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950 dark:to-orange-950",
        "border",
        selected ? "ring-2 ring-amber-500/50 border-amber-500 shadow-lg" : "border-amber-200 dark:border-amber-800 hover:border-amber-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-amber-500 text-white shadow-sm flex-shrink-0">
                <CheckCircle className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Human approval required</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded">
            <span className="font-medium line-clamp-2">{approvalPrompt}</span>
          </div>
          {timeoutSeconds && (
            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Timeout: {Math.floor(timeoutSeconds / 60)}m
            </div>
          )}
          {requiredApprovers.length > 0 && (
            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
              <Users className="h-3 w-3" />
              {requiredApprovers.length} approver(s)
            </div>
          )}
        </CardContent>
      </Card>

      {/* Two output handles: approved and rejected */}
      <Handle
        type="source"
        position={Position.Right}
        id="approved"
        className="!bg-green-500"
        style={{ top: '35%', ...handleStyle }}
      />
      <div className="absolute right-[-65px] top-[calc(35%-12px)] text-[10px] font-semibold text-green-600 dark:text-green-400 bg-white dark:bg-gray-900 px-1 py-0.5 rounded border border-green-200 dark:border-green-800">
        Approved
      </div>

      <Handle
        type="source"
        position={Position.Right}
        id="rejected"
        className="!bg-red-500"
        style={{ top: '65%', ...handleStyle }}
      />
      <div className="absolute right-[-65px] top-[calc(65%-12px)] text-[10px] font-semibold text-red-600 dark:text-red-400 bg-white dark:bg-gray-900 px-1 py-0.5 rounded border border-red-200 dark:border-red-800">
        Rejected
      </div>
    </>
  );
}

// ============================================================================
// Workspace Template Node
// ============================================================================

export function WorkspaceNode({ data, selected }: any) {
  const templateId = data.config.workspace_template_id;
  const waitForCompletion = data.config.wait_for_completion !== false;

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-indigo-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-indigo-50 to-violet-50 dark:from-indigo-950 dark:to-violet-950",
        "border",
        selected ? "ring-2 ring-indigo-500/50 border-indigo-500 shadow-lg" : "border-indigo-200 dark:border-indigo-800 hover:border-indigo-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-indigo-500 text-white shadow-sm flex-shrink-0">
                <BookOpen className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Workspace</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {templateId ? (
            <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded truncate">
              {templateId.substring(0, 8)}...
            </div>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Not selected
            </div>
          )}
          {waitForCompletion && (
            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
              <CheckCircle className="h-2.5 w-2.5" />
              Wait for completion
            </div>
          )}
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-indigo-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Workflow Template Node
// ============================================================================

export function TemplateNode({ data, selected }: any) {
  const templateId = data.config.template_id;
  const waitForCompletion = data.config.wait_for_completion !== false;

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-teal-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-teal-50 to-cyan-50 dark:from-teal-950 dark:to-cyan-950",
        "border",
        selected ? "ring-2 ring-teal-500/50 border-teal-500 shadow-lg" : "border-teal-200 dark:border-teal-800 hover:border-teal-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-teal-500 text-white shadow-sm flex-shrink-0">
                <GitBranch className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Template</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {templateId ? (
            <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded truncate">
              {templateId.substring(0, 8)}...
            </div>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Not selected
            </div>
          )}
          {waitForCompletion && (
            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
              <CheckCircle className="h-2.5 w-2.5" />
              Wait for completion
            </div>
          )}
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-teal-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Delay Node
// ============================================================================

export function DelayNode({ data, selected }: any) {
  const delaySeconds = data.config.delay_seconds;
  const delayExpression = data.config.delay_expression;

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-gray-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-gray-50 to-slate-50 dark:from-gray-950 dark:to-slate-950",
        "border",
        selected ? "ring-2 ring-gray-500/50 border-gray-500 shadow-lg" : "border-gray-200 dark:border-gray-800 hover:border-gray-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-gray-500 text-white shadow-sm flex-shrink-0">
                <Clock className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Pause</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {delaySeconds ? (
            <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded">
              <Clock className="h-3 w-3 inline mr-1" />
              {delaySeconds}s ({Math.floor(delaySeconds / 60)}m)
            </div>
          ) : delayExpression ? (
            <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded truncate">
              <span className="font-mono">{delayExpression}</span>
            </div>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Not configured
            </div>
          )}
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-gray-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Webhook Node
// ============================================================================

export function WebhookNode({ data, selected }: any) {
  const webhookUrl = data.config.webhook_url;
  const webhookMethod = data.config.webhook_method || 'POST';
  const authType = data.config.webhook_auth_type || 'none';

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-emerald-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-emerald-50 to-green-50 dark:from-emerald-950 dark:to-green-950",
        "border",
        selected ? "ring-2 ring-emerald-500/50 border-emerald-500 shadow-lg" : "border-emerald-200 dark:border-emerald-800 hover:border-emerald-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-emerald-500 text-white shadow-sm flex-shrink-0">
                <Webhook className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">HTTP request</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {webhookUrl ? (
            <>
              <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded">
                <Badge variant="secondary" className="text-[9px] px-1 py-0 h-3.5 mb-0.5">{webhookMethod}</Badge>
                <div className="font-mono truncate mt-0.5">{webhookUrl}</div>
              </div>
              {authType !== 'none' && (
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <CheckCircle className="h-2.5 w-2.5" />
                  Auth: {authType}
                </div>
              )}
            </>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              URL not configured
            </div>
          )}
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-emerald-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Hana Table Node
// ============================================================================

export function HanaTableNode({ data, selected }: any) {
  const connectionId = data.config.hana_connection_id;
  const tableName = data.config.hana_table_name;
  const conditions = data.config.conditions || [];

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-cyan-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-cyan-50 to-blue-50 dark:from-cyan-950 dark:to-blue-950",
        "border",
        selected ? "ring-2 ring-cyan-500/50 border-cyan-500 shadow-lg" : "border-cyan-200 dark:border-cyan-800 hover:border-cyan-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-cyan-500 text-white shadow-sm flex-shrink-0">
                <Database className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">HANA Table Query</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {tableName ? (
            <>
              <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded">
                <div className="font-mono font-semibold truncate">{tableName}</div>
              </div>
              {conditions.length > 0 && (
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <CheckCircle className="h-2.5 w-2.5" />
                  {conditions.length} condition{conditions.length !== 1 ? 's' : ''}
                </div>
              )}
            </>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Table not configured
            </div>
          )}
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-cyan-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// API Node
// ============================================================================

export function APINode({ data, selected }: any) {
  const connectionId = data.config.api_connection_id;
  const endpoint = data.config.api_endpoint; // Legacy/fallback
  const apiPath = data.config.api_path;
  const enableSnapshots = data.config.enable_snapshots;

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-violet-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-violet-50 to-purple-50 dark:from-violet-950 dark:to-purple-950",
        "border",
        selected ? "ring-2 ring-violet-500/50 border-violet-500 shadow-lg" : "border-violet-200 dark:border-violet-800 hover:border-violet-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-violet-500 text-white shadow-sm flex-shrink-0">
                <Globe className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">REST API Endpoint</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {(connectionId || endpoint) ? (
            <>
              <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded">
                <div className="font-mono font-semibold truncate">
                  {connectionId ? (
                    apiPath ? `...${apiPath}` : 'Connection configured'
                  ) : endpoint}
                </div>
              </div>
              {enableSnapshots && (
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <CheckCircle className="h-2.5 w-2.5 text-green-500" />
                  Snapshots enabled
                </div>
              )}
            </>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Endpoint not configured
            </div>
          )}
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-violet-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Snapshot Node
// ============================================================================

export function SnapshotNode({ data, selected }: any) {
  const sourceNodeId = data.config.source_node_id;
  const snapshotLabel = data.config.snapshot_label || 'auto';
  const retentionDays = data.config.retention_days || 30;

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-cyan-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-cyan-50 to-sky-50 dark:from-cyan-950 dark:to-sky-950",
        "border",
        selected ? "ring-2 ring-cyan-500/50 border-cyan-500 shadow-lg" : "border-cyan-200 dark:border-cyan-800 hover:border-cyan-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-cyan-500 text-white shadow-sm flex-shrink-0">
                <Database className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Store snapshot</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          {sourceNodeId ? (
            <>
              <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded">
                <span className="text-muted-foreground">Source: </span>
                <span className="font-mono">{sourceNodeId}</span>
              </div>
              <div className="flex gap-1">
                <div className="text-[10px] bg-cyan-100/50 dark:bg-cyan-900/20 text-cyan-700 dark:text-cyan-300 px-1.5 py-0.5 rounded">
                  {snapshotLabel}
                </div>
                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                  <Clock className="h-2.5 w-2.5" />
                  {retentionDays}d
                </div>
              </div>
            </>
          ) : (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-1.5 rounded flex items-center gap-1">
              <XCircle className="h-3 w-3" />
              Source not selected
            </div>
          )}
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-cyan-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Compare Node
// ============================================================================

export function CompareNode({ data, selected }: any) {
  const snapshot1 = data.config.compare_snapshot_1 || 'yesterday';
  const snapshot2 = data.config.compare_snapshot_2 || 'today';
  const strategy = data.config.comparison_strategy || 'fast';
  const threshold = data.config.change_threshold || 0;

  const strategyLabels: Record<string, string> = {
    fast: 'Hash',
    medium: 'Sample',
    full: 'Full'
  };

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-violet-500" style={handleStyle} />

      <Card className={cn(
        "min-w-[220px] transition-all duration-200",
        "bg-gradient-to-br from-violet-50 to-purple-50 dark:from-violet-950 dark:to-purple-950",
        "border",
        selected ? "ring-2 ring-violet-500/50 border-violet-500 shadow-lg" : "border-violet-200 dark:border-violet-800 hover:border-violet-400 shadow"
      )}>
        <CardHeader className="pb-2 pt-2 px-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded bg-violet-500 text-white shadow-sm flex-shrink-0">
                <GitBranch className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-sm font-semibold truncate">{data.label}</CardTitle>
                <p className="text-[10px] text-muted-foreground truncate">Compare snapshots</p>
              </div>
            </div>
            {getStatusBadge(data.status)}
          </div>
        </CardHeader>

        <CardContent className="pt-0 pb-2 px-3 space-y-1">
          <div className="text-[10px] bg-white/50 dark:bg-black/20 p-1.5 rounded space-y-1">
            <div className="flex items-center gap-1">
              <span className="text-muted-foreground">Compare:</span>
              <Badge variant="secondary" className="text-[9px] px-1 py-0 h-3.5">{snapshot1}</Badge>
              <span className="text-muted-foreground">vs</span>
              <Badge variant="secondary" className="text-[9px] px-1 py-0 h-3.5">{snapshot2}</Badge>
            </div>
          </div>
          <div className="flex gap-1">
            <div className="text-[10px] bg-violet-100/50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300 px-1.5 py-0.5 rounded">
              {strategyLabels[strategy]}
            </div>
            {threshold > 0 && (
              <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                Threshold: {threshold}%
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Handle type="source" position={Position.Right} className="!bg-violet-500" style={handleStyle} />
    </>
  );
}

// ============================================================================
// Node Type Map
// ============================================================================

export const nodeTypes = {
  input: InputNode,
  output: OutputNode,
  llm: LLMNode,
  tool: ToolNode,
  conditional: ConditionalNode,
  agent: AgentNode,
  notebook_generator: NotebookGeneratorNode,
  microsite_generator: MicrositeGeneratorNode,
  human_approval: HumanApprovalNode,
  workspace: WorkspaceNode,
  template: TemplateNode,
  delay: DelayNode,
  webhook: WebhookNode,
  api: APINode,
  hana_table: HanaTableNode,
  snapshot: SnapshotNode,
  compare: CompareNode,
};
