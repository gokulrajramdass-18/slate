/**
 * Presentation Generator Wizard
 *
 * Multi-step wizard for creating PowerPoint presentations from workspace sources.
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Loader2, FileText, Sparkles, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";

// Generate UUID v4
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { presentationApi, type PresentationTemplate } from "@/lib/api/presentations";
import { SlidePreview } from "./SlidePreview";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: 1, label: "Template" },
  { id: 2, label: "Sources" },
  { id: 3, label: "Configure" },
  { id: 4, label: "Generate" },
  { id: 5, label: "Preview" },
];

interface PresentationGeneratorProps {
  notebookId?: string;
  onComplete?: (presentationId: string) => void;
}

export function PresentationGenerator({
  notebookId,
  onComplete,
}: PresentationGeneratorProps) {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [presentationId, setPresentationId] = useState<string | null>(null);

  // Form state
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [slideCount, setSlideCount] = useState(10);

  // Fetch templates
  const { data: templates, isLoading: templatesLoading } = useQuery({
    queryKey: ["presentation-templates"],
    queryFn: () => presentationApi.listTemplates(),
  });

  // Fetch sources from notebook
  const { data: sources, isLoading: sourcesLoading } = useQuery({
    queryKey: ["notebook-sources", notebookId],
    queryFn: async () => {
      if (!notebookId) return [];
      try {
        const { data } = await apiClient.get(`/workspaces/${notebookId}/sources`);
        console.log('Fetched sources:', data);
        return data;
      } catch (error) {
        console.error('Failed to fetch sources:', error);
        return [];
      }
    },
    enabled: currentStep === 2 && !!notebookId,
  });

  // Fetch notes from notebook
  const { data: notes, isLoading: notesLoading } = useQuery({
    queryKey: ["notebook-notes", notebookId],
    queryFn: async () => {
      if (!notebookId) return [];
      try {
        const { data } = await apiClient.get(`/notes`, {
          params: { notebook_id: notebookId }
        });
        console.log('Fetched notes:', data);
        return data;
      } catch (error) {
        console.error('Failed to fetch notes:', error);
        return [];
      }
    },
    enabled: currentStep === 2 && !!notebookId,
  });

  // Generate presentation mutation
  const generateMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTemplate) throw new Error("No template selected");

      const newId = generateUUID();
      setPresentationId(newId);

      // Create presentation record
      await presentationApi.create({
        notebook_id: notebookId,
        template_id: selectedTemplate,
        title: title || "Untitled Presentation",
        description: userPrompt,
      });

      // Generate slides
      await presentationApi.generate(newId, {
        template_id: selectedTemplate,
        source_ids: selectedSources,
        notebook_id: notebookId,
        user_prompt: userPrompt,
        target_slide_count: slideCount,
      });

      return newId;
    },
    onSuccess: (id) => {
      toast.success("Presentation generated successfully!");
      setCurrentStep(5);
      onComplete?.(id);
    },
    onError: (error) => {
      console.error("Generation failed:", error);
      toast.error("Failed to generate presentation");
    },
  });

  // Navigation
  const canProceed = () => {
    if (currentStep === 1) return selectedTemplate !== null;
    if (currentStep === 2) return true; // Sources optional
    if (currentStep === 3) return title.trim().length > 0 && userPrompt.trim().length > 0;
    if (currentStep === 4) return true; // Allow generation
    return false;
  };

  const handleNext = () => {
    if (currentStep < 4) {
      setCurrentStep(currentStep + 1);
    } else if (currentStep === 4) {
      generateMutation.mutate();
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  // Group templates by category
  const groupedTemplates = templates?.reduce((acc, template) => {
    const category = template.category || "Other";
    if (!acc[category]) acc[category] = [];
    acc[category].push(template);
    return acc;
  }, {} as Record<string, PresentationTemplate[]>);

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Stepper */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {STEPS.map((step, idx) => (
            <div key={step.id} className="flex items-center flex-1">
              <div className="flex flex-col items-center flex-1">
                <div
                  className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors",
                    currentStep >= step.id
                      ? "bg-primary border-primary text-primary-foreground"
                      : "bg-background border-border text-muted-foreground"
                  )}
                >
                  {currentStep > step.id ? (
                    <Check className="h-5 w-5" />
                  ) : (
                    <span className="text-sm font-medium">{step.id}</span>
                  )}
                </div>
                <span
                  className={cn(
                    "text-sm mt-2 font-medium",
                    currentStep >= step.id
                      ? "text-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
              </div>

              {idx < STEPS.length - 1 && (
                <div
                  className={cn(
                    "h-0.5 flex-1 mx-4 transition-colors",
                    currentStep > step.id ? "bg-primary" : "bg-border"
                  )}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <div className="min-h-[500px]">
        {/* Step 1: Template Selection */}
        {currentStep === 1 && (
          <div>
            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-2">Choose a Template</h2>
              <p className="text-muted-foreground">
                Select a presentation template to get started
              </p>
            </div>

            {templatesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="space-y-6">
                {Object.entries(groupedTemplates || {}).map(([category, temps]) => (
                  <div key={category}>
                    <h3 className="text-lg font-semibold mb-3 capitalize">
                      {category}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {temps.map((template) => {
                        const isSelected = selectedTemplate === template.id;
                        const theme =
                          typeof template.theme_json === "string"
                            ? JSON.parse(template.theme_json)
                            : template.theme_json;

                        return (
                          <Card
                            key={template.id}
                            className={cn(
                              "cursor-pointer transition-all hover:shadow-lg",
                              isSelected && "ring-2 ring-primary"
                            )}
                            onClick={() => setSelectedTemplate(template.id)}
                          >
                            <CardHeader>
                              <div className="flex items-start justify-between mb-2">
                                <FileText className="h-8 w-8 text-muted-foreground" />
                                {isSelected && (
                                  <div className="bg-primary text-primary-foreground rounded-full p-1">
                                    <Check className="h-4 w-4" />
                                  </div>
                                )}
                              </div>
                              <CardTitle>{template.name}</CardTitle>
                              <CardDescription>
                                {template.description}
                              </CardDescription>
                            </CardHeader>
                            <CardContent>
                              {/* Color Preview */}
                              <div className="flex gap-2">
                                {theme?.colors?.primary && (
                                  <div
                                    className="w-8 h-8 rounded border"
                                    style={{
                                      backgroundColor: theme.colors.primary,
                                    }}
                                  />
                                )}
                                {theme?.colors?.secondary && (
                                  <div
                                    className="w-8 h-8 rounded border"
                                    style={{
                                      backgroundColor: theme.colors.secondary,
                                    }}
                                  />
                                )}
                                {theme?.colors?.accent && (
                                  <div
                                    className="w-8 h-8 rounded border"
                                    style={{
                                      backgroundColor: theme.colors.accent,
                                    }}
                                  />
                                )}
                              </div>
                            </CardContent>
                          </Card>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Source Selection */}
        {currentStep === 2 && (
          <div>
            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-2">Select Sources</h2>
              <p className="text-muted-foreground">
                Choose documents, notes, and data to include in your presentation (optional)
              </p>
            </div>

            {(sourcesLoading || notesLoading) ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (sources && sources.length > 0) || (notes && notes.length > 0) ? (
              <div className="space-y-6">
                {/* Select All Button */}
                <div className="flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const allIds = [
                        ...(sources || []).map((s: any) => s.id),
                        ...(notes || []).map((n: any) => n.id)
                      ];
                      if (selectedSources.length === allIds.length) {
                        setSelectedSources([]);
                      } else {
                        setSelectedSources(allIds);
                      }
                    }}
                  >
                    {selectedSources.length === ((sources?.length || 0) + (notes?.length || 0))
                      ? 'Deselect All'
                      : 'Select All'}
                  </Button>
                </div>

                {/* Sources Section */}
                {sources && sources.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3">Sources ({sources.length})</h3>
                    <div className="space-y-2">
                      {sources.map((source: any) => (
                        <label
                          key={source.id}
                          className="flex items-start gap-3 p-4 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                        >
                          <Checkbox
                            checked={selectedSources.includes(source.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedSources([...selectedSources, source.id]);
                              } else {
                                setSelectedSources(
                                  selectedSources.filter((id) => id !== source.id)
                                );
                              }
                            }}
                          />
                          <div className="flex-1">
                            <p className="font-medium">{source.title || source.name}</p>
                            <p className="text-sm text-muted-foreground">
                              {source.source_type}
                            </p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* Notes Section */}
                {notes && notes.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3">Notes ({notes.length})</h3>
                    <div className="space-y-2">
                      {notes.map((note: any) => (
                        <label
                          key={note.id}
                          className="flex items-start gap-3 p-4 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                        >
                          <Checkbox
                            checked={selectedSources.includes(note.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedSources([...selectedSources, note.id]);
                              } else {
                                setSelectedSources(
                                  selectedSources.filter((id) => id !== note.id)
                                );
                              }
                            }}
                          />
                          <div className="flex-1">
                            <p className="font-medium">{note.title || 'Untitled Note'}</p>
                            <p className="text-sm text-muted-foreground">
                              Note • {note.content ? `${note.content.substring(0, 100)}...` : 'Empty'}
                            </p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* Selection Summary */}
                {selectedSources.length > 0 && (
                  <div className="text-sm text-muted-foreground">
                    {selectedSources.length} item{selectedSources.length !== 1 ? 's' : ''} selected
                  </div>
                )}
              </div>
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <p className="text-muted-foreground mb-4">
                    No sources available in this workspace
                  </p>
                  <p className="text-sm text-muted-foreground">
                    You can still generate a presentation based on your prompt
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Step 3: Configure */}
        {currentStep === 3 && (
          <div>
            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-2">Configure Presentation</h2>
              <p className="text-muted-foreground">
                Provide details about what you want to create
              </p>
            </div>

            <div className="space-y-6 max-w-2xl">
              <div>
                <Label htmlFor="title">Presentation Title</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter presentation title"
                  className="mt-1.5"
                />
              </div>

              <div>
                <Label htmlFor="prompt">What should the presentation be about?</Label>
                <Textarea
                  id="prompt"
                  value={userPrompt}
                  onChange={(e) => setUserPrompt(e.target.value)}
                  placeholder="Describe what you want the presentation to cover..."
                  rows={6}
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-2">
                  Be specific about topics, key points, and the target audience
                </p>
              </div>

              <div>
                <Label htmlFor="slideCount">Number of Slides</Label>
                <Select
                  value={slideCount.toString()}
                  onValueChange={(value) => setSlideCount(parseInt(value))}
                >
                  <SelectTrigger className="mt-1.5">
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
            </div>
          </div>
        )}

        {/* Step 4: Generating */}
        {currentStep === 4 && (
          <div className="flex flex-col items-center justify-center py-12">
            {generateMutation.isPending ? (
              <>
                <Loader2 className="h-16 w-16 animate-spin text-primary mb-6" />
                <h3 className="text-2xl font-bold mb-2">Generating Presentation</h3>
                <p className="text-muted-foreground text-center max-w-md">
                  AI is creating your {slideCount}-slide presentation...
                </p>
              </>
            ) : generateMutation.isError ? (
              <>
                <div className="text-destructive text-6xl mb-6">✕</div>
                <h3 className="text-2xl font-bold mb-2">Generation Failed</h3>
                <p className="text-muted-foreground text-center max-w-md mb-6">
                  {generateMutation.error?.message || "An error occurred"}
                </p>
                <Button onClick={() => generateMutation.mutate()}>
                  Try Again
                </Button>
              </>
            ) : null}
          </div>
        )}

        {/* Step 5: Preview */}
        {currentStep === 5 && presentationId && (
          <div>
            <div className="mb-6">
              <h2 className="text-2xl font-bold mb-2">Preview & Download</h2>
              <p className="text-muted-foreground">
                Your presentation is ready! Review and download.
              </p>
            </div>

            <SlidePreview
              presentationId={presentationId}
              onEdit={(slideNumber) => {
                toast.info(`Edit slide ${slideNumber} - Coming soon!`);
              }}
            />
          </div>
        )}
      </div>

      {/* Navigation Buttons */}
      {currentStep < 5 && (
        <div className="flex items-center justify-between mt-8 pt-6 border-t">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === 1 || generateMutation.isPending}
          >
            Back
          </Button>

          <Button
            onClick={handleNext}
            disabled={!canProceed() || generateMutation.isPending}
            className="gap-2"
          >
            {currentStep === 4 ? (
              <>
                <Sparkles className="h-4 w-4" />
                Generate Presentation
              </>
            ) : (
              <>
                Next
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
