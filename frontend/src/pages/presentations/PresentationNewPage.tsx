/**
 * Presentation Generator Page
 *
 * Test page for PowerPoint generation wizard.
 */

import { PresentationGenerator } from "@/components/presentations/PresentationGenerator";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft, X } from "lucide-react";

export default function PresentationNewPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const notebookId = searchParams.get("notebook_id") || undefined;

  const handleClose = () => {
    if (notebookId) {
      // Go back to the workspace
      navigate(`/workspaces/${notebookId}`);
    } else {
      // Go back to previous page
      navigate(-1);
    }
  };

  return (
    <div className="container mx-auto py-8">
      {/* Header with close button */}
      <div className="flex items-center justify-between mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClose}
          className="gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Workspace
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleClose}
          className="rounded-full"
        >
          <X className="h-5 w-5" />
        </Button>
      </div>

      <PresentationGenerator
        notebookId={notebookId}
        onComplete={(presentationId) => {
          console.log("Presentation created:", presentationId);
          // Could navigate to a dedicated presentation page
          // navigate(`/presentations/${presentationId}`);
        }}
      />
    </div>
  );
}
