'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface EndpointSpec {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  path: string;
  scope: string;
  description: string;
  requestBody?: string;
  responseBody?: string;
  parameters?: Array<{ name: string; type: string; required: boolean; description: string }>;
}

interface ApiEndpointReferenceProps {
  scopes: string[];
  apiUrl: string;
}

const ENDPOINT_SPECS: EndpointSpec[] = [
  // Teams
  {
    method: 'GET',
    path: '/api/agents/teams',
    scope: 'read:teams',
    description: 'List all agent teams',
    responseBody: `{
  "teams": [
    {
      "id": "uuid",
      "name": "Research Team",
      "description": "Team for research tasks",
      "status": "idle",
      "agents": [...],
      "created": "2026-04-20T10:00:00Z"
    }
  ],
  "total": 1
}`,
  },
  {
    method: 'POST',
    path: '/api/agents/teams',
    scope: 'write:teams',
    description: 'Create a new agent team',
    requestBody: `{
  "name": "My Team",
  "description": "Team description",
  "notebook_id": "uuid",
  "goal": "Team objective"
}`,
    responseBody: `{
  "id": "uuid",
  "name": "My Team",
  "description": "Team description",
  "status": "idle",
  "agents": [],
  "created": "2026-04-20T10:00:00Z"
}`,
  },
  {
    method: 'GET',
    path: '/api/agents/teams/{id}',
    scope: 'read:teams',
    description: 'Get team details',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
    ],
    responseBody: `{
  "id": "uuid",
  "name": "My Team",
  "description": "Team description",
  "status": "idle",
  "agents": [
    {
      "id": "uuid",
      "name": "Agent 1",
      "role": "researcher",
      "status": "idle"
    }
  ],
  "created": "2026-04-20T10:00:00Z"
}`,
  },
  {
    method: 'PUT',
    path: '/api/agents/teams/{id}',
    scope: 'write:teams',
    description: 'Update team configuration',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
    ],
    requestBody: `{
  "name": "Updated Team Name",
  "description": "Updated description",
  "goal": "Updated objective"
}`,
    responseBody: `{
  "id": "uuid",
  "name": "Updated Team Name",
  "description": "Updated description",
  "updated": "2026-04-20T11:00:00Z"
}`,
  },
  {
    method: 'DELETE',
    path: '/api/agents/teams/{id}',
    scope: 'delete:teams',
    description: 'Delete an agent team',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
    ],
    responseBody: `{
  "message": "Team deleted successfully"
}`,
  },
  {
    method: 'POST',
    path: '/api/agents/teams/{id}/execute',
    scope: 'execute:teams',
    description: 'Execute a team workflow with a query',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
    ],
    requestBody: `{
  "query": "Analyze customer data from Q1",
  "context_source_ids": ["source-uuid-1", "source-uuid-2"],
  "stream": false
}`,
    responseBody: `{
  "execution_id": "uuid",
  "status": "running",
  "result": null,
  "started_at": "2026-04-20T10:00:00Z"
}`,
  },
  {
    method: 'POST',
    path: '/api/agents/teams/{id}/execute/stream',
    scope: 'execute:teams',
    description: 'Execute team workflow with streaming response (SSE)',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
    ],
    requestBody: `{
  "query": "Analyze customer data from Q1",
  "context_source_ids": ["source-uuid-1", "source-uuid-2"]
}`,
    responseBody: `// Server-Sent Events (SSE) stream
event: agent_step
data: {"agent": "researcher", "step": "analyzing data"}

event: chunk
data: {"content": "Based on the analysis..."}

event: done
data: {"execution_id": "uuid", "status": "completed"}`,
  },
  // Agents
  {
    method: 'GET',
    path: '/api/agents/teams/{id}/agents',
    scope: 'read:agents',
    description: 'List agents in a team',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
    ],
    responseBody: `{
  "agents": [
    {
      "id": "uuid",
      "name": "Research Agent",
      "role": "researcher",
      "status": "idle",
      "capabilities": ["search", "analyze"],
      "created": "2026-04-20T10:00:00Z"
    }
  ]
}`,
  },
  {
    method: 'POST',
    path: '/api/agents/teams/{id}/spawn',
    scope: 'write:agents',
    description: 'Spawn a new agent in a team',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
    ],
    requestBody: `{
  "name": "Data Analyst",
  "role": "analyst",
  "agent_type": "data_query_agent",
  "config": {
    "model": "gpt-4",
    "tools": ["python", "sql"]
  }
}`,
    responseBody: `{
  "id": "uuid",
  "name": "Data Analyst",
  "role": "analyst",
  "status": "idle",
  "created": "2026-04-20T10:00:00Z"
}`,
  },
  {
    method: 'DELETE',
    path: '/api/agents/agents/{id}',
    scope: 'delete:agents',
    description: 'Delete an agent',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Agent ID' },
    ],
    responseBody: `{
  "message": "Agent deleted successfully"
}`,
  },
  // Tasks
  {
    method: 'GET',
    path: '/api/agents/teams/{id}/tasks',
    scope: 'read:tasks',
    description: 'List tasks for a team',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
    ],
    responseBody: `{
  "tasks": [
    {
      "id": "uuid",
      "title": "Analyze data",
      "status": "completed",
      "assigned_to": "agent-uuid",
      "created": "2026-04-20T10:00:00Z",
      "completed": "2026-04-20T10:15:00Z"
    }
  ]
}`,
  },
  {
    method: 'GET',
    path: '/api/agents/tasks/{id}',
    scope: 'read:tasks',
    description: 'Get task details',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Task ID' },
    ],
    responseBody: `{
  "id": "uuid",
  "title": "Analyze data",
  "description": "Detailed task description",
  "status": "completed",
  "result": "Analysis complete with findings...",
  "assigned_to": "agent-uuid",
  "created": "2026-04-20T10:00:00Z"
}`,
  },
  // Executions
  {
    method: 'GET',
    path: '/api/agents/teams/{id}/executions',
    scope: 'read:executions',
    description: 'List execution history for a team',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Team ID' },
      { name: 'limit', type: 'integer', required: false, description: 'Max results (default: 50)' },
    ],
    responseBody: `{
  "executions": [
    {
      "id": "uuid",
      "query": "Analyze customer data",
      "status": "completed",
      "result": "Analysis results...",
      "started_at": "2026-04-20T10:00:00Z",
      "completed_at": "2026-04-20T10:15:00Z"
    }
  ],
  "total": 1
}`,
  },
  {
    method: 'GET',
    path: '/api/agents/executions/{id}',
    scope: 'read:executions',
    description: 'Get execution details',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Execution ID' },
    ],
    responseBody: `{
  "id": "uuid",
  "query": "Analyze customer data",
  "status": "completed",
  "result": "Detailed analysis results...",
  "steps": [
    {"agent": "researcher", "action": "search", "result": "..."},
    {"agent": "analyst", "action": "analyze", "result": "..."}
  ],
  "started_at": "2026-04-20T10:00:00Z",
  "completed_at": "2026-04-20T10:15:00Z"
}`,
  },
  {
    method: 'DELETE',
    path: '/api/agents/executions/{id}',
    scope: 'write:executions',
    description: 'Delete an execution record',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Execution ID' },
    ],
    responseBody: `{
  "message": "Execution deleted successfully"
}`,
  },
  {
    method: 'POST',
    path: '/api/agents/executions/{id}/cancel',
    scope: 'write:executions',
    description: 'Cancel a running execution',
    parameters: [
      { name: 'id', type: 'string', required: true, description: 'Execution ID' },
    ],
    responseBody: `{
  "id": "uuid",
  "status": "cancelled",
  "cancelled_at": "2026-04-20T10:05:00Z"
}`,
  },
];

