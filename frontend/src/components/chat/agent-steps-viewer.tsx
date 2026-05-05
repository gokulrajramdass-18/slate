"use client";

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { CheckCircle2, Loader2, XCircle, Clock, Brain, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AgentStep } from '@/lib/types';

interface AgentStepsViewerProps {
  steps: AgentStep[];
  isStreaming?: boolean;
}

export function AgentStepsViewer({ steps, isStreaming }: AgentStepsViewerProps) {
  // Collapse by default when not streaming (response has arrived)
  // Expand while streaming so user can see progress
  const [isExpanded, setIsExpanded] = useState(isStreaming);

  if (!steps || steps.length === 0) return null;

  const getStepIcon = (step: AgentStep) => {
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
    switch (step.step_type) {
      case 'thinking':
        return 'Analyzing';
      case 'tool_call':
        return step.metadata?.tool_name || 'Tool Execution';
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

  return (
    <Card className="mb-2 p-2.5 bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800">
      {/* Header - Always visible with toggle button */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Brain className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
          <span className="text-xs font-semibold text-blue-900 dark:text-blue-100">
            Agent Execution Steps ({steps.length})
          </span>
          {isStreaming && (
            <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-4 bg-blue-100 dark:bg-blue-900 border-blue-300 dark:border-blue-700">
              <Loader2 className="h-2.5 w-2.5 mr-0.5 animate-spin" />
              Live
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="h-6 w-6 p-0 hover:bg-blue-100 dark:hover:bg-blue-900"
        >
          {isExpanded ? (
            <ChevronUp className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
          )}
        </Button>
      </div>

      {/* Steps - Collapsible content */}
      {isExpanded && (
        <div className="space-y-2">
        {steps.map((step, index) => (
          <div
            key={index}
            className="flex items-start gap-2 text-xs p-2 rounded-md bg-white dark:bg-gray-900 border border-blue-100 dark:border-blue-900 shadow-sm"
          >
            {/* Step number badge */}
            <div className="flex-shrink-0 w-4 h-4 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-[10px] font-semibold text-blue-700 dark:text-blue-300">
              {index + 1}
            </div>

            {/* Status icon */}
            <div className="mt-0.5 flex-shrink-0">{getStepIcon(step)}</div>

            {/* Step content */}
            <div className="flex-1 min-w-0">
              {/* Step header with label, duration, and status */}
              <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                <span className="font-semibold text-gray-900 dark:text-gray-100 text-xs">
                  {getStepLabel(step)}
                </span>
                {step.metadata?.duration_ms && (
                  <Badge variant="outline" className="text-[10px] py-0 px-1 h-4">
                    {step.metadata.duration_ms}ms
                  </Badge>
                )}
                <Badge
                  variant={getStatusBadgeVariant(step.status)}
                  className="text-[10px] py-0 px-1 h-4"
                >
                  {step.status}
                </Badge>
              </div>

              {/* Step description/content */}
              <p className="text-gray-700 dark:text-gray-300 mb-1.5 leading-snug text-xs">
                {step.content}
              </p>

              {/* Result summary (if available) */}
              {step.metadata?.result_summary && (
                <div className="text-xs text-blue-700 dark:text-blue-300 mb-1.5 p-1.5 bg-blue-50 dark:bg-blue-950 rounded border border-blue-200 dark:border-blue-800">
                  <span className="font-semibold">Result:</span> {step.metadata.result_summary}
                </div>
              )}

              {/* Additional metadata */}
              <div className="space-y-0.5">
                {/* Tool name (if not already in label) */}
                {step.metadata?.tool_name && step.step_type !== 'tool_call' && (
                  <div className="text-[10px] text-gray-600 dark:text-gray-400">
                    <span className="font-medium">Tool:</span> {step.metadata.tool_name}
                  </div>
                )}

                {/* Timestamp */}
                {step.timestamp && (
                  <div className="text-[10px] text-gray-500 dark:text-gray-500">
                    <span className="font-medium">Time:</span> {new Date(step.timestamp).toLocaleTimeString()}
                  </div>
                )}

                {/* Start time (if available) */}
                {step.metadata?.started_at && (
                  <div className="text-[10px] text-gray-500 dark:text-gray-500">
                    <span className="font-medium">Started:</span> {new Date(step.metadata.started_at).toLocaleTimeString()}
                  </div>
                )}

                {/* Error message */}
                {step.metadata?.error_message && (
                  <div className="text-[10px] text-red-600 dark:text-red-400 mt-1 p-1.5 bg-red-50 dark:bg-red-950 rounded border border-red-200 dark:border-red-800">
                    <span className="font-semibold">Error:</span> {step.metadata.error_message}
                  </div>
                )}

                {/* Show filtered metadata (hide internal fields) */}
                {step.metadata && Object.keys(step.metadata).length > 0 && (() => {
                  // Filter out internal fields and fields already displayed
                  const filteredMetadata = Object.fromEntries(
                    Object.entries(step.metadata).filter(([key]) =>
                      !['tool_name', 'duration_ms', 'result_type', 'result_summary', 'error_message', 'started_at'].includes(key)
                    )
                  );

                  // Only show details if there's something to show
                  if (Object.keys(filteredMetadata).length === 0) return null;

                  return (
                    <details className="text-[10px] text-gray-600 dark:text-gray-400 mt-1">
                      <summary className="cursor-pointer font-medium hover:text-gray-900 dark:hover:text-gray-200">
                        Additional Details
                      </summary>
                      <pre className="mt-1 p-1.5 bg-gray-100 dark:bg-gray-800 rounded overflow-x-auto text-[10px]">
                        {JSON.stringify(filteredMetadata, null, 2)}
                      </pre>
                    </details>
                  );
                })()}
              </div>
            </div>
          </div>
        ))}
      </div>
      )}
    </Card>
  );
}
