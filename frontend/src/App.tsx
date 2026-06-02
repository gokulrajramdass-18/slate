import { lazy, Suspense, useEffect } from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import { AuthGuard } from "@/components/auth";
import { AppShell } from "@/components/layout/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAuthStore } from "@/lib/stores/auth-store";

// Public pages
const LandingPage = lazy(() => import("@/pages/LandingPage"));
const LoginPage = lazy(() => import("@/pages/auth/LoginPage"));
const AuthCallbackPage = lazy(() => import("@/pages/auth/AuthCallbackPage"));
const PublicSitePage = lazy(() => import("@/pages/public/PublicMicrositeViewPage"));
const PresentationsNewPage = lazy(() => import("@/pages/presentations/PresentationNewPage"));

// Dashboard
const DashboardPage = lazy(() => import("@/pages/dashboard/DashboardPage"));

// Agents
const AgentsPage = lazy(() => import("@/pages/agents/AgentsPage"));
const AgentStandaloneExecutePage = lazy(
  () => import("@/pages/agents/StandaloneAgentExecutePage")
);
const AgentTeamExecutePage = lazy(
  () => import("@/pages/agents/TeamAgentExecutePage")
);
const AgentMemoryInspectorPage = lazy(
  () => import("@/pages/agents/AgentMemoryInspectorPage")
);

// Evaluations
const EvaluationsPage = lazy(() => import("@/pages/evaluations/EvaluationsPage"));

// Approvals
const ApprovalsPage = lazy(() => import("@/pages/ApprovalsPage"));

// Bookmarks
const BookmarksPage = lazy(() => import("@/pages/BookmarksPage"));

// Chat
const ChatIndexPage = lazy(() => import("@/pages/chat/ChatListPage"));
const ChatDetailPage = lazy(() => import("@/pages/chat/ChatDetailPage"));

// Communities
const CommunitiesPage = lazy(() => import("@/pages/CommunitiesPage"));

// Entities
const EntitiesPage = lazy(() => import("@/pages/EntitiesPage"));

// Graph
const GraphPage = lazy(() => import("@/pages/GraphPage"));

// Microsites
const MicrositesPage = lazy(() => import("@/pages/microsites/MicrositesPage"));
const MicrositeDetailPage = lazy(
  () => import("@/pages/microsites/MicrositeViewPage")
);
const MicrositeEditPage = lazy(
  () => import("@/pages/microsites/MicrositeEditPage")
);

// Orchestration
const OrchestrationPage = lazy(
  () => import("@/pages/OrchestrationPage")
);

// Search
const SearchPage = lazy(() => import("@/pages/SearchPage"));

// Snapshots
const SnapshotsPage = lazy(() => import("@/pages/SnapshotsPage"));

// Sources
const SourcesPage = lazy(() => import("@/pages/sources/SourcesPage"));
const SourceNewPage = lazy(() => import("@/pages/sources/SourceCreatePage"));
const SourceDetailPage = lazy(
  () => import("@/pages/sources/SourceDetailPage")
);

// Templates
const TemplatesPage = lazy(() => import("@/pages/templates/TemplatesPage"));
const TemplateDetailPage = lazy(
  () => import("@/pages/templates/TemplateDetailPage")
);

// Test page
const TestPage = lazy(() => import("@/pages/TestPage"));

// Workflow templates
const WorkflowTemplatesPage = lazy(
  () => import("@/pages/WorkflowTemplatesPage")
);

// Workflows
const WorkflowsPage = lazy(() => import("@/pages/workflows/WorkflowsPage"));
const WorkflowDetailPage = lazy(
  () => import("@/pages/workflows/WorkflowDetailPage")
);
const WorkflowSettingsPage = lazy(
  () => import("@/pages/workflows/WorkflowSettingsPage")
);
const WorkflowSchedulesPage = lazy(
  () => import("@/pages/workflows/WorkflowSchedulesPage")
);
const WorkflowExecutionsPage = lazy(
  () => import("@/pages/workflows/WorkflowExecutionsPage")
);
const WorkflowExecutionDetailPage = lazy(
  () => import("@/pages/workflows/WorkflowExecutionDetailPage")
);
const WorkflowEvaluationsPage = lazy(
  () => import("@/pages/workflows/WorkflowEvaluationsPage")
);

// Workspaces
const WorkspacesPage = lazy(() => import("@/pages/workspaces/WorkspacesPage"));
const WorkspaceCreateGuidedPage = lazy(
  () => import("@/pages/workspaces/GuidedWorkspaceCreatePage")
);
const WorkspaceDetailPage = lazy(
  () => import("@/pages/workspaces/WorkspaceDetailPage")
);
const WorkspaceGraphPage = lazy(
  () => import("@/pages/workspaces/WorkspaceGraphPage")
);

