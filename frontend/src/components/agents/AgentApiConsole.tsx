/**
 * AgentApiConsole
 *
 * Developer-facing surface that exposes the REST API for an agent runtime:
 * endpoints, request/response JSON schemas, copyable code snippets
 * (cURL / JS / Python), and an interactive testing console that fires real
 * requests against the live backend.
 *
 * The component is *kind-agnostic*. It renders for either:
 *   - kind="standalone" → /api/standalone-agents/{id}/execute(/stream)
 *   - kind="team"       → /api/agents/teams/{id}/execute(/stream)
 *
 * The two surfaces share the same UI; only the "spec" (entity loader,
 * endpoints, schemas, sync/stream runners, banner copy) differs. Both
 * instances are mounted from `AgentsPage.tsx`.
 */

import { useState, useMemo, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  listStandaloneAgents,
  executeStandaloneAgent,
  executeStandaloneAgentStream,
} from "@/lib/api/standalone-agents";
import { agentsApi } from "@/lib/api/agents";
import type {
  StandaloneAgent,
  StandaloneAgentExecution,
  AgentTeam,
  TeamExecution,
} from "@/lib/types";
import { API_BASE_URL } from "@/lib/config/api";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Bot,
  Code2,
  Copy,
  Check,
  Play,
  Search as SearchIcon,
  Loader2,
  FileJson,
  Terminal,
  Zap,
  AlertCircle,
  CheckCircle2,
  Globe,
  Users,
} from "lucide-react";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// HTTP method colour map — matches conventions in tools like Postman/Swagger
// so developers parse it at a glance.
// ---------------------------------------------------------------------------

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  POST: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  PUT: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  DELETE: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
};

// ---------------------------------------------------------------------------
// Kind = which entity API we're rendering. Drives endpoint paths, schemas,
// list/runner functions, banner copy, and icons. Add a third kind here and
// the rest of the component picks it up automatically.
// ---------------------------------------------------------------------------

export type ApiKind = "standalone" | "team";

// ---------------------------------------------------------------------------
// Shared types — endpoint catalog & runtime entity (ListItem) shape.
// ---------------------------------------------------------------------------

interface EndpointDef {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: (id: string) => string;
  title: string;
  description: string;
  hasBody: boolean;
  /** When set, render this notice prominently inside the expanded row.
   *  Use for behavioural quirks the snippet alone won't reveal (e.g. the
   *  sync endpoint returning before the agent finishes). */
  notice?: { tone: "warn" | "info"; text: string };
  /** Optional follow-up snippet shown after the main code block. Used to
   *  document the polling loop callers need after firing the sync endpoint. */
  followUp?: {
    title: string;
    curl: (id: string) => string;
    js: (id: string) => string;
    python: (id: string) => string;
  };
}

/** Minimal shape every entity in the left rail needs to render. Both
 *  StandaloneAgent and AgentTeam map onto this through their kind's spec. */
interface ListItem {
  id: string;
  name: string;
  description?: string;
  /** Short label shown next to the name — role for agents, agent count for
   *  teams. */
  badge?: string;
  /** Optional second small line — model for agents, pattern for teams. */
  meta?: string;
}

// ---------------------------------------------------------------------------
// Standalone-agent polling snippets — paired with the standalone sync
// `/execute` endpoint, which returns status='running' immediately and expects
// the caller to GET /executions/{execution_id} until it lands on a terminal
// status. (The team endpoint runs synchronously and doesn't need this.)
// ---------------------------------------------------------------------------

const STANDALONE_POLL_CURL = (_id: string) => `# After /execute returns, poll the executions endpoint until status != "running"
EXEC_ID="<execution_id from /execute response>"
while :; do
  RESP=$(curl -s '${buildAbsoluteUrl(`/standalone-agents/executions/$EXEC_ID`)}')
  STATUS=$(echo "$RESP" | python -c 'import json,sys;print(json.load(sys.stdin)["status"])')
  echo "status=$STATUS"
  [ "$STATUS" != "running" ] && echo "$RESP" && break
  sleep 2
done`;

const STANDALONE_POLL_JS = (_id: string) => `// After /execute returns, poll until status != "running"
async function waitForExecution(executionId) {
  const url = '${buildAbsoluteUrl("/standalone-agents/executions")}/' + executionId;
  while (true) {
    const exec = await (await fetch(url)).json();
    if (exec.status !== 'running') return exec;
    await new Promise(r => setTimeout(r, 2000));
  }
}

const exec = await waitForExecution('<execution_id from /execute response>');
console.log(exec.status, exec.result);`;

const STANDALONE_POLL_PY = (_id: string) => `# After /execute returns, poll until status != "running"
import time, requests

def wait_for_execution(execution_id, every=2.0):
    url = f'${buildAbsoluteUrl("/standalone-agents/executions")}/{execution_id}'
    while True:
        exec_ = requests.get(url).json()
        if exec_['status'] != 'running':
            return exec_
        time.sleep(every)

exec_ = wait_for_execution('<execution_id from /execute response>')
print(exec_['status'], exec_.get('result'))`;

// ---------------------------------------------------------------------------
// Per-kind endpoint catalogs — keep these lists in sync with the routers in
// backend/api/routers/ (standalone_agents.py, agents.py).
// ---------------------------------------------------------------------------