export function ApiEndpointReference({ scopes, apiUrl }: ApiEndpointReferenceProps) {
  const [expandedEndpoints, setExpandedEndpoints] = useState<Set<string>>(new Set());
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const filteredEndpoints = ENDPOINT_SPECS.filter((endpoint) =>
    scopes.includes(endpoint.scope)
  );

  const toggleEndpoint = (key: string) => {
    setExpandedEndpoints((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const copyCode = (code: string, key: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(key);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const getMethodColor = (method: string) => {
    switch (method) {
      case 'GET':
        return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      case 'POST':
        return 'bg-green-500/10 text-green-500 border-green-500/20';
      case 'PUT':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20';
      case 'DELETE':
        return 'bg-red-500/10 text-red-500 border-red-500/20';
      default:
        return 'bg-gray-500/10 text-gray-500 border-gray-500/20';
    }
  };

  if (filteredEndpoints.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No endpoints available for selected scopes
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {filteredEndpoints.map((endpoint) => {
        const key = `${endpoint.method}-${endpoint.path}`;
        const isExpanded = expandedEndpoints.has(key);

        return (
          <div key={key} className="border rounded-lg overflow-hidden">
            {/* Header */}
            <button
              onClick={() => toggleEndpoint(key)}
              className="w-full flex items-center gap-3 p-4 hover:bg-muted/50 transition-colors"
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 flex-shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 flex-shrink-0" />
              )}
              <Badge
                variant="outline"
                className={`${getMethodColor(endpoint.method)} font-mono text-xs px-2 py-0.5`}
              >
                {endpoint.method}
              </Badge>
              <code className="text-sm font-mono flex-1 text-left">
                {endpoint.path}
              </code>
              <Badge variant="secondary" className="text-xs">
                {endpoint.scope}
              </Badge>
            </button>

            {/* Expanded Content */}
            {isExpanded && (
              <div className="border-t p-4 space-y-4 bg-muted/20">
                <p className="text-sm text-muted-foreground">{endpoint.description}</p>

                {/* Parameters */}
                {endpoint.parameters && endpoint.parameters.length > 0 && (
                  <div>
                    <h5 className="text-sm font-semibold mb-2">Path Parameters</h5>
                    <div className="space-y-2">
                      {endpoint.parameters.map((param) => (
                        <div key={param.name} className="flex items-start gap-2 text-sm">
                          <code className="bg-muted px-2 py-0.5 rounded text-xs">
                            {param.name}
                          </code>
                          <span className="text-muted-foreground">
                            {param.type}
                            {param.required && (
                              <Badge variant="destructive" className="ml-2 text-xs">
                                required
                              </Badge>
                            )}
                          </span>
                          <span className="text-muted-foreground">- {param.description}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Request Body */}
                {endpoint.requestBody && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h5 className="text-sm font-semibold">Request Body</h5>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyCode(endpoint.requestBody!, `req-${key}`)}
                      >
                        {copiedCode === `req-${key}` ? (
                          <Check className="h-3 w-3" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                    <pre className="bg-muted p-3 rounded text-xs overflow-x-auto">
                      <code>{endpoint.requestBody}</code>
                    </pre>
                  </div>
                )}

                {/* Response Body */}
                {endpoint.responseBody && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h5 className="text-sm font-semibold">Response (200 OK)</h5>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyCode(endpoint.responseBody!, `res-${key}`)}
                      >
                        {copiedCode === `res-${key}` ? (
                          <Check className="h-3 w-3" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                    <pre className="bg-muted p-3 rounded text-xs overflow-x-auto">
                      <code>{endpoint.responseBody}</code>
                    </pre>
                  </div>
                )}

                {/* cURL Example */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h5 className="text-sm font-semibold">cURL Example</h5>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        const curlCmd = `curl -X ${endpoint.method} ${apiUrl}${endpoint.path.replace('{id}', 'YOUR_ID')} \\
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"${
                          endpoint.requestBody
                            ? ` \\
  -H "Content-Type: application/json" \\
  -d '${endpoint.requestBody.replace(/\n/g, '')}'`
                            : ''
                        }`;
                        copyCode(curlCmd, `curl-${key}`);
                      }}
                    >
                      {copiedCode === `curl-${key}` ? (
                        <Check className="h-3 w-3" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                  <pre className="bg-muted p-3 rounded text-xs overflow-x-auto">
                    <code>
                      {`curl -X ${endpoint.method} ${apiUrl}${endpoint.path.replace('{id}', 'YOUR_ID')} \\
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"${
                        endpoint.requestBody
                          ? ` \\
  -H "Content-Type: application/json" \\
  -d '${endpoint.requestBody.replace(/\n/g, '')}'`
                          : ''
                      }`}
                    </code>
                  </pre>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
