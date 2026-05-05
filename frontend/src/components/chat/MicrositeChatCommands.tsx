"use client";

import { useState, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Globe,
  Loader2,
  ExternalLink,
  Pencil,
} from "lucide-react";
import { toast } from "sonner";
import { useGenerateMicrosite, useNotebooks, useNotebookSources, useMicrositeTemplates } from "@/lib/hooks/use-api";

const MICROSITE_PATTERNS = [
  /create\s+(?:a\s+)?(?:new\s+)?(?:blog|landing\s*page|portfolio|documentation|report)\s+(?:micro)?site/i,
  /generate\s+(?:a\s+)?(?:new\s+)?(?:blog|landing\s*page|portfolio|documentation|report)\s+(?:micro)?site/i,
  /make\s+(?:a\s+)?(?:new\s+)?(?:blog|landing\s*page|portfolio|documentation|report)\s+(?:micro)?site/i,
  /create\s+(?:a\s+)?(?:new\s+)?(?:micro)?site\s+from/i,
  /generate\s+(?:a\s+)?(?:micro)?site\s+from/i,
  /build\s+(?:a\s+)?(?:new\s+)?(?:micro)?site/i,
];

const TEMPLATE_MAP: Record<string, string> = {
  blog: "blog",
  "landing page": "landing",
  "landing": "landing",
  portfolio: "portfolio",
  documentation: "documentation",
  docs: "documentation",
  report: "report",
};

export function detectMicrositeIntent(message: string): {
  isMatch: boolean;
  templateHint?: string;
  workspaceHint?: string;
} {
  const lower = message.toLowerCase();

  const isMatch = MICROSITE_PATTERNS.some((p) => p.test(lower));
  if (!isMatch) {
    return { isMatch: false };
  }

  let templateHint: string | undefined;
  for (const [keyword, template] of Object.entries(TEMPLATE_MAP)) {
    if (lower.includes(keyword)) {
      templateHint = template;
      break;
    }
  }

  let workspaceHint: string | undefined;
  const fromMatch = lower.match(/from\s+(?:my\s+)?["']?(.+?)["']?\s*(?:workspace|notebook|$)/i);
  if (fromMatch) {
    workspaceHint = fromMatch[1].trim();
  }

  return { isMatch, templateHint, workspaceHint };
}

interface MicrositeChatCommandsProps {
  message: string;
  micrositeId: string;
  onGenerationComplete?: (previewUrl: string) => void;
  onEditRequest?: (micrositeId: string) => void;
}

export function MicrositeChatCommands({
  message,
  micrositeId,
  onGenerationComplete,
  onEditRequest,
}: MicrositeChatCommandsProps) {
  const intent = useMemo(() => detectMicrositeIntent(message), [message]);
  const [selectedNotebookId, setSelectedNotebookId] = useState<string>("");
  const [step, setStep] = useState<"select-workspace" | "confirm" | "generating" | "done">(
    "select-workspace"
  );
  const [result, setResult] = useState<{ previewUrl: string; version: number } | null>(null);

  const { data: notebooks } = useNotebooks();
  const { data: sources } = useNotebookSources(selectedNotebookId);
  const { data: templates } = useMicrositeTemplates();
  const generateMutation = useGenerateMicrosite();

  const matchedTemplate = useMemo(() => {
    if (!intent.templateHint || !templates) return templates?.[0];
    return templates.find((t) => t.name === intent.templateHint) || templates[0];
  }, [intent.templateHint, templates]);

  const matchedNotebook = useMemo(() => {
    if (!intent.workspaceHint || !notebooks) return null;
    return notebooks.find((n) =>
      n.name.toLowerCase().includes(intent.workspaceHint!.toLowerCase())
    );
  }, [intent.workspaceHint, notebooks]);

  const handleSelectNotebook = useCallback(
    (notebookId: string) => {
      setSelectedNotebookId(notebookId);
      setStep("confirm");
    },
    []
  );

  const handleGenerate = useCallback(async () => {
    if (!matchedTemplate || !sources?.length) return;

    setStep("generating");
    try {
      const response = await generateMutation.mutateAsync({
        micrositeId,
        request: {
          template_id: matchedTemplate.id,
          source_ids: sources.map((s) => s.id),
        },
      });
      setResult({
        previewUrl: response.preview_url,
        version: response.version,
      });
      setStep("done");
      onGenerationComplete?.(response.preview_url);
    } catch (error: any) {
      toast.error("Generation failed");
      setStep("confirm");
    }
  }, [matchedTemplate, sources, micrositeId, generateMutation, onGenerationComplete]);

  if (!intent.isMatch) return null;

  return (
    <Card className="mt-2">
      <CardContent className="p-4 space-y-3">
        {step === "select-workspace" && (
          <>
            <p className="text-sm">
              I can create a{" "}
              <Badge variant="secondary" className="capitalize">
                {intent.templateHint || "microsite"}
              </Badge>{" "}
              for you. Which workspace should I use?
            </p>
            {matchedNotebook ? (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  Found matching workspace:
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleSelectNotebook(matchedNotebook.id)}
                >
                  {matchedNotebook.name}
                </Button>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {notebooks?.slice(0, 5).map((nb) => (
                  <Button
                    key={nb.id}
                    variant="outline"
                    size="sm"
                    onClick={() => handleSelectNotebook(nb.id)}
                  >
                    {nb.name}
                  </Button>
                ))}
              </div>
            )}
          </>
        )}

        {step === "confirm" && (
          <>
            <p className="text-sm">
              Ready to generate using{" "}
              <strong>{sources?.length || 0} sources</strong> with the{" "}
              <Badge variant="secondary" className="capitalize">
                {matchedTemplate?.display_name || "default"}
              </Badge>{" "}
              template. Proceed?
            </p>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleGenerate}>
                <Globe className="w-4 h-4 mr-2" />
                Generate
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setStep("select-workspace")}
              >
                Change Workspace
              </Button>
            </div>
          </>
        )}

        {step === "generating" && (
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 animate-spin text-primary" />
            <p className="text-sm">Generating your microsite...</p>
          </div>
        )}

        {step === "done" && result && (
          <>
            <p className="text-sm">
              Your microsite has been created (version {result.version})!
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => window.open(result.previewUrl, "_blank")}
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                Preview
              </Button>
              <Button
                size="sm"
                onClick={() => onEditRequest?.(micrositeId)}
              >
                <Pencil className="w-4 h-4 mr-2" />
                Edit
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