const STANDALONE_ENDPOINTS: EndpointDef[] = [
  {
    method: "POST",
    path: (id) => `/standalone-agents/${id}/execute`,
    title: "Execute (async — returns immediately)",
    description:
      "Creates an execution record and returns it with status='running'. The agent then runs in the background. Poll GET /executions/{id} until status is 'completed', 'failed', or 'cancelled'.",
    hasBody: true,
    notice: {
      tone: "warn",
      text:
        "This endpoint does NOT block until the agent finishes. The response comes back instantly with status='running' and no result. To get the final answer, poll GET /standalone-agents/executions/{execution_id} (snippet below), or call the streaming endpoint instead.",
    },
    followUp: {
      title: "Poll for the final result",
      curl: STANDALONE_POLL_CURL,
      js: STANDALONE_POLL_JS,
      python: STANDALONE_POLL_PY,
    },
  },
  {
    method: "POST",
    path: (id) => `/standalone-agents/${id}/execute/stream`,
    title: "Execute (streaming — recommended for long runs)",
    description:
      "Runs the agent and streams progress as Server-Sent Events. Emits 'metadata', 'agent_step', 'chunk', 'ui_component', and finally 'done' (or 'error'). Server sends a keep-alive ping every 5s, so long-running agents won't be dropped by idle proxy timeouts.",
    hasBody: true,
    notice: {
      tone: "info",
      text:
        "Use this for any agent that may take more than a few seconds. The connection stays open until 'done' or 'error' arrives — your client just reads events as they come.",
    },
  },
  {
    method: "GET",
    path: (id) => `/standalone-agents/${id}`,
    title: "Get agent",
    description: "Fetch this agent's configuration.",
    hasBody: false,
  },
  {
    method: "GET",
    path: (id) => `/standalone-agents/${id}/executions?limit=20`,
    title: "List executions",
    description: "Fetch this agent's recent execution history.",
    hasBody: false,
  },
];

const TEAM_ENDPOINTS: EndpointDef[] = [
  {
    method: "POST",
    path: (id) => `/agents/teams/${id}/execute`,
    title: "Execute (sync — runs to completion)",
    description:
      "Runs the team's LangGraph orchestrator and returns the final result with all steps, tasks, and inter-agent messages. This call blocks until the team finishes — long runs may exceed proxy idle timeouts (AppRouter / nginx default 30–60s).",
    hasBody: true,
    notice: {
      tone: "warn",
      text:
        "Returns only when execution completes. For teams that run longer than ~30s end-to-end, prefer /execute/stream so the open connection isn't dropped by an idle proxy.",
    },
  },
  {
    method: "POST",
    path: (id) => `/agents/teams/${id}/execute/stream`,
    title: "Execute (streaming — recommended for long runs)",
    description:
      "Runs the team and streams progress as Server-Sent Events. Emits 'metadata', 'step_start', 'step_complete', 'tool_call', 'tool_result', 'llm_call', 'llm_response', and finally 'done' (or 'error'). The orchestrator emits frequently, which keeps the connection alive through proxies.",
    hasBody: true,
    notice: {
      tone: "info",
      text:
        "Use this for any team query that may take more than a few seconds. Read events as they arrive; 'done' carries the final result and the full tasks/messages array.",
    },
  },
  {
    method: "GET",
    path: (id) => `/agents/teams/${id}`,
    title: "Get team",
    description: "Fetch this team's configuration including its agents.",
    hasBody: false,
  },
  {
    method: "GET",
    path: (id) => `/agents/teams/${id}/executions`,
    title: "List executions",
    description: "Fetch this team's recent execution history.",
    hasBody: false,
  },
];

// ---------------------------------------------------------------------------
// JSON Schemas — mirror the Pydantic models in backend/api/models.py.
// We hand-roll them rather than fetching /openapi.json so the schemas render
// instantly and stay readable; if the backend models drift, update these to
// match.
// ---------------------------------------------------------------------------

const STANDALONE_REQUEST_SCHEMA = {
  $schema: "http://json-schema.org/draft-07/schema#",
  title: "StandaloneAgentExecuteRequest",
  type: "object",
  required: ["query"],
  properties: {
    query: {
      type: "string",
      minLength: 1,
      description: "Query or task for the agent",
    },
    context_source_ids: {
      type: ["array", "null"],
      items: { type: "string" },
      description:
        "Optional source IDs to use as context (overrides agent's data_source_ids)",
    },
    session_id: {
      type: ["string", "null"],
      description: "Optional chat session link",
    },
    max_steps: {
      type: "integer",
      minimum: 1,
      maximum: 50,
      default: 10,
      description: "Maximum execution steps",
    },
    stream: {
      type: "boolean",
      default: false,
      description: "Whether to stream progress via SSE",
    },
  },
} as const;

