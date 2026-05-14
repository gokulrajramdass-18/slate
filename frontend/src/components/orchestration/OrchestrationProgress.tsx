/**
 * Orchestration Progress
 *
 * Shows real-time progress of autonomous orchestration with event timeline.
 */

'use client';

import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CheckCircle2, Circle, Loader2, XCircle, ExternalLink } from 'lucide-react';
import { OrchestrationOutput } from './OrchestrationOutput';
import type { OrchestrationEvent, OrchestrationStatus } from '@/lib/api/orchestration';

interface OrchestrationProgressProps {
  status: OrchestrationStatus;
  events: OrchestrationEvent[];
}

const eventTypeLabels: Record<string, string> = {
  'orchestration.started': 'Orchestration Started',
  'analysis.completed': 'Goal Analysis Complete',
  'decision.made': 'Decision Made',
  'team.spawning': 'Spawning Team',
  'agent.spawned': 'Agent Spawned',
  'task.assigned': 'Task Assigned',
  'task.started': 'Task Started',
  'task.progress': 'Task Progress',
  'task.completed': 'Task Completed',
  'handover.initiated': 'Handover Initiated',
  'handover.completed': 'Handover Completed',
  'synthesis.started': 'Synthesis Started',
  'orchestration.completed': 'Orchestration Complete',
  'orchestration.error': 'Error Occurred',
};

const eventTypeColors: Record<string, string> = {
  'orchestration.started': 'bg-blue-500',
  'analysis.completed': 'bg-green-500',
  'decision.made': 'bg-purple-500',
  'team.spawning': 'bg-amber-500',
  'agent.spawned': 'bg-green-500',
  'task.assigned': 'bg-blue-500',
  'task.started': 'bg-blue-500',
  'task.progress': 'bg-blue-400',
  'task.completed': 'bg-green-500',
  'handover.initiated': 'bg-purple-500',
  'handover.completed': 'bg-purple-600',
  'synthesis.started': 'bg-amber-500',
  'orchestration.completed': 'bg-green-600',
  'orchestration.error': 'bg-red-500',
};

