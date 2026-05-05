"use client";

import { useParams, useSearchParams } from "next/navigation";
import { AgentTeamViewer } from "@/components/agents/AgentTeamViewer";

export default function TeamExecutePage() {
  const params = useParams();
  const teamId = params.id as string;

  return (
    <div className="container mx-auto py-6">
      <AgentTeamViewer teamId={teamId} />
    </div>
  );
}
