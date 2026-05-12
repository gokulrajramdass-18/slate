/**
 * Chat Integration for Presentation Detection
 *
 * Uses AI to detect presentation generation requests in natural language chat
 * and provides inline UI for quick generation.
 */

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles, Presentation, ChevronDown, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { presentationApi } from "@/lib/api/presentations";
import { SlidePreview } from "@/components/presentations/SlidePreview";
import { cn } from "@/lib/utils";

interface PresentationIntent {
  isMatch: boolean;
  templateHint?: string;
  slideCount?: number;
  topic?: string;
}

/**
 * Detect if message contains presentation generation intent using AI
 */
export async function detectPresentationIntentWithAI(message: string): Promise<PresentationIntent> {
  try {
    const response = await fetch('http://localhost:5055/api/presentations/detect-intent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });

    if (!response.ok) {
      return { isMatch: false };
    }

    return await response.json();
  } catch (error) {
    console.error('[PresentationIntent] AI detection failed:', error);
    return { isMatch: false };
  }
}

/**
 * Fallback regex-based detection (used synchronously for initial render)
 */
export function detectPresentationIntent(message: string): PresentationIntent {
  const presentationKeywords = [
    'presentation', 'powerpoint', 'slides', 'slide deck',
    'ppt', 'pptx', 'power point', 'pitch deck'
  ];

  const actionWords = [
    'create', 'generate', 'make', 'build', 'prepare', 'need'
  ];

  const messageLower = message.toLowerCase();

  // Quick check: does it mention presentation-related keywords?
  const hasPresentationKeyword = presentationKeywords.some(keyword =>
    messageLower.includes(keyword)
  );

  // And does it have an action word?
  const hasActionWord = actionWords.some(action =>
    messageLower.includes(action)
  );

  const isMatch = hasPresentationKeyword && hasActionWord;

  if (!isMatch) {
    return { isMatch: false };
  }

  // Extract hints
  const slideCountMatch = message.match(/(\d+)\s+slides?/i);
  const slideCount = slideCountMatch ? parseInt(slideCountMatch[1]) : undefined;

  return {
    isMatch: true,
    slideCount,
    topic: message
  };
}

interface PresentationChatCommandsProps {
  message: string;
  notebookId?: string;
  onGenerationComplete?: (presentationId: string) => void;
}

export function PresentationChatCommands({
  message,
  notebookId,
  onGenerationComplete,
}: PresentationChatCommandsProps) {
  const router = useRouter();

  // Start with quick regex detection
  const quickIntent = detectPresentationIntent(message);
  const [aiIntent, setAiIntent] = useState<PresentationIntent | null>(null);
  const [isCheckingIntent, setIsCheckingIntent] = useState(false);

  // Use AI to verify intent on mount
  useEffect(() => {
    if (quickIntent.isMatch) {
      setIsCheckingIntent(true);
      detectPresentationIntentWithAI(message)
        .then(intent => {
          console.log('[PresentationIntent] AI verification:', intent);
          setAiIntent(intent);
        })
        .finally(() => setIsCheckingIntent(false));
    }
  }, [message, quickIntent.isMatch]);

  // Use AI intent if available, otherwise use quick intent
  const intent = aiIntent || quickIntent;

  const [step, setStep] = useState<
    "confirm" | "select-template" | "configure" | "generating" | "complete"
  >("confirm");
  const [selectedTemplate, setSelectedTemplate] = useState<string>(
    intent.templateHint || "business-pitch"
  );
  const [title, setTitle] = useState(intent.topic || "Presentation");
  const [slideCount, setSlideCount] = useState(intent.slideCount || 10);
  const [presentationId, setPresentationId] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  // Fetch templates
  const { data: templates } = useQuery({
    queryKey: ["presentation-templates"],
    queryFn: () => presentationApi.listTemplates(),
    enabled: step === "select-template",
  });

  // Generate mutation
  const generateMutation = useMutation({
    mutationFn: async () => {
      // Create presentation record first
      const createResponse = await presentationApi.create({
        notebook_id: notebookId,
        template_id: selectedTemplate,
        title: title || "Chat Presentation",
        description: message,
      });

      const newId = createResponse.presentation_id;
      setPresentationId(newId);

      // Generate slides
      await presentationApi.generate(newId, {
        template_id: selectedTemplate,
        source_ids: [], // TODO: Get active sources from workspace
        notebook_id: notebookId,
        user_prompt: message,
        target_slide_count: slideCount,
      });

      return newId;
    },
    onSuccess: (id) => {
      setStep("complete");
      setShowPreview(true); // Automatically open preview canvas
      onGenerationComplete?.(id);
    },
    onError: (error) => {
      console.error("Generation failed:", error);
      toast.error("Failed to generate presentation");
    },
  });

  const handleGenerate = () => {
    // If no title, go to configure step
    if (!title || title.trim() === "") {
      setStep("configure");
      return;
    }

    setStep("generating");
    generateMutation.mutate();
  };

  if (!intent.isMatch) {
    return null;
  }

  return (
    <Card className="my-4 border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          <div className="bg-primary/10 p-2 rounded-lg">
            <Presentation className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <CardTitle className="text-base">Create Presentation</CardTitle>
            <CardDescription className="mt-1">
              {step === "confirm" &&
                `Generate a ${slideCount}-slide ${
                  templates?.find((t) => t.id === selectedTemplate)?.name ||
                  "presentation"
                }`}
              {step === "select-template" && "Choose a template"}
              {step === "configure" && "Configure presentation details"}
              {step === "generating" && "Generating your presentation..."}
              {step === "complete" && "Presentation ready!"}
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {/* Confirm Step */}
        {step === "confirm" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>Template:</span>
              <span className="font-medium text-foreground">
                {templates?.find((t) => t.id === selectedTemplate)?.name ||
                  "Business Pitch"}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setStep("select-template")}
                className="h-6 px-2"
              >
                Change
              </Button>
            </div>

            <div className="flex gap-2">
              <Button
                onClick={handleGenerate}
                className="gap-2"
                disabled={generateMutation.isPending}
              >
                <Sparkles className="h-4 w-4" />
                Generate Presentation
              </Button>
              <Button
                variant="outline"
                onClick={() => router.push("/presentations/new")}
              >
                Full Editor
              </Button>
            </div>
          </div>
        )}

        {/* Template Selection */}
        {step === "select-template" && (
          <div className="space-y-3">
            <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {templates?.map((template) => (
                  <SelectItem key={template.id} value={template.id}>
                    {template.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="flex gap-2">
              <Button onClick={() => setStep("confirm")} size="sm">
                Continue
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setStep("confirm")}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Configure Step */}
        {step === "configure" && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="chat-title" className="text-sm">
                Presentation Title
              </Label>
              <Input
                id="chat-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter title..."
                className="mt-1.5"
              />
            </div>

            <div>
              <Label htmlFor="chat-slides" className="text-sm">
                Number of Slides
              </Label>
              <Select
                value={slideCount.toString()}
                onValueChange={(v) => setSlideCount(parseInt(v))}
              >
                <SelectTrigger id="chat-slides" className="mt-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[5, 8, 10, 12, 15, 20].map((count) => (
                    <SelectItem key={count} value={count.toString()}>
                      {count} slides
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex gap-2">
              <Button onClick={handleGenerate} size="sm" disabled={!title}>
                Generate
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setStep("confirm")}
              >
                Back
              </Button>
            </div>
          </div>
        )}

        {/* Generating Step */}
        {step === "generating" && (
          <div className="flex flex-col items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
            <p className="text-sm text-muted-foreground">
              Creating {slideCount} slides...
            </p>
          </div>
        )}

        {/* Complete Step */}
        {step === "complete" && presentationId && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Your presentation has been generated successfully!
            </p>
            <div className="flex gap-2">
              <Button
                onClick={() => setShowPreview(true)}
                className="gap-2"
              >
                <Presentation className="h-4 w-4" />
                Open Preview
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  presentationApi.download(
                    presentationId,
                    title || "presentation"
                  )
                }
              >
                Download PPTX
              </Button>
            </div>
          </div>
        )}
      </CardContent>

      {/* Fullscreen Preview Canvas */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="max-w-[95vw] w-[95vw] max-h-[95vh] h-[95vh] p-0 gap-0 overflow-hidden">
          <DialogTitle className="sr-only">Presentation Preview</DialogTitle>
          {presentationId && (
            <SlidePreview
              presentationId={presentationId}
              onClose={() => setShowPreview(false)}
            />
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}