const statusLabels: Record<string, string> = {
  starting: 'Starting',
  analyzing: 'Analyzing Goal',
  analyzing_complete: 'Analysis Complete',
  decision_made: 'Decision Made',
  team_spawned: 'Team Spawned',
  plan_generated: 'Plan Generated',
  team_execution_complete: 'Execution Complete',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

const statusColors: Record<string, string> = {
  starting: 'secondary',
  analyzing: 'secondary',
  analyzing_complete: 'default',
  decision_made: 'default',
  team_spawned: 'default',
  plan_generated: 'default',
  team_execution_complete: 'default',
  completed: 'default',
  failed: 'destructive',
  cancelled: 'secondary',
};

function getEventIcon(eventType: string, index: number, isLatest: boolean) {
  if (eventType === 'orchestration.error') {
    return <XCircle className="h-5 w-5 text-red-500" />;
  }

  if (eventType === 'orchestration.completed') {
    return <CheckCircle2 className="h-5 w-5 text-green-600" />;
  }

  if (isLatest) {
    return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
  }

  return <CheckCircle2 className="h-5 w-5 text-green-500" />;
}

export function OrchestrationProgress({
  status,
  events,
}: OrchestrationProgressProps) {
  const progressPercentage = Math.round(status.progress * 100);

  // Extract key information from events
  const startEvent = events.find(e => e.type === 'orchestration.started');
  const decisionEvent = events.find(e => e.type === 'decision.made');
  const completionEvent = events.find(e => e.type === 'orchestration.completed');
  const errorEvent = events.find(e => e.type === 'orchestration.error');

  // Count spawned agents
  const spawnedAgents = events.filter(e => e.type === 'agent.spawned');
  const completedTasks = events.filter(e => e.type === 'task.completed');
  const totalTasks = events.filter(e => e.type === 'task.assigned').length;

  // Get execution result
  const executionResult = completionEvent?.data?.result || errorEvent?.data?.error;

  // Get agent count from decision event if spawned agents not found
  const agentCount = spawnedAgents.length > 0
    ? spawnedAgents.length
    : (decisionEvent?.data?.team_size || 0);

  console.log('OrchestrationProgress - Debug:', {
    totalEvents: events.length,
    spawnedAgentsEvents: spawnedAgents.length,
    decisionTeamSize: decisionEvent?.data?.team_size,
    finalAgentCount: agentCount,
    eventTypes: events.map(e => e.type),
  });

  return (
    <div className="space-y-4">
      {/* Execution Results - Show at top when completed */}
      {(status.status === 'completed' || status.status === 'failed') && executionResult && (
        <OrchestrationOutput
          result={executionResult}
          status={status.status}
          spawnedAgents={agentCount}
          completedTasks={completedTasks.length}
          totalTasks={totalTasks}
          duration={(() => {
            const start = new Date(status.started_at).getTime();
            const end = new Date(status.updated_at).getTime();
            const seconds = Math.floor((end - start) / 1000);
            return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
          })()}
        />
      )}

      {/* Technical Details */}
      <Card>
        <CardHeader>
          <CardTitle>Technical Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Orchestration Mode */}
          {decisionEvent && (
            <div className="space-y-2">
              <div className="text-sm font-medium">Orchestration Decision:</div>
              <div className="bg-muted/50 rounded-lg p-3 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Mode Selected:</span>
                  <Badge variant="outline" className="capitalize">
                    {decisionEvent.data.orchestration_mode}
                  </Badge>
                </div>
                {decisionEvent.data.team_size && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Team Size:</span>
                    <span className="font-medium">{decisionEvent.data.team_size} agents</span>
                  </div>
                )}
                {decisionEvent.data.reasoning && (
                  <div className="text-xs text-muted-foreground pt-2 border-t">
                    <strong>Reasoning:</strong> {decisionEvent.data.reasoning}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Spawned Agents */}
          {(spawnedAgents.length > 0 || decisionEvent?.data?.team_size) && (
            <div className="space-y-2">
              <div className="text-sm font-medium">
                Agent Team ({agentCount}):
              </div>
              {spawnedAgents.length > 0 ? (
                <div className="grid gap-2">
                  {spawnedAgents.map((agent, idx) => (
                    <div key={idx} className="bg-muted/50 rounded-lg p-3 text-sm">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{agent.data.agent_name || `Agent ${idx + 1}`}</div>
                          <div className="text-xs text-muted-foreground">
                            Role: {agent.data.agent_role}
                          </div>
                        </div>
                        {agent.data.agent_id && (
                          <code className="text-xs bg-muted px-2 py-1 rounded">
                            {agent.data.agent_id.slice(0, 8)}
                          </code>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-muted/50 rounded-lg p-3 text-sm text-muted-foreground">
                  {agentCount} agents spawned (details not available in event stream)
                </div>
              )}
            </div>
          )}

          {/* Team ID */}
          {status.team_id && (
            <div className="flex justify-between items-center text-sm pt-2 border-t">
              <span className="text-muted-foreground">Team ID:</span>
              <Link
                href={`/agents/teams/${status.team_id}/execute`}
                className="group flex items-center gap-1.5 hover:opacity-80 transition-opacity"
              >
                <code className="text-xs bg-blue-50 dark:bg-blue-950/30 text-blue-600 dark:text-blue-400 px-2 py-1 rounded font-mono border border-blue-200 dark:border-blue-800 group-hover:border-blue-400 dark:group-hover:border-blue-600 transition-colors">
                  {status.team_id.slice(0, 8)}
                </code>
                <ExternalLink className="h-3 w-3 text-blue-600 dark:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            </div>
          )}

          {/* Orchestration ID */}
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">Orchestration ID:</span>
            <code className="text-xs bg-muted px-2 py-1 rounded font-mono">
              {status.orchestration_id}
            </code>
          </div>
        </CardContent>
      </Card>

      {/* Status Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Orchestration Status</span>
            <Badge variant={statusColors[status.status] as any}>
              {statusLabels[status.status] || status.status}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Progress</span>
              <span className="font-medium">{progressPercentage}%</span>
            </div>
            <Progress value={progressPercentage} className="h-2" />
          </div>

          {/* Current Phase */}
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">Current Phase:</span>
            <span className="font-medium capitalize">
              {status.current_phase.replace(/_/g, ' ')}
            </span>
          </div>

          {/* Mode & Team */}
          {status.orchestration_mode && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">Mode:</span>
              <Badge variant="outline" className="capitalize">
                {status.orchestration_mode}
              </Badge>
            </div>
          )}

          {status.team_id && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">Team ID:</span>
              <Link
                href={`/agents/teams/${status.team_id}/execute`}
                className="group flex items-center gap-1.5 hover:opacity-80 transition-opacity"
              >
                <code className="text-xs bg-blue-50 dark:bg-blue-950/30 text-blue-600 dark:text-blue-400 px-2 py-1 rounded font-mono border border-blue-200 dark:border-blue-800 group-hover:border-blue-400 dark:group-hover:border-blue-600 transition-colors">
                  {status.team_id.slice(0, 8)}
                </code>
                <ExternalLink className="h-3 w-3 text-blue-600 dark:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            </div>
          )}

          {/* Timing */}
          <div className="text-xs text-muted-foreground pt-2 border-t">
            <div>Started: {new Date(status.started_at).toLocaleString()}</div>
            <div>Updated: {new Date(status.updated_at).toLocaleString()}</div>
          </div>
        </CardContent>
      </Card>

      {/* Event Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Event Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px] pr-4">
            <div className="space-y-4">
              {events.length === 0 && (
                <div className="text-center text-muted-foreground py-8">
                  No events yet...
                </div>
              )}

              {events.map((event, index) => {
                const isLatest = index === events.length - 1 && status.status !== 'completed';

                return (
                  <div key={`${event.type}-${index}`} className="flex gap-4">
                    {/* Icon */}
                    <div className="flex-shrink-0 mt-1">
                      {getEventIcon(event.type, index, isLatest)}
                    </div>

                    {/* Content */}
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">
                          {eventTypeLabels[event.type] || event.type}
                        </span>
                        <span
                          className={`h-2 w-2 rounded-full ${
                            eventTypeColors[event.type] || 'bg-gray-500'
                          }`}
                        />
                      </div>

                      {/* Event-specific details */}
                      {event.data && Object.keys(event.data).length > 0 && (
                        <div className="text-xs text-muted-foreground space-y-1">
                          {event.type === 'decision.made' && (
                            <>
                              <div>Mode: {event.data.orchestration_mode}</div>
                              {event.data.team_size && (
                                <div>Team Size: {event.data.team_size} agents</div>
                              )}
                            </>
                          )}

                          {event.type === 'agent.spawned' && (
                            <>
                              <div>Agent: {event.data.agent_name}</div>
                              <div>Role: {event.data.agent_role}</div>
                            </>
                          )}

                          {event.type === 'task.assigned' && (
                            <>
                              <div>Task: {event.data.task_description}</div>
                              {event.data.agent_name && (
                                <div>Assigned to: {event.data.agent_name}</div>
                              )}
                            </>
                          )}

                          {event.type === 'handover.completed' && (
                            <>
                              <div>
                                From: {event.data.from_agent} → To: {event.data.to_agent}
                              </div>
                            </>
                          )}
                        </div>
                      )}

                      <div className="text-xs text-muted-foreground">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
