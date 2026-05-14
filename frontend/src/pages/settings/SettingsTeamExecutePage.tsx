import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { AgentTeamViewer } from "@/components/agents/AgentTeamViewer";

export default function SettingsTeamExecutePage() {
  const params = useParams();
  const navigate = useNavigate();
  const teamId = params?.teamId as string;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Back Button */}
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/settings/agents")}
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
