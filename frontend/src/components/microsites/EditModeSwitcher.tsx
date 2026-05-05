"use client";

import { useState, useCallback, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Eye, Code, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { WYSIWYGEditor } from "./WYSIWYGEditor";
import { CodeEditor } from "./CodeEditor";
import { LivePreview } from "./LivePreview";
import { useMicrositeContent, useUpdateMicrositeContent } from "@/lib/hooks/use-api";
import { micrositesApi } from "@/lib/api/microsites";
import type { MicrositeContent } from "@/lib/types";

type EditMode = "visual" | "code";

interface EditModeSwitcherProps {
  micrositeId: string;
  initialMode?: EditMode;
  showPreview?: boolean;
}

export function EditModeSwitcher({
  micrositeId,
  initialMode = "visual",
  showPreview = true,
}: EditModeSwitcherProps) {
  const [mode, setMode] = useState<EditMode>(initialMode);
  const [pendingMode, setPendingMode] = useState<EditMode | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");

  const { data: content, isLoading } = useMicrositeContent(micrositeId);
  const updateMutation = useUpdateMicrositeContent();

  const sections = content?.sections || [];

  // Build combined HTML for code editor and preview
  const combinedHtml = sections
    .filter((s) => s.is_visible)
    .map((s) => s.content_html)
    .join("\n\n");

  const customCss = content?.custom_css || "";

  useEffect(() => {
    async function loadPreview() {
      try {
        const html = await micrositesApi.getPreviewHtml(micrositeId);
        setPreviewHtml(html);
      } catch {
        setPreviewHtml(combinedHtml);
      }
    }
    loadPreview();
  }, [micrositeId, combinedHtml]);

  const handleModeSwitch = useCallback(
    (newMode: string) => {
      const target = newMode as EditMode;
      if (target === mode) return;

      if (hasUnsavedChanges) {
        setPendingMode(target);
        setShowConfirm(true);
      } else {
        setMode(target);
      }
    },
    [mode, hasUnsavedChanges]
  );

  const confirmSwitch = useCallback(() => {
    if (pendingMode) {
      setMode(pendingMode);
      setPendingMode(null);
      setHasUnsavedChanges(false);
    }
    setShowConfirm(false);
  }, [pendingMode]);

  const cancelSwitch = useCallback(() => {
    setPendingMode(null);
    setShowConfirm(false);
  }, []);

  const handleWYSIWYGSave = async (
    updates: { section_id: string; content_html: string; content_json: string }[]
  ) => {
    await updateMutation.mutateAsync({
      micrositeId,
      update: {
        sections: updates.map((u) => ({
          section_id: u.section_id,
          content_html: u.content_html,
          content_json: u.content_json,
        })),
      },
    });
    setHasUnsavedChanges(false);
  };

  const handleCodeSave = async (html: string, css: string, _js: string) => {
    // For code editor, we save the full HTML as a single section update
    // The backend handles splitting into sections if needed
    await updateMutation.mutateAsync({
      micrositeId,
      update: {
        sections: sections.map((s, i) => ({
          section_id: s.section_id,
          content_html: i === 0 ? html : s.content_html,
        })),
      },
    });
    setHasUnsavedChanges(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Tabs value={mode} onValueChange={handleModeSwitch}>
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="visual" className="gap-2">
              <Eye className="w-4 h-4" />
              Visual Editor
            </TabsTrigger>
            <TabsTrigger value="code" className="gap-2">
              <Code className="w-4 h-4" />
              Code Editor
            </TabsTrigger>
          </TabsList>

          {hasUnsavedChanges && (
            <Badge variant="secondary" className="text-xs">
              Unsaved changes
            </Badge>
          )}
        </div>

        <div className={`${showPreview ? "flex gap-4" : ""}`}>
          <div className={showPreview ? "flex-1" : "w-full"}>
            <TabsContent value="visual" className="mt-0">
              <WYSIWYGEditor
                micrositeId={micrositeId}
                sections={sections}
                onSave={handleWYSIWYGSave}
                isSaving={updateMutation.isPending}
              />
            </TabsContent>

            <TabsContent value="code" className="mt-0">
              <CodeEditor
                micrositeId={micrositeId}
                initialHtml={combinedHtml}
                initialCss={customCss}
                initialJs=""
                onSave={handleCodeSave}
                isSaving={updateMutation.isPending}
              />
            </TabsContent>
          </div>

          {showPreview && mode === "visual" && (
            <div className="w-[400px] h-[600px]">
              <LivePreview
                html={previewHtml}
                previewUrl={micrositesApi.getPreviewUrl(micrositeId)}
              />
            </div>
          )}
        </div>
      </Tabs>

      {/* Unsaved Changes Confirmation */}
      <AlertDialog open={showConfirm} onOpenChange={setShowConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsaved Changes</AlertDialogTitle>
            <AlertDialogDescription>
              You have unsaved changes. Switching editors may cause some formatting
              to be lost. Do you want to switch anyway?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={cancelSwitch}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmSwitch}>
              Switch Anyway
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
