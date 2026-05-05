/**
 * Guided Workspace Creation Wizard
 *
 * Main container component for the 8-step guided workspace creation flow.
 * Handles step navigation, API calls, state management, and session resumption.
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useGuidedCreationStore } from '@/lib/stores/guided-creation-store';
import {
  analyzeGoal,
  submitClarification,
  discoverResources,
  generatePlan,
  createWorkspace,
  getSession,
} from '@/lib/api/guided-workspace';
import { sourcesApi } from '@/lib/api/sources';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

// Step components (to be created)
import { GoalInputStep } from './steps/GoalInputStep';
import { AnalysisReviewStep } from './steps/AnalysisReviewStep';
import { ClarificationStep } from './steps/ClarificationStep';
import { ResourceDiscoveryStep } from './steps/ResourceDiscoveryStep';
import { PlanGenerationStep } from './steps/PlanGenerationStep';
import { ConfirmationStep } from './steps/ConfirmationStep';
import { CreationStep } from './steps/CreationStep';

// ============================================================================
// Component
// ============================================================================

export function GuidedWorkspaceWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resumeSessionId = searchParams.get('session');

  const {
    currentStep,
    isLoading,
    error,
    sessionId,
    goal,
    selectedDataSources,
    analysis,
    needsClarification,
    clarificationQuestions,
    clarificationAnswers,
    selectedResources,
    generatedPlan,
    workspaceName,
    setSessionId,
    setCurrentStep,
    setLoading,
    setError,
    setGoal,
    setAnalysis,
    setClarificationQuestions,
    setClarificationAnswers,
    setDiscoveredResources,
    setSelectedResources,
    setGeneratedPlan,
    setCreatedWorkspaceId,
    setCreationProgress,
    goToNextStep,
    goToPreviousStep,
    canGoNext,
    canGoPrevious,
    resetWizard,
  } = useGuidedCreationStore();

  const [stepProgress, setStepProgress] = useState(0);
  const [isResuming, setIsResuming] = useState(false);

  // Reset wizard on mount if not resuming a session
  useEffect(() => {
    if (!resumeSessionId) {
      resetWizard();
    }
  }, []);

  // Resume session on mount if session parameter is present
  useEffect(() => {
    if (resumeSessionId && !sessionId) {
      resumeSession(resumeSessionId);
    }
  }, [resumeSessionId]);

  const resumeSession = async (id: string) => {
    try {
      setIsResuming(true);
      console.log('🔄 Resuming session:', id);
      const session = await getSession(id);
      console.log('✅ Session fetched:', session);

      // Restore state from session
      setSessionId(session.id);
      setGoal(session.goal);

      if (session.analysis) {
        setAnalysis(session.analysis, false); // needsClarification = false since we're resuming
      }

      if (session.clarification_answers) {
        setClarificationAnswers(session.clarification_answers);
      }

      if (session.discovered_resources) {
        // Transform backend format to frontend format
        // Backend uses: {data_sources: [], tools: [], agents: [], teams: []}
        // Frontend uses: {sources: [], tools: [], agents: [], teams: []}
        setDiscoveredResources({
          sources: session.discovered_resources.data_sources ||
                   session.discovered_resources.sources || [],
          tools: session.discovered_resources.tools || [],
          agents: session.discovered_resources.agents || [],
          teams: session.discovered_resources.teams || [],
        });
      }

      if (session.selected_resources) {
        // Transform backend format to frontend format
        // Backend uses: {data_sources: [], tools: [], agents: [], teams: []}
        // Frontend uses: {source_ids: [], tool_ids: [], agent_ids: [], team_ids: []}
        setSelectedResources({
          source_ids: session.selected_resources.data_sources?.map((s: any) => s.id || s) ||
                      session.selected_resources.source_ids || [],
          tool_ids: session.selected_resources.tools?.map((t: any) => t.id || t) ||
                    session.selected_resources.tool_ids || [],
          agent_ids: session.selected_resources.agents?.map((a: any) => a.id || a) ||
                     session.selected_resources.agent_ids || [],
          team_ids: session.selected_resources.teams?.map((t: any) => t.id || t) ||
                    session.selected_resources.team_ids || [],
        });
      }

      if (session.plan) {
        setGeneratedPlan(session.plan);
      }

      // Navigate to the current step
      const stepMap: Record<string, string> = {
        goal_analysis: 'goal',
        analysis_review: 'analysis',
        clarification: 'clarification',
        resource_discovery: 'resources',
        plan_generation: 'plan',
        confirmation: 'confirmation',
        workspace_creation: 'creation',
      };
      const wizardStep = stepMap[session.current_step || 'goal_analysis'] || 'goal';
      setCurrentStep(wizardStep as any);

      // Wait for async operations if needed
      let asyncOpsPromise = Promise.resolve();

      // If we're on resource discovery step but resources haven't been discovered yet, trigger discovery
      if (wizardStep === 'resources' && !session.discovered_resources) {
        console.log('🔍 Discovering resources...');
        asyncOpsPromise = asyncOpsPromise.then(async () => {
          try {
            const resourcesResponse = await discoverResources({
              session_id: session.id,
              source_limit: 10,
              tool_limit: 5,
              agent_limit: 5,
              team_limit: 3,
            });

            setDiscoveredResources({
              sources: (resourcesResponse.data_sources || []).map((s: any) => ({
                ...s,
                type: 'source' as const,
                name: s.name || s.title || 'Unnamed Source',
                relevance_reason: s.relevance_reason || '',
              })),
              tools: (resourcesResponse.tools || []).map((t: any) => ({
                ...t,
                type: 'tool' as const,
                relevance_reason: t.relevance_reason || '',
              })),
              agents: (resourcesResponse.agents || []).map((a: any) => ({
                ...a,
                type: 'agent' as const,
                relevance_reason: a.relevance_reason || '',
              })),
              teams: (resourcesResponse.teams || []).map((t: any) => ({
                ...t,
                type: 'team' as const,
                relevance_reason: t.relevance_reason || '',
              })),
            });
            console.log('✅ Resources discovered');
          } catch (err) {
            console.error('❌ Failed to discover resources on resume:', err);
            throw err;
          }
        });
      }

      // If we're on plan generation step but plan hasn't been generated yet, trigger generation
      if (wizardStep === 'plan' && !session.plan) {
        console.log('📋 Generating plan...');
        asyncOpsPromise = asyncOpsPromise.then(async () => {
          try {
            setLoading(true);
            const planResponse = await generatePlan({
              session_id: session.id,
              selected_resources: session.selected_resources || {
                data_sources: [],
                tools: [],
                agents: [],
                teams: [],
              },
            });

            setGeneratedPlan({
              phases: planResponse.phases.map((p: any) => ({
                phase: p.name || p.phase || `Phase ${p.phase_number || 1}`,
                tasks: p.tasks.map((t: any) => ({
                  name: t.name,
                  description: t.description || '',
                  assigned_agent_id: t.assigned_agent_id,
                  estimated_duration: t.estimated_duration || t.estimated_minutes || 30,
                  dependencies: t.dependencies || [],
                  required_tools: t.required_tools || [],
                  required_sources: t.required_sources || [],
                })),
              })),
              agent_assignments: planResponse.agent_assignments || {},
              estimated_total_duration: planResponse.total_duration,
            });
            console.log('✅ Plan generated');
          } catch (err) {
            console.error('❌ Failed to generate plan on resume:', err);
            setError('Failed to generate plan. Please try again.');
            throw err;
          } finally {
            setLoading(false);
          }
        });
      }

      // Wait for all async operations to complete before hiding loading screen
      await asyncOpsPromise;

      toast.success('Draft workspace resumed');
      console.log('✅ Resume complete');
    } catch (error) {
      console.error('❌ Failed to resume session:', error);
      toast.error('Failed to resume draft workspace');
      // Start fresh if resume fails
      resetWizard();
    } finally {
      setIsResuming(false);
    }
  };

  // Calculate if user provided any clarification answers
  const hasAnswers = Object.keys(clarificationAnswers).length > 0;
  const hasRealAnswers = Object.entries(clarificationAnswers).some(
    ([_, value]) => value !== '[SKIPPED]' && value !== ''
  );

  // Calculate progress percentage
  useEffect(() => {
    const steps = [
      'goal',
      'analysis',
      'clarification',
      'sources',
      'tools',
      'agents',
      'plan',
      'confirmation',
      'creation',
    ];
    const currentIndex = steps.indexOf(currentStep);
    const progress = Math.round(((currentIndex + 1) / steps.length) * 100);
    setStepProgress(progress);
  }, [currentStep]);

  // ============================================================================
  // Step Handlers
  // ============================================================================

  const handleAnalyzeGoal = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await analyzeGoal({ goal });

      setSessionId(response.session_id);
      setAnalysis(response.analysis, response.needs_clarification);

      if (response.needs_clarification && response.questions) {
        setClarificationQuestions(response.questions);
      }

      goToNextStep();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to analyze goal');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitClarification = async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      setError(null);

      // Filter out skipped questions before sending
      const realAnswers = Object.fromEntries(
        Object.entries(clarificationAnswers).filter(
          ([_, value]) => value !== '[SKIPPED]' && value !== ''
        )
      );

      // Only call API if there are real answers
      if (Object.keys(realAnswers).length > 0) {
        const response = await submitClarification({
          session_id: sessionId,
          answers: realAnswers,
        });

        setAnalysis(response.refined_analysis, false);
      }

      goToNextStep();
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 'Failed to submit clarification answers'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSkipClarification = () => {
    // Skip clarification and go directly to resource discovery
    goToNextStep();
  };

  const handleDiscoverResources = async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      setError(null);

      const response = await discoverResources({
        session_id: sessionId,
        source_limit: 10,
        tool_limit: 5,
        agent_limit: 5,
        team_limit: 3,
      });

      // Map discovered resources
      const discoveredSources = (response.data_sources || []).map((s: any) => ({
        ...s,
        type: 'source' as const,
        name: s.name || s.title || 'Unnamed Source',
        relevance_reason: s.relevance_reason || '',
      }));

      // Add pre-selected data sources from step 1 if not already discovered
      const preSelectedSourceIds = new Set(selectedDataSources);
      const discoveredSourceIds = new Set(discoveredSources.map((s: any) => s.id));

      // Fetch full details of pre-selected sources that weren't discovered
      const additionalSources: any[] = [];
      for (const sourceId of Array.from(preSelectedSourceIds)) {
        if (!discoveredSourceIds.has(sourceId)) {
          try {
            const source = await sourcesApi.get(sourceId);
            additionalSources.push({
              id: source.id,
              type: 'source' as const,
              name: source.title,
              description: source.full_text?.slice(0, 200) || '',
              relevance_score: 1.0, // Max relevance since manually selected
              relevance_reason: 'Manually selected in step 1',
              metadata: { source_type: source.source_type },
            });
          } catch (err) {
            console.error(`Failed to fetch source ${sourceId}:`, err);
          }
        }
      }

      // Combine discovered and pre-selected sources
      const allSources = [...discoveredSources, ...additionalSources];

      setDiscoveredResources({
        sources: allSources,
        tools: (response.tools || []).map((t: any) => ({
          ...t,
          type: 'tool' as const,
          relevance_reason: t.relevance_reason || '',
        })),
        agents: (response.agents || []).map((a: any) => ({
          ...a,
          type: 'agent' as const,
          relevance_reason: a.relevance_reason || '',
        })),
        teams: (response.teams || []).map((t: any) => ({
          ...t,
          type: 'team' as const,
          relevance_reason: t.relevance_reason || '',
        })),
      });

      // Auto-select pre-selected sources
      if (selectedDataSources.length > 0) {
        setSelectedResources({
          ...selectedResources,
          source_ids: selectedDataSources,
        });
      }

      goToNextStep();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to discover resources');
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePlan = async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      setError(null);

      const response = await generatePlan({
        session_id: sessionId,
        selected_resources: selectedResources,
      });

      // Response has phases, total_duration, collaboration_graph at top level
      setGeneratedPlan({
        phases: (response.phases || []).map((p: any) => ({
          phase: p.name || p.phase || `Phase ${p.phase_number || 1}`,
          tasks: p.tasks.map((t: any) => ({
            name: t.name,
            description: t.description || '',
            assigned_agent_id: t.assigned_agent_id,
            estimated_duration: t.estimated_duration || t.estimated_minutes || 30,
            dependencies: t.dependencies || [],
            required_tools: t.required_tools || [],
            required_sources: t.required_sources || [],
          })),
        })),
        agent_assignments: response.agent_assignments || {},
        estimated_total_duration: response.total_duration || 0,
      });

      goToNextStep();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate plan');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWorkspace = async () => {
    if (!sessionId) {
      console.error('No sessionId available for workspace creation');
      setError('Session ID is missing. Please restart the wizard.');
      return;
    }

    if (!workspaceName.trim()) {
      setError('Workspace name is required');
      return;
    }

    if (!generatedPlan) {
      setError('Plan is missing. Please go back and generate a plan.');
      return;
    }

    console.log('Starting workspace creation...', { sessionId, workspaceName });

    let progressInterval: NodeJS.Timeout | null = null;
    let timeoutId: NodeJS.Timeout | null = null;

    try {
      // Move to creation step immediately to show progress
      goToNextStep();

      setLoading(true);
      setError(null);
      setCreationProgress(0);

      // More realistic progress simulation
      let currentProgress = 0;
      progressInterval = setInterval(() => {
        currentProgress += Math.random() * 15; // Random increments
        if (currentProgress > 85) currentProgress = 85; // Cap at 85% until API returns
        setCreationProgress(Math.floor(currentProgress));
      }, 800);

      // Set a timeout for the API call (60 seconds)
      const timeoutPromise = new Promise((_, reject) => {
        timeoutId = setTimeout(() => {
          reject(new Error('Workspace creation timed out. Please try again.'));
        }, 60000);
      });

      console.log('Calling createWorkspace API...');
      const apiPromise = createWorkspace({
        session_id: sessionId,
        name: workspaceName,
        goal: goal,
        selected_resources: {
          data_sources: selectedResources.source_ids.map((id) => ({ id })),
          tools: selectedResources.tool_ids.map((id) => ({ id })),
          agents: selectedResources.agent_ids.map((id) => ({ id })),
          teams: selectedResources.team_ids.map((id) => ({ id })),
        },
        plan: {
          phases: generatedPlan.phases,
          agent_assignments: generatedPlan.agent_assignments,
          estimated_total_duration: generatedPlan.estimated_total_duration,
        },
        auto_start: false,
      });

      // Race between API call and timeout
      const response = await Promise.race([apiPromise, timeoutPromise]) as any;

      console.log('Workspace created successfully:', response);

      if (progressInterval) clearInterval(progressInterval);
      if (timeoutId) clearTimeout(timeoutId);

      // Quickly jump to 100%
      setCreationProgress(95);
      await new Promise(resolve => setTimeout(resolve, 200));
      setCreationProgress(100);
      setCreatedWorkspaceId(response.workspace_id);

      toast.success('Workspace created successfully!');

      // After 2 seconds, redirect to the new workspace
      setTimeout(() => {
        router.push(`/workspaces/${response.workspace_id}`);
      }, 2000);
    } catch (err: any) {
      console.error('Failed to create workspace:', err);

      // Clean up intervals and timeouts
      if (progressInterval) clearInterval(progressInterval);
      if (timeoutId) clearTimeout(timeoutId);

      const errorMessage = err.message ||
                          err.response?.data?.detail ||
                          'Failed to create workspace. Please try again.';

      setError(errorMessage);
      toast.error(errorMessage);

      // Reset progress
      setCreationProgress(0);

      // Go back to confirmation step on error
      goToPreviousStep();
    } finally {
      setLoading(false);
    }
  };

  // ============================================================================
  // Navigation Handlers
  // ============================================================================

  const handleNext = async () => {
    console.log('handleNext called, currentStep:', currentStep);
    // Trigger API calls at specific steps
    switch (currentStep) {
      case 'goal':
        await handleAnalyzeGoal();
        break;
      case 'analysis':
        // Discover resources when leaving analysis step
        await handleDiscoverResources();
        break;
      case 'clarification':
        await handleSubmitClarification();
        break;
      case 'sources':
        // Just navigate to tools step
        goToNextStep();
        break;
      case 'tools':
        // Just navigate to agents step
        goToNextStep();
        break;
      case 'agents':
        // Generate plan when leaving agents step
        await handleGeneratePlan();
        break;
      case 'plan':
        // Navigate to confirmation
        goToNextStep();
        break;
      case 'confirmation':
        console.log('Confirmation step - calling handleCreateWorkspace');
        await handleCreateWorkspace();
        break;
      default:
        goToNextStep();
    }
  };

  const handlePrevious = () => {
    goToPreviousStep();
  };

  const handleCancel = () => {
    if (confirm('Are you sure you want to cancel? All progress will be lost.')) {
      resetWizard();
      router.push('/workspaces');
    }
  };

  // ============================================================================
  // Render Step Content
  // ============================================================================

  const renderStepContent = () => {
    switch (currentStep) {
      case 'goal':
        return <GoalInputStep />;
      case 'analysis':
        return <AnalysisReviewStep />;
      case 'clarification':
        return <ClarificationStep />;
      case 'sources':
        return <ResourceDiscoveryStep resourceType="sources" />;
      case 'tools':
        return <ResourceDiscoveryStep resourceType="tools" />;
      case 'agents':
        return <ResourceDiscoveryStep resourceType="agents" />;
      case 'plan':
        return <PlanGenerationStep />;
      case 'confirmation':
        return <ConfirmationStep />;
      case 'creation':
        return <CreationStep />;
      default:
        return null;
    }
  };

  // ============================================================================
  // Render
  // ============================================================================

  // Show loading state while resuming session
  if (isResuming) {
    return (
      <div className="container mx-auto py-8 max-w-5xl">
        <Card className="p-12">
          <div className="flex flex-col items-center justify-center space-y-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-lg font-medium">Resuming your workspace session...</p>
            <p className="text-sm text-muted-foreground">Loading your saved progress</p>
            <p className="text-xs text-muted-foreground mt-2">
              This may take a few moments as we restore your configuration
            </p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="h-full p-3 md:p-4">
      <div className="w-full mx-auto h-full flex flex-col">
        {/* Minimal Header */}
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-sm font-medium text-muted-foreground">Workspace Setup</h1>
          <div className="text-xs text-muted-foreground">{stepProgress}%</div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="mb-3">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="text-sm">{error}</AlertDescription>
          </Alert>
        )}

        {/* Step Content - Maximum space */}
        <Card className="flex-1 p-6 md:p-8 mb-3 overflow-auto">
          {renderStepContent()}
        </Card>

        {/* Navigation Buttons */}
        <div className="flex justify-between items-center pt-3 border-t">
          <Button
            variant="outline"
            size="lg"
            onClick={handleCancel}
            disabled={isLoading || currentStep === 'creation'}
          >
            Cancel
          </Button>

          <div className="flex gap-4">
            <Button
              variant="outline"
              size="lg"
              onClick={handlePrevious}
              disabled={!canGoPrevious() || isLoading}
            >
              <ChevronLeft className="h-4 w-4 mr-2" />
              Previous
            </Button>

            <Button
              size="lg"
              onClick={handleNext}
              disabled={!canGoNext() || isLoading || currentStep === 'creation'}
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : currentStep === 'confirmation' ? (
                'Create Workspace'
              ) : currentStep === 'clarification' ? (
                hasRealAnswers ? (
                  <>
                    Continue with Answers
                    <ChevronRight className="h-4 w-4 ml-2" />
                  </>
                ) : (
                  <>
                    Skip Clarification
                    <ChevronRight className="h-4 w-4 ml-2" />
                  </>
                )
              ) : (
                <>
                  Next
                  <ChevronRight className="h-4 w-4 ml-2" />
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