// Settings
const SettingsIndexPage = lazy(
  () => import("@/pages/settings/SettingsHomePage")
);
const SettingsActionsPage = lazy(
  () => import("@/pages/settings/SettingsActionsPage")
);
const SettingsAgentsPage = lazy(
  () => import("@/pages/settings/SettingsAgentsPage")
);
const SettingsAgentTeamExecutePage = lazy(
  () => import("@/pages/settings/SettingsTeamExecutePage")
);
const SettingsApiConnectionsPage = lazy(
  () => import("@/pages/settings/SettingsApiConnectionsPage")
);
const SettingsApiKeysPage = lazy(
  () => import("@/pages/settings/SettingsApiKeysPage")
);
const SettingsChatPage = lazy(
  () => import("@/pages/settings/SettingsChatPage")
);
const SettingsDailyBriefPage = lazy(
  () => import("@/pages/settings/SettingsDailyBriefPage")
);
const SettingsDatabasePage = lazy(
  () => import("@/pages/settings/SettingsDatabasePage")
);
const SettingsFoldersPage = lazy(
  () => import("@/pages/settings/SettingsFoldersPage")
);
const SettingsGraphPage = lazy(
  () => import("@/pages/settings/SettingsGraphPage")
);
const SettingsHanaConnectionsPage = lazy(
  () => import("@/pages/settings/SettingsHanaConnectionsPage")
);
const SettingsMcpServersPage = lazy(
  () => import("@/pages/settings/SettingsMcpServersPage")
);
const SettingsModelsPage = lazy(
  () => import("@/pages/settings/SettingsModelsPage")
);
const SettingsOauthAppsPage = lazy(
  () => import("@/pages/settings/SettingsOAuthAppsPage")
);
const SettingsObservabilityPage = lazy(
  () => import("@/pages/settings/SettingsObservabilityPage")
);
const SettingsPromptsPage = lazy(
  () => import("@/pages/settings/SettingsPromptsPage")
);
const SettingsRolesPage = lazy(
  () => import("@/pages/settings/SettingsRolesPage")
);
const SettingsLookupsPage = lazy(
  () => import("@/pages/settings/SettingsLookupsPage")
);
const SettingsSkillsPage = lazy(
  () => import("@/pages/settings/SettingsSkillsPage")
);
const SettingsSmtpPage = lazy(
  () => import("@/pages/settings/SettingsSmtpPage")
);
const SettingsToolsPage = lazy(
  () => import("@/pages/settings/SettingsToolsPage")
);
const SettingsUsersPage = lazy(
  () => import("@/pages/settings/SettingsUsersPage")
);

function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto" />
        <p className="mt-4 text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}

function PublicLayout() {
  // In XSUAA mode: AppRouter already authenticated, no auth checks needed
  // In local mode: no auth required for public routes
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Outlet />
    </Suspense>
  );
}

function ProtectedLayout() {
  // Check if XSUAA mode at runtime
  const isXsuaaMode = typeof window !== "undefined" &&
    (window.location.port === "5001" || window.location.port === "5000" || import.meta.env.VITE_XSUAA_ENABLED === "true");

  // In XSUAA mode: AppRouter already authenticated, skip AuthGuard entirely
  if (isXsuaaMode) {
    return (
      <TooltipProvider>
        <AppShell>
          <Suspense fallback={<LoadingSpinner />}>
            <Outlet />
          </Suspense>
        </AppShell>
      </TooltipProvider>
    );
  }

  // In local mode: use AuthGuard
  return (
    <AuthGuard requireAuth={true}>
      <TooltipProvider>
        <AppShell>
          <Suspense fallback={<LoadingSpinner />}>
            <Outlet />
          </Suspense>
        </AppShell>
      </TooltipProvider>
    </AuthGuard>
  );
}

function SettingsLayout() {
  return (
    <div className="p-6 h-full overflow-auto">
      <Outlet />
    </div>
  );
}

function OpenLayout() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Outlet />
    </Suspense>
  );
}