const STANDALONE_RESPONSE_SCHEMA = {
  $schema: "http://json-schema.org/draft-07/schema#",
  title: "StandaloneAgentExecutionResponse",
  type: "object",
  required: ["id", "agent_id", "query", "status", "started_at"],
  properties: {
    id: { type: "string", description: "Execution ID" },
    agent_id: { type: "string" },
    query: { type: "string" },
    status: {
      type: "string",
      enum: ["running", "completed", "failed", "cancelled"],
    },
    steps: {
      type: "array",
      items: {
        type: "object",
        properties: {
          step_number: { type: "integer" },
          action: { type: "string" },
          status: { type: "string" },
          tool_name: { type: ["string", "null"] },
          tool_input: { type: ["object", "null"] },
          result: { type: ["string", "null"] },
          started_at: { type: ["string", "null"], format: "date-time" },
          completed_at: { type: ["string", "null"], format: "date-time" },
        },
      },
    },
    result: { type: ["string", "null"] },
    error: { type: ["string", "null"] },
    context: { type: ["object", "null"] },
    tool_calls: { type: ["array", "null"] },
    started_at: { type: "string", format: "date-time" },
    completed_at: { type: ["string", "null"], format: "date-time" },
    duration_ms: { type: ["integer", "null"] },
  },
} as const;

const TEAM_REQUEST_SCHEMA = {
  $schema: "http://json-schema.org/draft-07/schema#",
  title: "TeamExecuteRequest",
  type: "object",
  required: ["query"],
  properties: {
    query: {
      type: "string",
      minLength: 1,
      description: "Query or task for the team to execute",
    },
    context_source_ids: {
      type: ["array", "null"],
      items: { type: "string" },
      description: "Optional source IDs to use as context",
    },
    notebook_id: {
      type: ["string", "null"],
      description: "Optional notebook for context",
    },
    max_steps: {
      type: "integer",
      minimum: 1,
      maximum: 50,
      default: 10,
      description: "Maximum execution steps",
    },
    stream: {
      type: "boolean",
      default: false,
      description: "Whether to stream progress via SSE",
    },
    prompt_role: {
      type: ["string", "null"],
      description: "Role of prompt template to use for execution",
    },
  },
} as const;

const TEAM_RESPONSE_SCHEMA = {
  $schema: "http://json-schema.org/draft-07/schema#",
  title: "TeamExecutionResponse",
  type: "object",
  required: ["id", "team_id", "query", "status", "started_at"],
  properties: {
    id: { type: "string", description: "Execution ID" },
    team_id: { type: "string" },
    query: { type: "string" },
    status: {
      type: "string",
      enum: ["running", "completed", "failed", "cancelled"],
    },
    steps: {
      type: "array",
      description: "Workflow steps emitted by the orchestrator",
      items: {
        type: "object",
        properties: {
          step_number: { type: "integer" },
          agent_id: { type: ["string", "null"] },
          agent_name: { type: ["string", "null"] },
          action: { type: "string" },
          status: { type: "string" },
          result: { type: ["string", "null"] },
          started_at: { type: ["string", "null"], format: "date-time" },
          completed_at: { type: ["string", "null"], format: "date-time" },
        },
      },
    },
    tasks: {
      type: "array",
      description: "Sub-tasks the team decomposed the query into",
      items: { type: "object" },
    },
    messages: {
      type: "array",
      description: "Inter-agent messages exchanged during execution",
      items: {
        type: "object",
        properties: {
          id: { type: "string" },
          execution_id: { type: "string" },
          from_agent_id: { type: "string" },
          from_agent_name: { type: ["string", "null"] },
          to_agent_id: { type: ["string", "null"] },
          to_agent_name: { type: ["string", "null"] },
          message_type: { type: "string" },
          content: { type: "string" },
          metadata: { type: ["object", "null"] },
          created: { type: "string", format: "date-time" },
        },
      },
    },
    result: { type: ["string", "null"] },
    started_at: { type: "string", format: "date-time" },
    completed_at: { type: ["string", "null"], format: "date-time" },
  },
} as const;

// ---------------------------------------------------------------------------
// Stream execution for teams
//
// `agentsApi.executeTeam` mixes streaming + non-streaming behind one method,
// dispatching on whether `onStep` is provided. For the test console we want
// a thinner adapter that emits the raw SSE-event-shape `{type, data}` so the
// console can render every event verbatim — same as the standalone helper.
// ---------------------------------------------------------------------------

