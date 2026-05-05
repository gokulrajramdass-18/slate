"use client";

import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { AgentTeamViewer } from "@/components/agents/AgentTeamViewer";

export default function TeamExecutePage() {
  const params = useParams();
  const router = useRouter();
  const teamId = params?.teamId as string;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Back Button */}
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push("/settings/agents")}
          className="mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Teams
        </Button>
      </div>

      {/* Execution Interface */}
      {teamId && <AgentTeamViewer teamId={teamId} />}
    </div>
  );
}