export default function App() {
  // Check if XSUAA mode at runtime
  const isXsuaaMode = typeof window !== "undefined" &&
    (window.location.port === "5001" || window.location.port === "5000" || import.meta.env.VITE_XSUAA_ENABLED === "true");

  const checkXsuaaSession = useAuthStore((state) => state.checkXsuaaSession);

  // In XSUAA mode, check session on mount
  useEffect(() => {
    if (isXsuaaMode) {
      console.log("[App] XSUAA mode detected - checking session");
      checkXsuaaSession().catch((error) => {
        console.error("[App] Failed to check XSUAA session:", error);
      });
    }
  }, [isXsuaaMode, checkXsuaaSession]);

  return (
    <Routes>
      {/* Open routes (no auth wrapper) */}
      <Route element={<OpenLayout />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route path="/site/view/public/:slug" element={<PublicSitePage />} />
        <Route path="/presentations/new" element={<PresentationsNewPage />} />
      </Route>

      {/* Public auth routes - only in local mode */}
      {!isXsuaaMode && (
        <Route element={<PublicLayout />}>
          <Route path="/login" element={<LoginPage />} />
        </Route>
      )}

      {/* XSUAA callback - redirect to dashboard */}
      {isXsuaaMode && (
        <Route path="/login/callback" element={<Navigate to="/dashboard" replace />} />
      )}

      {/* Protected routes */}
      <Route element={<ProtectedLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />

        {/* Agents */}
        <Route path="/agents" element={<AgentsPage />} />
        <Route
          path="/agents/standalone/:id/execute"
          element={<AgentStandaloneExecutePage />}
        />
        <Route
          path="/agents/standalone/:id/memory"
          element={<AgentMemoryInspectorPage />}
        />
        <Route
          path="/agents/teams/:id/execute"
          element={<AgentTeamExecutePage />}
        />

        {/* Evaluations */}
        <Route path="/evaluations" element={<EvaluationsPage />} />

        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/bookmarks" element={<BookmarksPage />} />

        {/* Chat */}
        <Route path="/chat" element={<ChatIndexPage />} />
        <Route path="/chat/:id" element={<ChatDetailPage />} />

        <Route path="/communities" element={<CommunitiesPage />} />
        <Route path="/entities" element={<EntitiesPage />} />
        <Route path="/graph" element={<GraphPage />} />

        {/* Microsites */}
        <Route path="/microsites" element={<MicrositesPage />} />
        <Route path="/microsites/:id" element={<MicrositeDetailPage />} />
        <Route path="/microsites/:id/edit" element={<MicrositeEditPage />} />

        <Route path="/orchestration" element={<OrchestrationPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/snapshots" element={<SnapshotsPage />} />

        {/* Sources */}
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/sources/new" element={<SourceNewPage />} />
        <Route path="/sources/:id" element={<SourceDetailPage />} />

        {/* Templates */}
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/templates/:id" element={<TemplateDetailPage />} />

        <Route path="/test-page" element={<TestPage />} />
        <Route path="/workflow-templates" element={<WorkflowTemplatesPage />} />

        {/* Workflows */}
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/workflows/:id" element={<WorkflowDetailPage />} />
        <Route
          path="/workflows/:id/settings"
          element={<WorkflowSettingsPage />}
        />
        <Route
          path="/workflows/:id/schedules"
          element={<WorkflowSchedulesPage />}
        />
        <Route
          path="/workflows/:id/executions"
          element={<WorkflowExecutionsPage />}
        />
        <Route
          path="/workflows/:id/executions/:executionId"
          element={<WorkflowExecutionDetailPage />}
        />
        <Route
          path="/workflows/:id/evaluations"
          element={<WorkflowEvaluationsPage />}
        />

        {/* Workspaces */}
        <Route path="/workspaces" element={<WorkspacesPage />} />
        <Route
          path="/workspaces/create/guided"
          element={<WorkspaceCreateGuidedPage />}
        />
        <Route path="/workspaces/:id" element={<WorkspaceDetailPage />} />
        <Route
          path="/workspaces/:id/graph"
          element={<WorkspaceGraphPage />}
        />

        {/* Settings (nested layout adds padding wrapper) */}
        <Route path="/settings" element={<SettingsLayout />}>
          <Route index element={<SettingsIndexPage />} />
          <Route path="actions" element={<SettingsActionsPage />} />
          <Route path="agents" element={<SettingsAgentsPage />} />
          <Route
            path="agents/teams/:teamId/execute"
            element={<SettingsAgentTeamExecutePage />}
          />
          <Route
            path="api-connections"
            element={<SettingsApiConnectionsPage />}
          />
          <Route path="api-keys" element={<SettingsApiKeysPage />} />
          <Route path="chat" element={<SettingsChatPage />} />
          <Route path="daily-brief" element={<SettingsDailyBriefPage />} />
          <Route path="database" element={<SettingsDatabasePage />} />
          <Route path="folders" element={<SettingsFoldersPage />} />
          <Route path="graph" element={<SettingsGraphPage />} />
          <Route
            path="hana-connections"
            element={<SettingsHanaConnectionsPage />}
          />
          <Route path="mcp-servers" element={<SettingsMcpServersPage />} />
          <Route path="models" element={<SettingsModelsPage />} />
          <Route path="oauth-apps" element={<SettingsOauthAppsPage />} />
          <Route path="observability" element={<SettingsObservabilityPage />} />
          <Route path="prompts" element={<SettingsPromptsPage />} />
          <Route path="roles" element={<SettingsRolesPage />} />
          <Route path="lookups" element={<SettingsLookupsPage />} />
          <Route path="skills" element={<SettingsSkillsPage />} />
          <Route path="smtp" element={<SettingsSmtpPage />} />
          <Route path="tools" element={<SettingsToolsPage />} />
          <Route path="users" element={<SettingsUsersPage />} />
        </Route>
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