async function executeTeamStream(
  teamId: string,
  request: { query: string; max_steps?: number; stream?: boolean; context_source_ids?: string[] | null },
  onEvent: (event: { type: string; data: any }) => void,
): Promise<void> {
  const base = API_BASE_URL.startsWith("http")
    ? API_BASE_URL
    : `${typeof window !== "undefined" ? window.location.origin : ""}${API_BASE_URL}`;
  const response = await fetch(`${base}/agents/teams/${teamId}/execute/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`Stream failed: ${response.status} ${await response.text()}`);
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Split on SSE record terminator. Each frame is "event: <t>\ndata: <json>".
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      for (const frame of frames) {
        let eventType = "message";
        let dataStr = "";
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
        }
        if (!dataStr) continue;
        try {
          onEvent({ type: eventType, data: JSON.parse(dataStr) });
        } catch {
          // Forward raw text if the server emitted something non-JSON.
          onEvent({ type: eventType, data: dataStr });
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ---------------------------------------------------------------------------
// Spec — collects everything that varies between kinds. Two specs below;
// both are picked up by the main component via the `kind` prop.
// ---------------------------------------------------------------------------

interface ApiSpec {
  /** Used in the entity list header. */
  entityNoun: string; // "agent" / "team"
  entityNounPlural: string; // "agents" / "teams"
  /** Heading shown above the search box on the left rail. */
  listLabel: string;
  /** lucide-react icon component for the entity. */
  Icon: typeof Bot;
  /** Endpoint catalog rendered in the Endpoints sub-tab. */
  endpoints: EndpointDef[];
  /** JSON Schemas rendered in the Schemas sub-tab. */
  requestSchema: object;
  responseSchema: object;
  schemaTitles: { request: string; response: string };
  /** Loads entities for the left rail. */
  loadEntities: () => Promise<ListItem[]>;
  /** Reactql cache key for the loader. */
  queryKey: readonly unknown[];
  /** Fires the synchronous /execute endpoint. Returns the response payload. */
  executeSync: (id: string, body: any) => Promise<any>;
  /** Streams /execute/stream and feeds events to onEvent. */
  executeStream: (
    id: string,
    body: any,
    onEvent: (e: { type: string; data: any }) => void,
  ) => Promise<void>;
  /** One-line banner copy describing the timeout / streaming guidance. */
  bannerCopy: React.ReactNode;
  /** Empty-state copy when no entities exist. */
  emptyState: { title: string; body: string };
  /** Test console copy that varies by kind. */
  consoleCopy: {
    queryPlaceholder: string;
    syncLabel: string; // dropdown label for the non-streaming mode
    /** Inline warning shown beneath the Mode select when sync is chosen.
     *  null hides it entirely (e.g. when sync is already the right answer). */
    syncNote: string | null;
  };
}

function adaptStandalone(a: StandaloneAgent): ListItem {
  return {
    id: a.id,
    name: a.name,
    description: a.description,
    badge: a.role,
    meta: a.model_name,
  };
}

function adaptTeam(t: AgentTeam): ListItem {
  return {
    id: t.id,
    name: t.name,
    description: t.description,
    badge: `${t.agents.length} agent${t.agents.length === 1 ? "" : "s"}`,
    meta: t.orchestration_pattern,
  };
}

const STANDALONE_SPEC: ApiSpec = {
  entityNoun: "agent",
  entityNounPlural: "agents",
  listLabel: "Agents",
  Icon: Bot,
  endpoints: STANDALONE_ENDPOINTS,
  requestSchema: STANDALONE_REQUEST_SCHEMA,
  responseSchema: STANDALONE_RESPONSE_SCHEMA,
  schemaTitles: {
    request: "Input — request body",
    response: "Output — execution response",
  },
  queryKey: ["standalone-agents", "api-tab"],
  loadEntities: async () => {
    const res = await listStandaloneAgents({ status: "active", limit: 200 });
    return (res.agents || []).map(adaptStandalone);
  },
  executeSync: async (id, body) => {
    const exec: StandaloneAgentExecution = await executeStandaloneAgent(id, body);
    return exec;
  },
  executeStream: (id, body, onEvent) =>
    executeStandaloneAgentStream(id, body, onEvent),
  bannerCopy: (
    <span>
      <strong>Long-running calls:</strong> use the{" "}
      <code className="px-1 py-0.5 rounded bg-white/70 dark:bg-gray-900/60 font-mono text-[11px]">
        /execute/stream
      </code>{" "}
      endpoint. It emits an SSE keep-alive every 5 s so the connection survives
      idle proxy timeouts (AppRouter / nginx default 30–60 s). The plain{" "}
      <code className="px-1 py-0.5 rounded bg-white/70 dark:bg-gray-900/60 font-mono text-[11px]">
        /execute
      </code>{" "}
      endpoint is async — it returns immediately with{" "}
      <code className="font-mono">status="running"</code> and you poll{" "}
      <code className="px-1 py-0.5 rounded bg-white/70 dark:bg-gray-900/60 font-mono text-[11px]">
        GET /executions/{"{"}id{"}"}
      </code>{" "}
      for the final result.
    </span>
  ),
  emptyState: {
    title: "No agents to expose yet",
    body: "Create a standalone agent first — the API tab automatically generates endpoints, schemas, and a test console for every active agent.",
  },
  consoleCopy: {
    queryPlaceholder: "What should the agent do? e.g. 'Summarise our Q4 sales pipeline.'",
    syncLabel: "Async (returns immediately)",
    syncNote:
      "Async mode returns instantly with status=\"running\" — the agent runs in the background. The console won't show a final result; check the agent's execution history instead.",
  },
};

const TEAM_SPEC: ApiSpec = {
  entityNoun: "team",
  entityNounPlural: "teams",
  listLabel: "Teams",
  Icon: Users,
  endpoints: TEAM_ENDPOINTS,
  requestSchema: TEAM_REQUEST_SCHEMA,
  responseSchema: TEAM_RESPONSE_SCHEMA,
  schemaTitles: {
    request: "Input — request body",
    response: "Output — execution response (tasks, messages, steps)",
  },
  queryKey: ["agent-teams", "api-tab"],
  loadEntities: async () => {
    const teams = await agentsApi.listTeams();
    return (Array.isArray(teams) ? teams : []).map(adaptTeam);
  },
  executeSync: async (id, body) => {
    const exec: TeamExecution = await agentsApi.executeTeam(id, body) as TeamExecution;
    return exec;
  },
  executeStream: (id, body, onEvent) => executeTeamStream(id, body, onEvent),
  bannerCopy: (
    <span>
      <strong>Long-running calls:</strong> use the{" "}
      <code className="px-1 py-0.5 rounded bg-white/70 dark:bg-gray-900/60 font-mono text-[11px]">
        /execute/stream
      </code>{" "}
      endpoint. The plain{" "}
      <code className="px-1 py-0.5 rounded bg-white/70 dark:bg-gray-900/60 font-mono text-[11px]">
        /execute
      </code>{" "}
      endpoint is synchronous — it runs the team to completion before returning,
      so long runs may exceed proxy idle timeouts (AppRouter / nginx default
      30–60 s). Streaming keeps the connection alive while the orchestrator
      emits step events.
    </span>
  ),
  emptyState: {
    title: "No agent teams to expose yet",
    body: "Create an agent team first — the API tab automatically generates endpoints, schemas, and a test console for every team.",
  },
  consoleCopy: {
    queryPlaceholder:
      "What should the team work on? e.g. 'Research and summarise our top three competitors.'",
    syncLabel: "Sync (runs to completion)",
    syncNote:
      "Sync mode blocks until the orchestrator finishes. Long runs may exceed the proxy idle timeout — switch to streaming if you see the connection drop.",
  },
};

const SPEC_REGISTRY: Record<ApiKind, ApiSpec> = {
  standalone: STANDALONE_SPEC,
  team: TEAM_SPEC,
};

// ---------------------------------------------------------------------------
// Snippet helpers
// ---------------------------------------------------------------------------

function buildAbsoluteUrl(path: string): string {
  // API_BASE_URL is "/api" or "https://host/api"; if relative, prepend the
  // current origin so the snippet is paste-ready.
  const base = API_BASE_URL.startsWith("http")
    ? API_BASE_URL
    : `${typeof window !== "undefined" ? window.location.origin : "http://localhost:5001"}${API_BASE_URL}`;
  return `${base}${path}`;
}

function curlSnippet(endpoint: EndpointDef, agentId: string, body?: string): string {
  const url = buildAbsoluteUrl(endpoint.path(agentId));
  if (!endpoint.hasBody) {
    return `curl -X ${endpoint.method} '${url}' \\
  -H 'Accept: application/json'`;
  }
  return `curl -X ${endpoint.method} '${url}' \\
  -H 'Content-Type: application/json' \\
  -H 'Accept: application/json' \\
  -d '${body || "{}"}'`;
}

function jsSnippet(endpoint: EndpointDef, agentId: string, body?: string): string {
  const url = buildAbsoluteUrl(endpoint.path(agentId));
  if (!endpoint.hasBody) {
    return `const res = await fetch('${url}', {
  method: '${endpoint.method}',
  headers: { 'Accept': 'application/json' },
});
const data = await res.json();
console.log(data);`;
  }
  return `const res = await fetch('${url}', {
  method: '${endpoint.method}',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
  body: JSON.stringify(${body || "{}"}),
});
const data = await res.json();
console.log(data);`;
}

function pythonSnippet(endpoint: EndpointDef, agentId: string, body?: string): string {
  const url = buildAbsoluteUrl(endpoint.path(agentId));
  if (!endpoint.hasBody) {
    return `import requests

r = requests.${endpoint.method.toLowerCase()}('${url}')
print(r.json())`;
  }
  return `import requests

payload = ${body || "{}"}
r = requests.${endpoint.method.toLowerCase()}(
    '${url}',
    json=payload,
)
print(r.json())`;
}

// ---------------------------------------------------------------------------
// Reusable code block with copy-to-clipboard
// ---------------------------------------------------------------------------

function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      toast.success("Copied");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Copy failed");
    }
  };

  return (
    <div className="relative group">
      {language && (
        <span className="absolute top-2 left-3 text-[10px] uppercase tracking-wider text-gray-400 font-mono pointer-events-none">
          {language}
        </span>
      )}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={onCopy}
        className="absolute top-1.5 right-1.5 h-7 px-2 text-xs opacity-70 hover:opacity-100"
      >
        {copied ? (
          <>
            <Check className="w-3.5 h-3.5 mr-1" /> Copied
          </>
        ) : (
          <>
            <Copy className="w-3.5 h-3.5 mr-1" /> Copy
          </>
        )}
      </Button>
      <pre className="bg-gray-950 text-gray-100 rounded-lg p-4 pt-7 overflow-x-auto text-xs font-mono leading-relaxed border border-gray-800">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Endpoint row — collapsible card showing path, snippets, and (where
// applicable) the request/response schema preview.
// ---------------------------------------------------------------------------

function EndpointRow({
  endpoint,
  agentId,
  defaultBody,
}: {
  endpoint: EndpointDef;
  agentId: string;
  defaultBody: string;
}) {
  const [snippetLang, setSnippetLang] = useState<"curl" | "js" | "python">("curl");
  const [open, setOpen] = useState(false);

  const snippet = useMemo(() => {
    if (snippetLang === "curl") return curlSnippet(endpoint, agentId, defaultBody);
    if (snippetLang === "js") return jsSnippet(endpoint, agentId, defaultBody);
    return pythonSnippet(endpoint, agentId, defaultBody);
  }, [snippetLang, endpoint, agentId, defaultBody]);

  const followUpSnippet = useMemo(() => {
    if (!endpoint.followUp) return null;
    if (snippetLang === "curl") return endpoint.followUp.curl(agentId);
    if (snippetLang === "js") return endpoint.followUp.js(agentId);
    return endpoint.followUp.python(agentId);
  }, [endpoint, agentId, snippetLang]);

  return (
    <div className="border rounded-lg overflow-hidden bg-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors text-left"
      >
        <Badge
          className={`${METHOD_COLORS[endpoint.method]} font-mono text-[11px] tracking-wider border-0 shrink-0`}
        >
          {endpoint.method}
        </Badge>
        <code className="text-sm font-mono flex-1 min-w-0 truncate">
          {endpoint.path(agentId)}
        </code>
        <span className="text-xs text-muted-foreground shrink-0 hidden md:inline">
          {endpoint.title}
        </span>
      </button>

      {open && (
        <div className="border-t bg-muted/20 p-4 space-y-3">
          <p className="text-xs text-muted-foreground">{endpoint.description}</p>

          {/* Behavioural notice — only shown for endpoints with surprising
              semantics (e.g. /execute returning before the agent finishes). */}
          {endpoint.notice && (
            <div
              className={`flex items-start gap-2 rounded-md border p-2.5 text-xs ${
                endpoint.notice.tone === "warn"
                  ? "border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200"
                  : "border-blue-200 dark:border-blue-900/60 bg-blue-50 dark:bg-blue-950/30 text-blue-900 dark:text-blue-200"
              }`}
            >
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span className="leading-relaxed">{endpoint.notice.text}</span>
            </div>
          )}

          <div className="flex items-center gap-2">
            <Label className="text-xs">Snippet:</Label>
            <div className="flex rounded-md border bg-background p-0.5">
              {(["curl", "js", "python"] as const).map((lang) => (
                <button
                  key={lang}
                  type="button"
                  onClick={() => setSnippetLang(lang)}
                  className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                    snippetLang === lang
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {lang === "curl" ? "cURL" : lang === "js" ? "JavaScript" : "Python"}
                </button>
              ))}
            </div>
          </div>

          <CodeBlock code={snippet} language={snippetLang} />

          {/* Follow-up snippet — currently only used by /execute to show the
              polling loop callers need to actually retrieve the result. */}
          {endpoint.followUp && followUpSnippet && (
            <div className="space-y-2 pt-2 border-t border-dashed">
              <Label className="text-xs">{endpoint.followUp.title}</Label>
              <CodeBlock code={followUpSnippet} language={snippetLang} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Schema viewer — pretty-prints a JSON Schema with copy.
// ---------------------------------------------------------------------------

function SchemaViewer({ title, schema }: { title: string; schema: object }) {
  const json = useMemo(() => JSON.stringify(schema, null, 2), [schema]);
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <FileJson className="w-4 h-4 text-muted-foreground" />
        <h4 className="text-sm font-semibold">{title}</h4>
      </div>
      <CodeBlock code={json} language="json" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Test Console — POST to /execute and render the response.
// ---------------------------------------------------------------------------

interface TestEvent {
  id: number;
  type: string;
  data: any;
  ts: string;
}

function TestConsole({ entity, spec }: { entity: ListItem; spec: ApiSpec }) {
  const [query, setQuery] = useState("");
  const [maxSteps, setMaxSteps] = useState(10);
  const [streaming, setStreaming] = useState(true);
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<TestEvent[]>([]);
  const [elapsed, setElapsed] = useState<number | null>(null);

  // Tick a wall-clock timer during a request so the UI feels alive.
  useEffect(() => {
    if (!running) return;
    const start = performance.now();
    const t = window.setInterval(
      () => setElapsed(Math.round(performance.now() - start)),
      100
    );
    return () => window.clearInterval(t);
  }, [running]);

  const runRequest = async () => {
    if (!query.trim()) {
      toast.error("Query is required");
      return;
    }
    setRunning(true);
    setResponse(null);
    setError(null);
    setEvents([]);
    setElapsed(0);

    const payload = {
      query: query.trim(),
      max_steps: maxSteps,
      stream: streaming,
    };

    try {
      if (streaming) {
        let counter = 0;
        await spec.executeStream(entity.id, payload, (evt) => {
          counter += 1;
          setEvents((prev) => [
            ...prev,
            {
              id: counter,
              type: evt.type,
              data: evt.data,
              ts: new Date().toISOString().split("T")[1].replace("Z", ""),
            },
          ]);
          // The 'done' event payload IS the final execution record.
          if (evt.type === "done" && evt.data) setResponse(evt.data);
          if (evt.type === "error" && evt.data) {
            setError(
              typeof evt.data === "string"
                ? evt.data
                : evt.data.error || evt.data.message || JSON.stringify(evt.data),
            );
          }
        });
      } else {
        const exec = await spec.executeSync(entity.id, payload);
        setResponse(exec);
      }
    } catch (e: any) {
      setError(e?.message || String(e));
      toast.error("Request failed");
    } finally {
      setRunning(false);
    }
  };

  const requestPreview = useMemo(
    () =>
      JSON.stringify(
        { query: query || "<your query>", max_steps: maxSteps, stream: streaming },
        null,
        2
      ),
    [query, maxSteps, streaming]
  );

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Request column */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Request
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-xs">Query</Label>
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={spec.consoleCopy.queryPlaceholder}
              rows={4}
              className="font-mono text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Max steps</Label>
              <Input
                type="number"
                min={1}
                max={50}
                value={maxSteps}
                onChange={(e) =>
                  setMaxSteps(Math.max(1, Math.min(50, Number(e.target.value) || 10)))
                }
              />
            </div>
            <div>
              <Label className="text-xs">Mode</Label>
              <Select
                value={streaming ? "stream" : "sync"}
                onValueChange={(v) => setStreaming(v === "stream")}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                  <SelectItem value="stream">Streaming (SSE) — recommended</SelectItem>
                  <SelectItem value="sync">{spec.consoleCopy.syncLabel}</SelectItem>
                </SelectContent>
              </Select>
              {!streaming && spec.consoleCopy.syncNote && (
                <p className="text-[11px] text-muted-foreground mt-1 leading-snug">
                  {spec.consoleCopy.syncNote}
                </p>
              )}
            </div>
          </div>

          <div>
            <Label className="text-xs mb-1.5 block">Request body preview</Label>
            <CodeBlock code={requestPreview} language="json" />
          </div>

          <Button
            onClick={runRequest}
            disabled={running || !query.trim()}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
          >
            {running ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Running… {elapsed !== null ? `${(elapsed / 1000).toFixed(1)}s` : ""}
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Send request
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Response column */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            {error ? (
              <>
                <AlertCircle className="w-4 h-4 text-red-500" />
                Response — error
              </>
            ) : response?.status === "completed" ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                Response
              </>
            ) : (
              <>
                <Terminal className="w-4 h-4" />
                Response
              </>
            )}
            {response?.duration_ms != null && (
              <Badge variant="outline" className="text-[10px] ml-auto">
                {response.duration_ms}ms
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {error && (
            <div className="rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 p-3 text-xs text-red-700 dark:text-red-300 font-mono break-words">
              {error}
            </div>
          )}

          {streaming && events.length > 0 && (
            <div>
              <Label className="text-xs mb-1.5 block">Live events</Label>
              <div className="rounded-md border bg-muted/30 max-h-48 overflow-y-auto p-2 space-y-1 font-mono text-[11px]">
                {events.map((e) => (
                  <div key={e.id} className="flex gap-2 items-start">
                    <span className="text-muted-foreground tabular-nums shrink-0">
                      {e.ts}
                    </span>
                    <Badge
                      variant="outline"
                      className="text-[10px] py-0 px-1.5 shrink-0"
                    >
                      {e.type}
                    </Badge>
                    <span className="truncate text-foreground/80">
                      {typeof e.data === "string"
                        ? e.data
                        : JSON.stringify(e.data).slice(0, 200)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {response ? (
            <div>
              <Label className="text-xs mb-1.5 block">Response body</Label>
              <CodeBlock
                code={JSON.stringify(response, null, 2)}
                language="json"
              />
            </div>
          ) : !error && !running ? (
            <p className="text-xs text-muted-foreground text-center py-12">
              Send a request to see the response here.
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AgentApiConsole({ kind = "standalone" }: { kind?: ApiKind } = {}) {
  const spec = SPEC_REGISTRY[kind];
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [innerTab, setInnerTab] = useState<"endpoints" | "schemas" | "console">(
    "endpoints"
  );

  const { data: entities = [], isLoading } = useQuery({
    queryKey: spec.queryKey,
    queryFn: spec.loadEntities,
  });

  // Pick the first entity once the list arrives so the right pane has
  // something to render immediately. Reset on kind switch.
  useEffect(() => {
    setSelectedId(null);
  }, [kind]);
  useEffect(() => {
    if (!selectedId && entities.length > 0) setSelectedId(entities[0].id);
  }, [entities, selectedId]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entities;
    return entities.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        (a.badge || "").toLowerCase().includes(q) ||
        (a.description || "").toLowerCase().includes(q)
    );
  }, [entities, search]);

  const selected = entities.find((a) => a.id === selectedId) || null;

  // Default body shown in snippets and the console request preview.
  const defaultBody = useMemo(
    () =>
      JSON.stringify(
        {
          query:
            kind === "team"
              ? "Research and summarise the latest project status"
              : "Summarise the latest project status",
          max_steps: 10,
          stream: false,
        },
        null,
        2
      ),
    [kind]
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (entities.length === 0) {
    return (
      <Card>
        <CardContent className="py-16 text-center space-y-4">
          <div className="rounded-full bg-gradient-to-br from-blue-500 to-purple-500 w-16 h-16 mx-auto flex items-center justify-center">
            <Code2 className="w-8 h-8 text-white" />
          </div>
          <div className="space-y-1">
            <p className="font-medium text-lg">{spec.emptyState.title}</p>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              {spec.emptyState.body}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const EntityIcon = spec.Icon;

  return (
    <div className="space-y-5">
      {/* Header card with API base URL — useful for sharing with external
          callers. */}
      <Card className="border-blue-200 dark:border-blue-900 bg-gradient-to-br from-blue-50/60 to-purple-50/60 dark:from-blue-950/20 dark:to-purple-950/20">
        <CardContent className="py-4 space-y-3">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2 text-sm">
              <Globe className="w-4 h-4 text-blue-600" />
              <span className="font-medium">Base URL:</span>
              <code className="px-2 py-0.5 rounded bg-white/70 dark:bg-gray-900/60 font-mono text-xs">
                {API_BASE_URL.startsWith("http")
                  ? API_BASE_URL
                  : `${typeof window !== "undefined" ? window.location.origin : ""}${API_BASE_URL}`}
              </code>
            </div>
            <span className="text-xs text-muted-foreground">
              Every active {spec.entityNoun} is reachable through these endpoints.
            </span>
          </div>

          {/* Long-running guidance — runs can take minutes; spell out which
              endpoint to use so callers don't get bitten by proxy timeouts. */}
          <div className="flex items-start gap-2 text-xs text-blue-900 dark:text-blue-200 leading-relaxed">
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            {spec.bannerCopy}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        {/* Entity list — left rail */}
        <Card className="h-fit lg:sticky lg:top-4">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <EntityIcon className="w-4 h-4" />
              {spec.listLabel}
              <Badge variant="outline" className="ml-auto text-[10px]">
                {entities.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="relative">
              <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={`Search ${spec.entityNounPlural}…`}
                className="pl-8 h-8 text-sm"
              />
            </div>
            <div className="max-h-[60vh] overflow-y-auto space-y-1 pr-1">
              {filtered.length === 0 ? (
                <p className="text-xs text-muted-foreground p-2">No matches.</p>
              ) : (
                filtered.map((a) => {
                  const isSel = a.id === selectedId;
                  return (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => setSelectedId(a.id)}
                      className={`w-full text-left p-2 rounded-md border transition-colors ${
                        isSel
                          ? "border-primary bg-primary/5"
                          : "border-transparent hover:bg-muted/50"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-medium truncate">{a.name}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {a.badge && (
                          <Badge variant="outline" className="text-[10px] py-0">
                            {a.badge}
                          </Badge>
                        )}
                        {a.meta && (
                          <span className="text-[10px] text-muted-foreground font-mono truncate">
                            {a.meta}
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>

        {/* Detail panel — right side */}
        {selected ? (
          <div className="space-y-4 min-w-0">
            {/* Selected entity header */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="shrink-0 w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                      <EntityIcon className="w-5 h-5 text-white" />
                    </div>
                    <div className="min-w-0">
                      <CardTitle className="text-base truncate">
                        {selected.name}
                      </CardTitle>
                      {selected.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                          {selected.description}
                        </p>
                      )}
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        {selected.badge && (
                          <Badge variant="outline" className="text-[10px]">
                            {selected.badge}
                          </Badge>
                        )}
                        {selected.meta && (
                          <code className="text-[10px] font-mono text-muted-foreground">
                            {selected.meta}
                          </code>
                        )}
                        <span className="text-[10px] text-muted-foreground">
                          ID:{" "}
                          <code className="font-mono">
                            {selected.id.slice(0, 8)}…
                          </code>
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardHeader>
            </Card>

            {/* Inner tabs: Endpoints / Schemas / Console */}
            <Tabs value={innerTab} onValueChange={(v) => setInnerTab(v as any)}>
              <TabsList>
                <TabsTrigger value="endpoints">
                  <Code2 className="w-3.5 h-3.5 mr-1.5" /> Endpoints
                </TabsTrigger>
                <TabsTrigger value="schemas">
                  <FileJson className="w-3.5 h-3.5 mr-1.5" /> Schemas
                </TabsTrigger>
                <TabsTrigger value="console">
                  <Terminal className="w-3.5 h-3.5 mr-1.5" /> Test Console
                </TabsTrigger>
              </TabsList>

              <TabsContent value="endpoints" className="space-y-3 mt-4">
                {spec.endpoints.map((ep, i) => (
                  <EndpointRow
                    key={i}
                    endpoint={ep}
                    agentId={selected.id}
                    defaultBody={defaultBody}
                  />
                ))}
              </TabsContent>

              <TabsContent value="schemas" className="space-y-6 mt-4">
                <SchemaViewer
                  title={spec.schemaTitles.request}
                  schema={spec.requestSchema}
                />
                <SchemaViewer
                  title={spec.schemaTitles.response}
                  schema={spec.responseSchema}
                />
              </TabsContent>

              <TabsContent value="console" className="mt-4">
                <TestConsole entity={selected} spec={spec} />
              </TabsContent>
            </Tabs>
          </div>
        ) : (
          <Card>
            <CardContent className="py-16 text-center text-sm text-muted-foreground">
              Select {spec.entityNoun === "team" ? "a team" : "an agent"} on the left to view its API.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
