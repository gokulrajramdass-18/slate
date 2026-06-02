"use client";

/**
 * Workflow Evaluations Page
 *
 * Sibling to /workflows/:id/settings, /schedules, /executions. Hosts the
 * WorkflowEvaluationTab so that authoring evaluations for a workflow has the
 * same chrome as the rest of the workflow sub-nav.
 */

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "@/lib/routing/navigation";
import { workflowsApi } from "@/lib/api/workflows";
import { Button } from "@/components/ui/button";
import { ArrowLeft, BarChart3 } from "lucide-react";
import { WorkflowEvaluationTab } from "@/components/workflows/WorkflowEvaluationTab";

export default function WorkflowEvaluationsPage() {
  const router = useRouter();
  const params = useParams();
  const workflowId = (params?.id as string) || "";

  const { data: workflow } = useQuery({
    queryKey: ["workflow", workflowId],
    queryFn: () => workflowsApi.get(workflowId),
    enabled: !!workflowId,
  });

  if (!workflowId) {
    return null;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push(`/workflows/${workflowId}`)}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <BarChart3 className="w-7 h-7" />
            Evaluations
          </h1>
          {workflow && (
            <p className="text-muted-foreground mt-1">{workflow.name}</p>
          )}
        </div>
      </div>

      <WorkflowEvaluationTab
        workflowId={workflowId}
        workflowName={workflow?.name || "Workflow"}
      />
    </div>
  );
}
