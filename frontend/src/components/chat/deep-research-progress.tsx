"use client";

import { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Brain, Search, Lightbulb, FileText, CheckCircle2, AlertCircle, XCircle } from "lucide-react";
import { ResearchPhase } from "@/lib/api/deep-research";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface DeepResearchProgressProps {
  jobId: string;
  onComplete: (result: any) => void;
  onCancel?: () => void;
}

const PHASE_CONFIG: Record<ResearchPhase, { label: string; icon: any; color: string }> = {
  initializing: { label: 'Initializing research...', icon: Loader2, color: 'text-gray-500' },
  analyzing_query: { label: 'Analyzing your question...', icon: Brain, color: 'text-blue-500' },
  decomposing: { label: 'Breaking down into sub-questions...', icon: Lightbulb, color: 'text-yellow-500' },
  searching: { label: 'Searching across sources...', icon: Search, color: 'text-purple-500' },
  synthesizing: { label: 'Synthesizing findings...', icon: Lightbulb, color: 'text-orange-500' },
  finalizing: { label: 'Generating comprehensive report...', icon: FileText, color: 'text-green-500' },
  complete: { label: 'Research complete!', icon: CheckCircle2, color: 'text-green-600' },
  error: { label: 'Research failed', icon: AlertCircle, color: 'text-red-600' },
};

export function DeepResearchProgress({
  jobId,
  onComplete,
  onCancel,
}: DeepResearchProgressProps) {
  const [phase, setPhase] = useState<ResearchPhase>('initializing');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [startTime] = useState(Date.now());
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    // Update elapsed time every second, but stop if error or complete
    if (phase === 'error' || phase === 'complete') {
      return;
    }

    const timer = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(timer);
  }, [startTime, phase]);

  useEffect(() => {
    // Connect to SSE stream
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5055/api';
    const eventSource = new EventSource(
      `${baseUrl}/chat/deep-research/jobs/${jobId}/stream`
    );

    eventSource.addEventListener('status', (event) => {
      const data = JSON.parse(event.data);
      setPhase(data.phase);
      setProgress(data.progress);
    });

    eventSource.addEventListener('progress', (event) => {
      const data = JSON.parse(event.data);
      setPhase(data.phase);
      setProgress(data.progress);
      setMessage(data.message || '');
    });

    eventSource.addEventListener('complete', (event) => {
      const data = JSON.parse(event.data);
      setPhase('complete');
      setProgress(100);
      onComplete(data);
      eventSource.close();
    });

    eventSource.addEventListener('error', (event) => {
      // Custom error event from server
      const msgEvent = event as MessageEvent;
      if (event.type === 'error' && msgEvent.data) {
        try {
          const data = JSON.parse(msgEvent.data);
          setPhase('error');
          setError(data.error || 'Research failed');
          eventSource.close();
          return;
        } catch (e) {
          // Fall through to connection error
        }
      }

      // Connection/network error
      setPhase('error');
      setError('Connection error - check if backend is running');
      eventSource.close();
    });

    // Also handle native EventSource onerror
    eventSource.onerror = (err) => {
      console.error('[Deep Research] EventSource error:', err);
      setPhase('error');
      setError('Lost connection to server');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [jobId, onComplete]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const PhaseIcon = PHASE_CONFIG[phase]?.icon || Loader2;
  const phaseColor = PHASE_CONFIG[phase]?.color || 'text-gray-500';

  return (
    <Card className="border-purple-200 dark:border-purple-800 shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <PhaseIcon className={`h-5 w-5 ${phaseColor} ${phase !== 'complete' && phase !== 'error' ? 'animate-spin' : ''}`} />
            <span>Deep Research in Progress</span>
          </CardTitle>

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs">
              {formatTime(elapsedTime)}
            </Badge>

            {onCancel && phase !== 'complete' && phase !== 'error' && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onCancel}
                className="h-8"
              >
                <XCircle className="h-4 w-4 mr-1" />
                Cancel
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Phase indicator */}
        <div className="flex items-center gap-2">
          <div className={`flex-shrink-0 ${phaseColor}`}>
            <PhaseIcon className="h-4 w-4" />
          </div>
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {PHASE_CONFIG[phase]?.label || 'Processing...'}
          </span>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400">
            <span>Progress</span>
            <span className="font-semibold">{progress}%</span>
          </div>
          <Progress
            value={progress}
            className="h-2"
          />
        </div>

        {/* Status message */}
        {message && (
          <p className="text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
            {message}
          </p>
        )}

        {/* Error message */}
        {error && (
          <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
            <div className="flex items-center gap-2 text-red-700 dark:text-red-400">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span className="text-sm font-medium">{error}</span>
            </div>
          </div>
        )}

        {/* Info text */}
        {phase !== 'complete' && phase !== 'error' && (
          <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-2">
              <Brain className="h-3 w-3" />
              This may take 2-5 minutes. You can close this window and return later.
            </p>
          </div>
        )}

        {/* Phase checklist */}
        <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
          <div className="space-y-1.5 text-xs">
            {(['analyzing_query', 'decomposing', 'searching', 'synthesizing', 'finalizing'] as ResearchPhase[]).map((p) => {
              const isDone = progress >= getPhaseProgress(p);
              const isCurrent = phase === p;

              return (
                <div
                  key={p}
                  className={`flex items-center gap-2 ${isDone ? 'text-gray-700 dark:text-gray-300' : 'text-gray-400 dark:text-gray-600'}`}
                >
                  {isDone ? (
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                  ) : isCurrent ? (
                    <Loader2 className="h-3 w-3 animate-spin text-purple-500" />
                  ) : (
                    <div className="h-3 w-3 rounded-full border-2 border-gray-300 dark:border-gray-600" />
                  )}
                  <span className={isCurrent ? 'font-medium' : ''}>
                    {PHASE_CONFIG[p].label.replace('...', '')}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Helper to get approximate progress for each phase
function getPhaseProgress(phase: ResearchPhase): number {
  const progressMap: Record<ResearchPhase, number> = {
    initializing: 0,
    analyzing_query: 10,
    decomposing: 25,
    searching: 40,
    synthesizing: 75,
    finalizing: 90,
    complete: 100,
    error: 0,
  };
  return progressMap[phase] || 0;
}
