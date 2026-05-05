"use client";

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import {
  CheckCircle2,
  Loader2,
  XCircle,
  Clock,
  Brain,
  ChevronDown,
  ChevronUp,
  Wrench,
  Lightbulb,
  ListChecks,
  MessageSquare,
  Eye
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AgentStep } from '@/lib/types';

interface AgentStepsViewerProps {
  steps: AgentStep[];
  isStreaming?: boolean;
}

export function AgentStepsViewer({ steps, isStreaming }: AgentStepsViewerProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  if (!steps || steps.length === 0) return null;

  const toggleStepExpansion = (index: number) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const getStepIcon = (step: AgentStep) => {
    // LangGraph-specific step types
    if (step.step_type === 'analysis') {
      return <Eye className="h-4 w-4 text-purple-500" />;
    }
    if (step.step_type === 'planning') {
      return <ListChecks className="h-4 w-4 text-indigo-500" />;
    }
    if (step.step_type === 'step_start') {
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    }
    if (step.step_type === 'step_complete') {
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    }
    if (step.step_type === 'llm_call') {
      return <MessageSquare className="h-4 w-4 text-orange-500" />;
    }
    if (step.step_type === 'llm_response') {
      return <Lightbulb className="h-4 w-4 text-yellow-500" />;
    }

    // Status-based icons
    switch (step.status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'running':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-gray-400" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStepLabel = (step: AgentStep) => {
    // LangGraph step types
    if (step.step_type === 'analysis') {
      return 'Analyzing Query';
    }
    if (step.step_type === 'planning') {
      return 'Creating Execution Plan';
    }
    if (step.step_type === 'step_start') {
      return step.metadata?.step || 'Step Started';
    }
    if (step.step_type === 'step_complete') {
      return step.metadata?.step || 'Step Completed';
    }
    if (step.step_type === 'llm_call') {
      return 'AI Thinking';
    }
    if (step.step_type === 'llm_response') {
      return 'AI Response';
    }

    // Original step types
    switch (step.step_type) {
      case 'thinking':
        return 'Analyzing';
      case 'tool_call':
        return `Tool: ${step.metadata?.tool_name || step.metadata?.tool || 'Unknown'}`;
      case 'tool_result':
        return 'Tool Result';
      case 'response':
        return 'Generating Response';
      default:
        return 'Processing';
    }
  };

  const getStatusBadgeVariant = (status: AgentStep['status']) => {
    switch (status) {
      case 'completed':
        return 'default';
      case 'error':
        return 'destructive';
      case 'running':
        return 'secondary';
      case 'pending':
        return 'outline';
      default:
        return 'outline';
    }
  };

  const renderToolCallDetails = (step: AgentStep) => {
    if (step.step_type !== 'tool_call' && !step.metadata?.tool) return null;

    const toolName = step.metadata?.tool_name || step.metadata?.tool;
    const args = step.metadata?.args;

    return (
      <div className="mt-2 p-3 bg-blue-50 dark:bg-blue-950 rounded border border-blue-200 dark:border-blue-800">
        <div className="flex items-center gap-2 mb-2">
          <Wrench className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <span className="font-semibold text-sm text-blue-900 dark:text-blue-100">
            Tool: {toolName}
          </span>
        </div>
        {args && (
          <details className="text-xs">
            <summary className="cursor-pointer font-medium text-blue-700 dark:text-blue-300 hover:text-blue-900 dark:hover:text-blue-100">
              Arguments
            </summary>
            <pre className="mt-1 p-2 bg-white dark:bg-gray-900 rounded overflow-x-auto text-xs">
              {JSON.stringify(args, null, 2)}
            </pre>
          </details>
        )}
      </div>
    );
  };

  const renderPlanDetails = (step: AgentStep) => {
    if (step.step_type !== 'planning' || !step.metadata?.plan) return null;

    const plan = step.metadata.plan;

    return (
      <div className="mt-2 p-3 bg-indigo-50 dark:bg-indigo-950 rounded border border-indigo-200 dark:border-indigo-800">
        <div className="flex items-center gap-2 mb-2">
          <ListChecks className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
          <span className="font-semibold text-sm text-indigo-900 dark:text-indigo-100">
            Execution Plan ({plan.length} steps)
          </span>
        </div>
        <ol className="list-decimal list-inside space-y-1 text-xs text-indigo-800 dark:text-indigo-200">
          {plan.map((planStep: any, idx: number) => (
            <li key={idx}>
              <span className="font-medium">{planStep.step_name || `Step ${idx + 1}`}</span>
              {planStep.tool_name && (
                <span className="text-indigo-600 dark:text-indigo-400 ml-1">
                  using {planStep.tool_name}
                </span>
              )}
            </li>
          ))}
        </ol>
      </div>
    );
  };

  const renderAnalysisDetails = (step: AgentStep) => {
    if (step.step_type !== 'analysis' || !step.metadata?.analysis) return null;

    const analysis = step.metadata.analysis;

    return (
      <div className="mt-2 p-3 bg-purple-50 dark:bg-purple-950 rounded border border-purple-200 dark:border-purple-800">
        <div className="flex items-center gap-2 mb-2">
          <Eye className="h-4 w-4 text-purple-600 dark:text-purple-400" />
          <span className="font-semibold text-sm text-purple-900 dark:text-purple-100">
            Query Analysis
          </span>
        </div>
        <div className="space-y-1 text-xs">
          {analysis.complexity && (
            <div>
              <span className="font-medium text-purple-700 dark:text-purple-300">Complexity:</span>{' '}
              <Badge variant="outline" className="ml-1 text-xs">
                {analysis.complexity}
              </Badge>
            </div>
          )}
          {analysis.estimated_steps && (
            <div>
              <span className="font-medium text-purple-700 dark:text-purple-300">Estimated Steps:</span>{' '}
              <span className="text-purple-900 dark:text-purple-100">{analysis.estimated_steps}</span>
            </div>
          )}
          {analysis.required_tools && analysis.required_tools.length > 0 && (
            <div>
              <span className="font-medium text-purple-700 dark:text-purple-300">Required Tools:</span>{' '}
              <span className="text-purple-900 dark:text-purple-100">
                {analysis.required_tools.join(', ')}
              </span>
            </div>
          )}
          {analysis.approach && (
            <div className="mt-2 pt-2 border-t border-purple-200 dark:border-purple-800">
              <span className="font-medium text-purple-700 dark:text-purple-300">Approach:</span>
              <p className="mt-1 text-purple-900 dark:text-purple-100">{analysis.approach}</p>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderLLMPrompt = (step: AgentStep) => {
    if (step.step_type !== 'llm_call' || !step.metadata?.prompt) return null;

    return (
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer font-medium text-orange-700 dark:text-orange-300 hover:text-orange-900 dark:hover:text-orange-100">
          View Prompt
        </summary>
        <pre className="mt-1 p-2 bg-orange-50 dark:bg-orange-950 rounded overflow-x-auto text-xs whitespace-pre-wrap">
          {step.metadata.prompt}
        </pre>
      </details>
    );
  };

  const renderStepOutput = (step: AgentStep) => {
    const output = step.metadata?.output;
    if (!output) return null;

    const outputStr = typeof output === 'string' ? output : JSON.stringify(output, null, 2);
    if (outputStr.length < 200) {
      return (
        <div className="mt-2 p-2 bg-gray-50 dark:bg-gray-900 rounded text-xs">
          <span className="font-medium text-gray-700 dark:text-gray-300">Output:</span>
          <pre className="mt-1 whitespace-pre-wrap text-gray-900 dark:text-gray-100">{outputStr}</pre>
        </div>
      );
    }

    return (
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100">
          View Output ({outputStr.length} chars)
        </summary>
        <pre className="mt-1 p-2 bg-gray-50 dark:bg-gray-900 rounded overflow-x-auto text-xs whitespace-pre-wrap">
          {outputStr}
        </pre>
      </details>
    );
  };

  return (
    <Card className="mb-3 p-4 bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800">
      {/* Header - Always visible with toggle button */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-blue-200 dark:border-blue-800">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          <span className="text-sm font-semibold text-blue-900 dark:text-blue-100">
            Agent Execution Steps ({steps.length})
          </span>
          {isStreaming && (
            <Badge variant="outline" className="text-xs bg-blue-100 dark:bg-blue-900 border-blue-300 dark:border-blue-700">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Live
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="h-8 w-8 p-0 hover:bg-blue-100 dark:hover:bg-blue-900"
        >
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          )}
        </Button>
      </div>

      {/* Steps - Collapsible content */}
      {isExpanded && (
        <div className="space-y-3">
        {steps.map((step, index) => {
          const isExpanded = expandedSteps.has(index);
          const hasDetails = step.metadata?.plan || step.metadata?.analysis ||
                           step.metadata?.args || step.metadata?.output ||
                           step.metadata?.prompt;

          return (
            <div
              key={index}
              className="flex items-start gap-3 text-sm p-3 rounded-lg bg-white dark:bg-gray-900 border border-blue-100 dark:border-blue-900 shadow-sm"
            >
              {/* Step number badge */}
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-xs font-semibold text-blue-700 dark:text-blue-300">
                {step.metadata?.step_number || index + 1}
              </div>

              {/* Status icon */}
              <div className="mt-0.5 flex-shrink-0">{getStepIcon(step)}</div>

              {/* Step content */}
              <div className="flex-1 min-w-0">
                {/* Step header with label, duration, and status */}
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="font-semibold text-gray-900 dark:text-gray-100">
                    {getStepLabel(step)}
                  </span>
                  {step.metadata?.duration_ms && (
                    <Badge variant="outline" className="text-xs">
                      {step.metadata.duration_ms}ms
                    </Badge>
                  )}
                  <Badge
                    variant={getStatusBadgeVariant(step.status)}
                    className="text-xs"
                  >
                    {step.status}
                  </Badge>
                </div>

                {/* Step description/content */}
                {step.content && (
                  <p className="text-gray-700 dark:text-gray-300 mb-2 leading-relaxed">
                    {step.content}
                  </p>
                )}

                {/* LangGraph-specific details */}
                {renderAnalysisDetails(step)}
                {renderPlanDetails(step)}
                {renderToolCallDetails(step)}
                {renderLLMPrompt(step)}
                {renderStepOutput(step)}

                {/* Error message */}
                {step.metadata?.error_message && (
                  <div className="text-xs text-red-600 dark:text-red-400 mt-2 p-2 bg-red-50 dark:bg-red-950 rounded border border-red-200 dark:border-red-800">
                    <span className="font-semibold">Error:</span> {step.metadata.error_message}
                  </div>
                )}

                {/* Timestamp */}
                {step.timestamp && (
                  <div className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                    {new Date(step.timestamp).toLocaleTimeString()}
                  </div>
                )}

                {/* Show all other metadata if available */}
                {hasDetails && Object.keys(step.metadata || {}).length > 5 && (
                  <details className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                    <summary className="cursor-pointer font-medium hover:text-gray-900 dark:hover:text-gray-200">
                      Additional Details
                    </summary>
                    <pre className="mt-1 p-2 bg-gray-100 dark:bg-gray-800 rounded overflow-x-auto text-xs">
                      {JSON.stringify(step.metadata, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          );
        })}
      </div>
      )}
    </Card>
  );
}
