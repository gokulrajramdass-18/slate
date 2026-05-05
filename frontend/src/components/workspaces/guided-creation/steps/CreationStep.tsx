/**
 * Creation Step
 *
 * Shows workspace creation progress and success.
 */

'use client';

import { useGuidedCreationStore } from '@/lib/stores/guided-creation-store';
import { Progress } from '@/components/ui/progress';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2, CheckCircle, Sparkles, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

export function CreationStep() {
  const { workspaceName, creationProgress, createdWorkspaceId, error } =
    useGuidedCreationStore();

  const isComplete = creationProgress === 100 && createdWorkspaceId;
  const hasFailed = error && creationProgress === 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="p-3 bg-primary/10 rounded-lg">
          {isComplete ? (
            <CheckCircle className="h-6 w-6 text-green-600" />
          ) : hasFailed ? (
            <AlertCircle className="h-6 w-6 text-destructive" />
          ) : (
            <Loader2 className="h-6 w-6 text-primary animate-spin" />
          )}
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold mb-2">
            {isComplete ? 'Workspace Created!' : hasFailed ? 'Creation Failed' : 'Creating Workspace...'}
          </h2>
          <p className="text-muted-foreground">
            {isComplete
              ? `Your workspace "${workspaceName}" is ready. Redirecting you now...`
              : hasFailed
              ? 'There was an issue creating your workspace. Please go back and try again.'
              : 'Please wait while we set up your workspace with all selected resources and agents.'}
          </p>
        </div>
      </div>

      {/* Error Alert */}
      {hasFailed && error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription className="text-sm">
            {error}
            <p className="mt-2 text-xs">
              Click "Previous" to go back and try again, or contact support if the problem persists.
            </p>
          </AlertDescription>
        </Alert>
      )}

      {/* Progress */}
      {!isComplete && !hasFailed && (
        <Card>
          <CardContent className="pt-6 space-y-4">
            <Progress value={creationProgress} className="h-3" />
            <div className="text-center">
              <p className="text-sm text-muted-foreground">
                {creationProgress < 30 && 'Creating workspace structure...'}
                {creationProgress >= 30 &&
                  creationProgress < 60 &&
                  'Linking data sources and tools...'}
                {creationProgress >= 60 &&
                  creationProgress < 90 &&
                  'Initializing agents and tasks...'}
                {creationProgress >= 90 && 'Finalizing setup...'}
              </p>
              <p className="text-2xl font-bold text-primary mt-2">
                {creationProgress}%
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Success */}
      {isComplete && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="p-4 bg-green-100 rounded-full">
                  <Sparkles className="h-8 w-8 text-green-600" />
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-green-900">
                  All Set!
                </h3>
                <p className="text-sm text-green-700 mt-2">
                  Your workspace has been created successfully with:
                </p>
              </div>

              <div className="grid grid-cols-3 gap-4 text-center py-4">
                <div>
                  <p className="text-sm text-green-600 font-medium">
                    Data Sources
                  </p>
                  <p className="text-2xl font-bold text-green-900">✓</p>
                </div>
                <div>
                  <p className="text-sm text-green-600 font-medium">
                    AI Agents
                  </p>
                  <p className="text-2xl font-bold text-green-900">✓</p>
                </div>
                <div>
                  <p className="text-sm text-green-600 font-medium">
                    Task Plan
                  </p>
                  <p className="text-2xl font-bold text-green-900">✓</p>
                </div>
              </div>

              <p className="text-xs text-green-700">
                Redirecting you to your new workspace in a moment...
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* What's Next */}
      {!hasFailed && (
        <Card>
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-3">What happens next?</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span>
                  Your workspace is set up with all selected data sources and tools
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span>
                  AI agents are configured and ready to execute tasks
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span>
                  You can monitor progress, chat with agents, and review results
                </span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span>
                  Tasks will execute automatically or await your approval based on
                  settings
                </span>
              </li>
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
