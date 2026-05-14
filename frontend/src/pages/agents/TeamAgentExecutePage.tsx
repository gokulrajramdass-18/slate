import { useParams } from "react-router-dom";
import { AgentTeamViewer } from "@/components/agents/AgentTeamViewer";

export default function TeamAgentExecutePage() {
  const { id: teamId } = useParams<{ id: string }>();

  return (
    <div className="container mx-auto py-6">
      <AgentTeamViewer teamId={teamId as string} />
    </div>
  );
}
