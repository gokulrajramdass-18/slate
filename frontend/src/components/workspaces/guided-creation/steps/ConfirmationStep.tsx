/**
 * Confirmation Step
 *
 * Final review and confirmation before creating the workspace.
 */

'use client';

import { useGuidedCreationStore } from '@/lib/stores/guided-creation-store';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { CheckCircle, Target, Database, Wrench, Bot, Users, FileText } from 'lucide-react';

export function ConfirmationStep() {
  const {
    workspaceName,
    goal,
    analysis,
    selectedResources,
    discoveredResources,
    generatedPlan,
    confirmed,
    setWorkspaceName,
    setConfirmed,
  } = useGuidedCreationStore();

  // Get selected resource details
  const selectedSources = discoveredResources.sources.filter((s) =>
    selectedResources.source_ids.includes(s.id)
  );
  const selectedTools = discoveredResources.tools.filter((t) =>
    selectedResources.tool_ids.includes(t.id)
  );
  const selectedAgents = discoveredResources.agents.filter((a) =>
    selectedResources.agent_ids.includes(a.id)
  );
  const selectedTeams = discoveredResources.teams.filter((t) =>
    selectedResources.team_ids.includes(t.id)
  );

  const totalTasks = generatedPlan?.phases.reduce(
    (acc, phase) => acc + phase.tasks.length,
    0
  ) || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="p-3 bg-primary/10 rounded-lg">
          <CheckCircle className="h-6 w-6 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold mb-2">Ready to Create</h2>
          <p className="text-muted-foreground">
            Review your workspace configuration and give it a name. Once confirmed, we'll create
            your workspace with all selected resources and begin executing the plan.
          </p>
        </div>
      </div>

      {/* Workspace Name */}
      <Card className="border-primary/20">
        <CardContent className="pt-6">
          <div className="space-y-2">
            <Label htmlFor="workspace-name">Workspace Name *</Label>
            <Input
              id="workspace-name"
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
              placeholder="e.g., Customer Feedback Analysis Q1 2026"
              className="text-lg font-medium"
            />
            <p className="text-xs text-muted-foreground">
              Choose a descriptive name that reflects your goal
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Summary */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Goal */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Target className="h-4 w-4" />
              Goal
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{goal}</p>
            {analysis && (
              <div className="flex gap-2 mt-3">
                <Badge variant="outline" className="text-xs">
                  {analysis.domain}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {analysis.complexity}
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Plan */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Execution Plan
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Phases:</span>
                <span className="font-medium">{generatedPlan?.phases.length || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tasks:</span>
                <span className="font-medium">{totalTasks}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Estimated Time:</span>
                <span className="font-medium">
                  {generatedPlan?.estimated_total_duration
                    ? `${Math.round(generatedPlan.estimated_total_duration / 60)}h`
                    : '0h'}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Resources */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Selected Resources</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Sources */}
          {selectedSources.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Database className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">
                  Data Sources ({selectedSources.length})
                </span>
              </div>
              <div className="flex flex-wrap gap-2 ml-6">
                {selectedSources.map((source) => (
                  <Badge key={source.id} variant="secondary" className="text-xs">
                    {source.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {selectedSources.length > 0 && selectedTools.length > 0 && (
            <Separator />
          )}

          {/* Tools */}
          {selectedTools.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Wrench className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">
                  Tools ({selectedTools.length})
                </span>
              </div>
              <div className="flex flex-wrap gap-2 ml-6">
                {selectedTools.map((tool) => (
                  <Badge key={tool.id} variant="secondary" className="text-xs">
                    {tool.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {selectedTools.length > 0 && selectedAgents.length > 0 && <Separator />}

          {/* Agents */}
          {selectedAgents.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Bot className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">
                  Agents ({selectedAgents.length})
                </span>
              </div>
              <div className="flex flex-wrap gap-2 ml-6">
                {selectedAgents.map((agent) => (
                  <Badge key={agent.id} variant="secondary" className="text-xs">
                    {agent.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {selectedAgents.length > 0 && selectedTeams.length > 0 && <Separator />}

          {/* Teams */}
          {selectedTeams.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Users className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">
                  Teams ({selectedTeams.length})
                </span>
              </div>
              <div className="flex flex-wrap gap-2 ml-6">
                {selectedTeams.map((team) => (
                  <Badge key={team.id} variant="secondary" className="text-xs">
                    {team.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confirmation Checkbox */}
      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <Checkbox
              id="confirm"
              checked={confirmed}
              onCheckedChange={(checked) => setConfirmed(checked as boolean)}
            />
            <div className="flex-1">
              <Label
                htmlFor="confirm"
                className="text-sm font-medium cursor-pointer"
              >
                I confirm that I want to create this workspace
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                The workspace will be created with the above configuration. You can modify
                resources and settings after creation.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
