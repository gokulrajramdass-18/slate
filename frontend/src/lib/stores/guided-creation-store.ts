/**
 * Guided Workspace Creation Store
 *
 * Manages state for the 8-step guided workspace creation wizard:
 * 1. Goal Input
 * 2. Analysis Review
 * 3. Clarification Questions
 * 4. Resource Discovery
 * 5. Plan Generation
 * 6. Collaboration View
 * 7. Confirmation
 * 8. Creation
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

// ============================================================================
// Types
// ============================================================================

export type WizardStep =
  | 'goal'
  | 'analysis'
  | 'clarification'
  | 'sources'          // Step 4: Data sources selection
  | 'tools'            // Step 5: Tools selection
  | 'agents'           // Step 6: Agents OR teams selection (conditional)
  | 'plan'             // Step 7: Plan generation
  | 'confirmation'     // Step 8: Confirmation
  | 'creation';        // Step 9: Creation

export interface GoalAnalysis {
  intent: string;
  domain: string;
  complexity: 'simple' | 'moderate' | 'complex';
  keywords: string[];
  requirements: string[];
}

export interface ClarificationQuestion {
  question: string;
  type: 'multiple_choice' | 'text' | 'date_range';
  options?: string[];
  help_text?: string;
}

export interface DiscoveredResource {
  id: string;
  type: 'source' | 'tool' | 'agent' | 'team';
  name: string;
  description?: string;
  relevance_score: number;
  relevance_reason: string;
  metadata?: Record<string, any>;
}

export interface TaskPlan {
  phase: string;
  tasks: TaskItem[];
}

export interface TaskItem {
  id?: string; // Optional ID for tracking
  name: string;
  description: string;
  assigned_agent_id?: string;
  estimated_duration?: number;
  dependencies: string[];
  required_tools: string[];
  required_sources: string[];
  is_manual?: boolean; // Flag to indicate manual task
}

// ============================================================================
// Store State
// ============================================================================

interface GuidedCreationState {
  // Session
  sessionId: string | null;
  currentStep: WizardStep;
  isLoading: boolean;
  error: string | null;

  // Step 1: Goal
  goal: string;
  selectedDataSources: string[]; // Pre-selected data sources from step 1

  // Step 2: Analysis
  analysis: GoalAnalysis | null;
  needsClarification: boolean;

  // Step 3: Clarification
  clarificationQuestions: ClarificationQuestion[];
  clarificationAnswers: Record<string, any>;

  // Step 4: Resources
  discoveredResources: {
    sources: DiscoveredResource[];
    tools: DiscoveredResource[];
    agents: DiscoveredResource[];
    teams: DiscoveredResource[];
  };
  selectedResources: {
    source_ids: string[];
    tool_ids: string[];
    agent_ids: string[];
    team_ids: string[];
  };

  // Step 5: Plan
  generatedPlan: {
    phases: TaskPlan[];
    agent_assignments: Record<string, string>;
    estimated_total_duration: number;
  } | null;

  // Step 7: Confirmation
  workspaceName: string;
  confirmed: boolean;

  // Step 8: Creation
  createdWorkspaceId: string | null;
  creationProgress: number;

  // Actions
  setSessionId: (sessionId: string) => void;
  setCurrentStep: (step: WizardStep) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Step 1 actions
  setGoal: (goal: string) => void;
  setSelectedDataSources: (sourceIds: string[]) => void;

  // Step 2 actions
  setAnalysis: (analysis: GoalAnalysis, needsClarification: boolean) => void;

  // Step 3 actions
  setClarificationQuestions: (questions: ClarificationQuestion[]) => void;
  setClarificationAnswer: (question: string, answer: any) => void;
  setClarificationAnswers: (answers: Record<string, any>) => void;
  clearClarificationAnswers: () => void;

  // Step 4 actions
  setDiscoveredResources: (resources: {
    sources: DiscoveredResource[];
    tools: DiscoveredResource[];
    agents: DiscoveredResource[];
    teams: DiscoveredResource[];
  }) => void;
  setSelectedResources: (resources: {
    source_ids: string[];
    tool_ids: string[];
    agent_ids: string[];
    team_ids: string[];
  }) => void;
  toggleResourceSelection: (type: 'source' | 'tool' | 'agent' | 'team', id: string) => void;
  clearResourceSelections: () => void;

  // Step 5 actions
  setGeneratedPlan: (plan: {
    phases: TaskPlan[];
    agent_assignments: Record<string, string>;
    estimated_total_duration: number;
  }) => void;
  addManualTask: (phaseIndex: number, task: TaskItem) => void;
  updateManualTask: (phaseIndex: number, taskIndex: number, task: TaskItem) => void;
  deleteManualTask: (phaseIndex: number, taskIndex: number) => void;

  // Step 7 actions
  setWorkspaceName: (name: string) => void;
  setConfirmed: (confirmed: boolean) => void;

  // Step 8 actions
  setCreatedWorkspaceId: (id: string) => void;
  setCreationProgress: (progress: number) => void;

  // Navigation
  goToNextStep: () => void;
  goToPreviousStep: () => void;
  canGoNext: () => boolean;
  canGoPrevious: () => boolean;

  // Reset
  resetWizard: () => void;
}

// ============================================================================
// Initial State
// ============================================================================

const initialState = {
  sessionId: null,
  currentStep: 'goal' as WizardStep,
  isLoading: false,
  error: null,

  goal: '',
  selectedDataSources: [],
  analysis: null,
  needsClarification: false,

  clarificationQuestions: [],
  clarificationAnswers: {},

  discoveredResources: {
    sources: [],
    tools: [],
    agents: [],
    teams: [],
  },
  selectedResources: {
    source_ids: [],
    tool_ids: [],
    agent_ids: [],
    team_ids: [],
  },

  generatedPlan: null,

  workspaceName: '',
  confirmed: false,

  createdWorkspaceId: null,
  creationProgress: 0,
};

// ============================================================================
// Step Order
// ============================================================================

const stepOrder: WizardStep[] = [
  'goal',
  'analysis',
  'clarification',
  'sources',        // Step 4: Data sources
  'tools',          // Step 5: Tools
  'agents',         // Step 6: Agents/Teams
  'plan',           // Step 7: Plan generation
  'confirmation',   // Step 8: Confirmation
  'creation',       // Step 9: Creation
];

// ============================================================================
// Store Implementation
// ============================================================================

export const useGuidedCreationStore = create<GuidedCreationState>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // Session actions
      setSessionId: (sessionId) => set({ sessionId }),
      setCurrentStep: (currentStep) => set({ currentStep }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),

      // Step 1 actions
      setGoal: (goal) => set({ goal }),
      setSelectedDataSources: (selectedDataSources) => set({ selectedDataSources }),

      // Step 2 actions
      setAnalysis: (analysis, needsClarification) =>
        set({ analysis, needsClarification }),

      // Step 3 actions
      setClarificationQuestions: (clarificationQuestions) =>
        set({ clarificationQuestions }),
      setClarificationAnswer: (question, answer) =>
        set((state) => ({
          clarificationAnswers: {
            ...state.clarificationAnswers,
            [question]: answer,
          },
        })),
      setClarificationAnswers: (clarificationAnswers) =>
        set({ clarificationAnswers }),
      clearClarificationAnswers: () => set({ clarificationAnswers: {} }),

      // Step 4 actions
      setDiscoveredResources: (discoveredResources) =>
        set({ discoveredResources }),
      setSelectedResources: (selectedResources) =>
        set({ selectedResources }),
      toggleResourceSelection: (type, id) =>
        set((state) => {
          const key = `${type}_ids` as keyof typeof state.selectedResources;
          const currentIds = state.selectedResources[key];
          const newIds = currentIds.includes(id)
            ? currentIds.filter((existingId) => existingId !== id)
            : [...currentIds, id];

          return {
            selectedResources: {
              ...state.selectedResources,
              [key]: newIds,
            },
          };
        }),
      clearResourceSelections: () =>
        set({
          selectedResources: {
            source_ids: [],
            tool_ids: [],
            agent_ids: [],
            team_ids: [],
          },
        }),

      // Step 5 actions
      setGeneratedPlan: (generatedPlan) => set({ generatedPlan }),
      addManualTask: (phaseIndex, task) => {
        set((state) => {
          if (!state.generatedPlan) return state;

          const newPhases = [...state.generatedPlan.phases];
          if (phaseIndex >= 0 && phaseIndex < newPhases.length) {
            const taskWithId = {
              ...task,
              id: `manual-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              is_manual: true,
            };
            newPhases[phaseIndex].tasks = [
              ...(newPhases[phaseIndex].tasks || []),
              taskWithId,
            ];
          }

          return {
            generatedPlan: {
              ...state.generatedPlan,
              phases: newPhases,
            },
          };
        });
      },
      updateManualTask: (phaseIndex, taskIndex, task) => {
        set((state) => {
          if (!state.generatedPlan) return state;

          const newPhases = [...state.generatedPlan.phases];
          if (
            phaseIndex >= 0 &&
            phaseIndex < newPhases.length &&
            taskIndex >= 0 &&
            taskIndex < (newPhases[phaseIndex].tasks?.length || 0)
          ) {
            const tasks = [...(newPhases[phaseIndex].tasks || [])];
            tasks[taskIndex] = {
              ...task,
              is_manual: true,
            };
            newPhases[phaseIndex].tasks = tasks;
          }

          return {
            generatedPlan: {
              ...state.generatedPlan,
              phases: newPhases,
            },
          };
        });
      },
      deleteManualTask: (phaseIndex, taskIndex) => {
        set((state) => {
          if (!state.generatedPlan) return state;

          const newPhases = [...state.generatedPlan.phases];
          if (
            phaseIndex >= 0 &&
            phaseIndex < newPhases.length &&
            taskIndex >= 0 &&
            taskIndex < (newPhases[phaseIndex].tasks?.length || 0)
          ) {
            const tasks = [...(newPhases[phaseIndex].tasks || [])];
            tasks.splice(taskIndex, 1);
            newPhases[phaseIndex].tasks = tasks;
          }

          return {
            generatedPlan: {
              ...state.generatedPlan,
              phases: newPhases,
            },
          };
        });
      },

      // Step 7 actions
      setWorkspaceName: (workspaceName) => set({ workspaceName }),
      setConfirmed: (confirmed) => set({ confirmed }),

      // Step 8 actions
      setCreatedWorkspaceId: (createdWorkspaceId) => set({ createdWorkspaceId }),
      setCreationProgress: (creationProgress) => set({ creationProgress }),

      // Navigation
      goToNextStep: () => {
        const state = get();
        const currentIndex = stepOrder.indexOf(state.currentStep);
        if (currentIndex < stepOrder.length - 1) {
          let nextStep = stepOrder[currentIndex + 1];

          // Skip clarification step if not needed
          if (nextStep === 'clarification' && !state.needsClarification) {
            nextStep = stepOrder[currentIndex + 2];
          }

          // Skip sources step if data sources were already selected in step 1
          if (nextStep === 'sources' && state.selectedDataSources.length > 0) {
            // Auto-populate selectedResources with the pre-selected sources
            set({
              selectedResources: {
                ...state.selectedResources,
                source_ids: state.selectedDataSources,
              },
            });
            // Skip to next step (tools/agents/plan)
            nextStep = stepOrder[currentIndex + 2];
          }

          set({ currentStep: nextStep });
        }
      },

      goToPreviousStep: () => {
        const state = get();
        const currentIndex = stepOrder.indexOf(state.currentStep);
        if (currentIndex > 0) {
          let prevStep = stepOrder[currentIndex - 1];

          // Skip clarification step if not needed (going backwards)
          if (prevStep === 'clarification' && !state.needsClarification) {
            prevStep = stepOrder[currentIndex - 2];
          }

          // Skip sources step if data sources were already selected in step 1 (going backwards)
          if (prevStep === 'sources' && state.selectedDataSources.length > 0) {
            prevStep = stepOrder[currentIndex - 2];
          }

          set({ currentStep: prevStep });
        }
      },

      canGoNext: () => {
        const state = get();
        switch (state.currentStep) {
          case 'goal':
            return state.goal.trim().length >= 20;
          case 'analysis':
            return state.analysis !== null;
          case 'clarification':
            // Clarification is optional - user can skip or answer
            return true;
          case 'sources':
            // Sources are optional - user can continue without
            return true;
          case 'tools':
            // Tools are optional - user can continue without
            return true;
          case 'agents':
            // Agents are optional - user can continue without
            return true;
          case 'plan':
            return state.generatedPlan !== null;
          case 'confirmation':
            return state.workspaceName.trim().length > 0 && state.confirmed;
          case 'creation':
            return false; // Final step
          default:
            return false;
        }
      },

      canGoPrevious: () => {
        const state = get();
        const currentIndex = stepOrder.indexOf(state.currentStep);
        return currentIndex > 0 && state.currentStep !== 'creation';
      },

      // Reset
      resetWizard: () => set(initialState),
    }),
    { name: 'GuidedCreationStore' }
  )
);
