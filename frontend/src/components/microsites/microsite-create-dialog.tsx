"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { MicrositeGenerator } from "./MicrositeGenerator";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api/client";

interface MicrositeCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  notebookId: string;
  notebookTitle: string;
}

export function MicrositeCreateDialog({
  open,
  onOpenChange,
  notebookId,
  notebookTitle,
}: MicrositeCreateDialogProps) {
  const router = useRouter();
  const [micrositeId, setMicrositeId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const handleCreateMicrosite = async () => {
    try {
      setCreating(true);

      // Step 1: Create empty microsite
      const { data } = await apiClient.post("/microsites", {
        notebook_id: notebookId,
        title: `${notebookTitle} - Microsite`,
        description: `AI-generated microsite from ${notebookTitle}`,
        theme: "light",
      });

      setMicrositeId(data.id);
      toast.success("Microsite created! Now let's generate content...");
    } catch (error: any) {
      console.error("Failed to create microsite:", error);
      toast.error(error.message || "Failed to create microsite");
      setCreating(false);
    }
  };

  const handleComplete = (completedMicrositeId: string) => {
    toast.success("Microsite generated successfully!");
    onOpenChange(false);
    // Navigate to microsite preview or edit page
    router.push(`/microsites/${completedMicrositeId}`);
  };

  const handleEdit = (editMicrositeId: string, mode: "visual" | "code") => {
    onOpenChange(false);
    router.push(`/microsites/${editMicrositeId}/edit?mode=${mode}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary-600" />
            Create AI-Generated Microsite
          </DialogTitle>
          <DialogDescription>
            Generate a professional microsite from your workspace content with AI enhancement
          </DialogDescription>
        </DialogHeader>

        {!micrositeId ? (
          <div className="space-y-6 py-8">
            <div className="text-center">
              <Sparkles className="w-16 h-16 text-primary-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2">Generate Your Microsite</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-md mx-auto">
                Create a beautiful, AI-enhanced website from your workspace sources.
                Choose from multiple templates and customize with dual edit modes.
              </p>
              <Button
                size="lg"
                onClick={handleCreateMicrosite}
                disabled={creating}
                className="min-w-[200px]"
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Start Generation
                  </>
                )}
              </Button>
            </div>

            <div className="grid md:grid-cols-3 gap-4 max-w-4xl mx-auto mt-8">
              <div className="text-center p-4 border rounded-lg">
                <div className="text-2xl mb-2">🎨</div>
                <h4 className="font-semibold mb-1">Multiple Templates</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Blog, documentation, portfolio, landing page, and report themes
                </p>
              </div>
              <div className="text-center p-4 border rounded-lg">
                <div className="text-2xl mb-2">🤖</div>
                <h4 className="font-semibold mb-1">AI Enhancement</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Hybrid template + AI content generation with 4-layer guardrails
                </p>
              </div>
              <div className="text-center p-4 border rounded-lg">
                <div className="text-2xl mb-2">✏️</div>
                <h4 className="font-semibold mb-1">Dual Edit Modes</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  WYSIWYG visual editor and Monaco code editor with live preview
                </p>
              </div>
            </div>
          </div>
        ) : (
          <MicrositeGenerator
            micrositeId={micrositeId}
            initialNotebookId={notebookId}
            onComplete={handleComplete}
            onEdit={handleEdit}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
