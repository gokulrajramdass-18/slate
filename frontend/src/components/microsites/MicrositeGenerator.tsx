"use client";

import { useState, useCallback, useEffect } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  Check,
  AlertCircle,
  ExternalLink,
  Pencil,
  Globe,
  FileText,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Database,
} from "lucide-react";
import { toast } from "sonner";
import { TemplateSelector } from "./TemplateSelector";
import { ModerationDashboard } from "./ModerationDashboard";
import {
  useMicrositeTemplates,
  useNotebooks,
  useNotebookSources,
  useGenerateMicrosite,
} from "@/lib/hooks/use-api";
import type {
  Notebook,
  Source,
  MicrositeTemplate,
  MicrositeGenerateResponse,
  ModerationReport,
} from "@/lib/types";

const STEPS = [
  { label: "Select Workspace", description: "Choose a notebook" },
  { label: "Choose Template", description: "Pick a design" },
  { label: "Select Sources", description: "Pick content sources" },
  { label: "Generate", description: "AI creates your site" },
  { label: "Review", description: "Check moderation results" },
  { label: "Edit / Publish", description: "Finalize your site" },
];

interface MicrositeGeneratorProps {
  micrositeId: string;
  initialNotebookId?: string;
  onComplete?: (micrositeId: string) => void;
  onEdit?: (micrositeId: string, mode: "visual" | "code") => void;
}

export function MicrositeGenerator({
  micrositeId,
  initialNotebookId,
  onComplete,
  onEdit,
}: MicrositeGeneratorProps) {
  const [step, setStep] = useState(initialNotebookId ? 1 : 0);
  const [selectedNotebookId, setSelectedNotebookId] = useState(initialNotebookId || "");
  const [selectedTemplate, setSelectedTemplate] = useState<MicrositeTemplate | null>(null);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [userPrompt, setUserPrompt] = useState("");
  const [generationResult, setGenerationResult] = useState<MicrositeGenerateResponse | null>(null);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [notes, setNotes] = useState<any[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(true);
  const [notesOpen, setNotesOpen] = useState(true);

  const { data: notebooks, isLoading: notebooksLoading } = useNotebooks();
  const { data: templates, isLoading: templatesLoading } = useMicrositeTemplates();
  const { data: sources, isLoading: sourcesLoading } = useNotebookSources(selectedNotebookId);
  const generateMutation = useGenerateMicrosite();

  // Fetch notes when notebook is selected
  useEffect(() => {
    if (selectedNotebookId) {
      setNotesLoading(true);
      fetch(`/api/notes?notebook_id=${selectedNotebookId}`)
        .then(res => res.json())
        .then(data => {
          setNotes(data);
          setNotesLoading(false);
        })
        .catch(err => {
          console.error('Failed to load notes:', err);
          setNotesLoading(false);
        });
    }
  }, [selectedNotebookId]);

  const canProceed = useCallback(() => {
    switch (step) {
      case 0: return !!selectedNotebookId;
      case 1: return !!selectedTemplate;
      case 2: return selectedSourceIds.length > 0;
      case 3: return !!generationResult;
      case 4: return true;
      case 5: return true;
      default: return false;
    }
  }, [step, selectedNotebookId, selectedTemplate, selectedSourceIds, generationResult]);

  const handleGenerate = async () => {
    if (!selectedTemplate) return;

    setGenerationProgress(0);
    const progressInterval = setInterval(() => {
      setGenerationProgress((prev) => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + Math.random() * 15;
      });
    }, 500);

    try {
      const result = await generateMutation.mutateAsync({
        micrositeId,
        request: {
          template_id: selectedTemplate.id,
          source_ids: selectedSourceIds,
          user_prompt: userPrompt || undefined,
        },
      });
      setGenerationResult(result);
      setGenerationProgress(100);
      clearInterval(progressInterval);
      toast.success("Microsite generated successfully");
      setStep(4);
    } catch (error: any) {
      clearInterval(progressInterval);
      setGenerationProgress(0);
      toast.error(error?.response?.data?.detail || "Generation failed");
    }
  };

  const handleNext = () => {
    if (step === 3 && !generationResult) {
      handleGenerate();
      return;
    }
    setStep((s) => Math.min(s + 1, 5));
  };

  const toggleSource = (sourceId: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(sourceId)
        ? prev.filter((id) => id !== sourceId)
        : [...prev, sourceId]
    );
  };

  const selectAllSources = () => {
    const allIds = [
      ...(sources?.map((s) => s.id) || []),
      ...(notes?.map((n) => n.id) || [])
    ];
    setSelectedSourceIds(allIds);
  };

  const deselectAllSources = () => {
    setSelectedSourceIds([]);
  };

  return (
    <div className="space-y-6">
      {/* Stepper */}
      <div className="flex items-center gap-1 overflow-x-auto pb-2">
        {STEPS.map((s, i) => (
          <div key={i} className="flex items-center">
            <button
              onClick={() => i < step && setStep(i)}
              disabled={i > step}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                i === step
                  ? "bg-primary text-primary-foreground"
                  : i < step
                  ? "bg-primary/10 text-primary hover:bg-primary/20 cursor-pointer"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              <span className="flex-shrink-0 w-6 h-6 rounded-full border flex items-center justify-center text-xs font-medium">
                {i < step ? <Check className="w-3 h-3" /> : i + 1}
              </span>
              <span className="hidden sm:inline whitespace-nowrap">{s.label}</span>
            </button>
            {i < STEPS.length - 1 && (
              <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0 mx-1" />
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>{STEPS[step].label}</CardTitle>
          <CardDescription>{STEPS[step].description}</CardDescription>
        </CardHeader>

        <CardContent>
          {/* Step 0: Select Workspace */}
          {step === 0 && (
            <div className="space-y-3">
              {notebooksLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin" />
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {notebooks?.map((nb: Notebook) => (
                    <Card
                      key={nb.id}
                      className={`cursor-pointer transition-all hover:shadow-sm ${
                        selectedNotebookId === nb.id
                          ? "ring-2 ring-primary border-primary"
                          : ""
                      }`}
                      onClick={() => setSelectedNotebookId(nb.id)}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <p className="font-medium">{nb.name}</p>
                            {nb.description && (
                              <p className="text-sm text-muted-foreground mt-1">
                                {nb.description}
                              </p>
                            )}
                          </div>
                          {selectedNotebookId === nb.id && (
                            <Check className="w-5 h-5 text-primary flex-shrink-0" />
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
              {notebooks?.length === 0 && (
                <p className="text-center text-muted-foreground py-8">
                  No notebooks found. Create a notebook first.
                </p>
              )}
            </div>
          )}

          {/* Step 1: Choose Template */}
          {step === 1 && (
            <TemplateSelector
              templates={templates || []}
              selectedId={selectedTemplate?.id || null}
              onSelect={setSelectedTemplate}
              isLoading={templatesLoading}
            />
          )}

          {/* Step 2: Select Sources */}
          {step === 2 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {selectedSourceIds.length} of {(sources?.length || 0) + (notes?.length || 0)} items selected
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={selectAllSources}>
                    Select All
                  </Button>
                  <Button variant="outline" size="sm" onClick={deselectAllSources}>
                    Deselect All
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Custom prompt (optional)</Label>
                <Textarea
                  placeholder="E.g., Focus on technical insights and use a professional tone..."
                  value={userPrompt}
                  onChange={(e) => setUserPrompt(e.target.value)}
                  rows={2}
                />
              </div>

              {sourcesLoading || notesLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin" />
                </div>
              ) : (
                <ScrollArea className="h-[300px] pr-4">
                  <div className="space-y-4">
                    {/* Data Sources Section - Now First */}
                    {sources && sources.length > 0 && (
                      <Collapsible open={sourcesOpen} onOpenChange={setSourcesOpen}>
                        <CollapsibleTrigger className="flex items-center justify-between w-full p-2 hover:bg-muted/50 rounded-lg">
                          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <Database className="w-4 h-4" />
                            <span>Data Sources ({sources.length})</span>
                          </div>
                          {sourcesOpen ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </CollapsibleTrigger>
                        <CollapsibleContent className="space-y-1 mt-2">
                          {sources.map((source: Source) => (
                            <div
                              key={source.id}
                              className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors hover:bg-muted/50 ${
                                selectedSourceIds.includes(source.id)
                                  ? "border-primary bg-primary/5"
                                  : ""
                              }`}
                              onClick={() => toggleSource(source.id)}
                            >
                              <div onClick={(e) => e.stopPropagation()}>
                                <Checkbox
                                  checked={selectedSourceIds.includes(source.id)}
                                  onCheckedChange={() => toggleSource(source.id)}
                                />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-sm truncate">{source.title}</p>
                                <div className="flex items-center gap-2 mt-1">
                                  <Badge variant="outline" className="text-xs capitalize">
                                    {source.source_type}
                                  </Badge>
                                  {source.chunk_count !== undefined && (
                                    <span className="text-xs text-muted-foreground">
                                      {source.chunk_count} chunks
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </CollapsibleContent>
                      </Collapsible>
                    )}

                    {/* Notes Section - Now Second */}
                    {notes && notes.length > 0 && (
                      <Collapsible open={notesOpen} onOpenChange={setNotesOpen}>
                        <CollapsibleTrigger className="flex items-center justify-between w-full p-2 hover:bg-muted/50 rounded-lg">
                          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                            <FileText className="w-4 h-4" />
                            <span>Notes ({notes.length})</span>
                          </div>
                          {notesOpen ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </CollapsibleTrigger>
                        <CollapsibleContent className="space-y-1 mt-2">
                          {/* Final Deliverable Note (if exists) */}
                          {notes.filter((note: any) => note.title.includes("🎯 FINAL DELIVERABLE") || note.title.includes("FINAL DELIVERABLE")).map((note: any) => (
                            <div
                              key={note.id}
                              className={`flex items-center gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                                selectedSourceIds.includes(note.id)
                                  ? "border-purple-500 bg-gradient-to-br from-purple-50 to-indigo-50"
                                  : "border-purple-300 bg-purple-50/50 hover:border-purple-400"
                              }`}
                              onClick={() => toggleSource(note.id)}
                            >
                              <div onClick={(e) => e.stopPropagation()}>
                                <Checkbox
                                  checked={selectedSourceIds.includes(note.id)}
                                  onCheckedChange={() => toggleSource(note.id)}
                                />
                              </div>
                              <Sparkles className="w-5 h-5 text-purple-600 flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <p className="font-semibold text-sm">{note.title}</p>
                                  <Badge className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs">
                                    FINAL
                                  </Badge>
                                </div>
                                <p className="text-xs text-purple-700 mt-1">
                                  ⚡ Comprehensive AI analysis - Highly recommended for best results
                                </p>
                              </div>
                            </div>
                          ))}

                          {/* Regular Notes */}
                          {notes.filter((note: any) => !note.title.includes("FINAL DELIVERABLE")).map((note: any) => (
                            <div
                              key={note.id}
                              className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors hover:bg-muted/50 ${
                                selectedSourceIds.includes(note.id)
                                  ? "border-primary bg-primary/5"
                                  : ""
                              }`}
                              onClick={() => toggleSource(note.id)}
                            >
                              <div onClick={(e) => e.stopPropagation()}>
                                <Checkbox
                                  checked={selectedSourceIds.includes(note.id)}
                                  onCheckedChange={() => toggleSource(note.id)}
                                />
                              </div>
                              <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-sm truncate">{note.title}</p>
                                <p className="text-xs text-muted-foreground">Note</p>
                              </div>
                            </div>
                          ))}
                        </CollapsibleContent>
                      </Collapsible>
                    )}
                  </div>
                </ScrollArea>
              )}

              {sources?.length === 0 && notes?.length === 0 && !sourcesLoading && !notesLoading && (
                <p className="text-center text-muted-foreground py-8">
                  No sources or notes in this notebook. Add sources or notes first.
                </p>
              )}
            </div>
          )}

          {/* Step 3: Generate */}
          {step === 3 && (
            <div className="flex flex-col items-center justify-center py-12 space-y-6">
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="w-12 h-12 animate-spin text-primary" />
                  <div className="text-center space-y-2">
                    <p className="text-lg font-medium">Generating your microsite...</p>
                    <p className="text-sm text-muted-foreground">
                      Analyzing {selectedSourceIds.length} sources with{" "}
                      {selectedTemplate?.display_name} template
                    </p>
                  </div>
                  <div className="w-full max-w-md">
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all duration-500"
                        style={{ width: `${generationProgress}%` }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground text-center mt-2">
                      {Math.round(generationProgress)}% complete
                    </p>
                  </div>
                </>
              ) : generationResult ? (
                <>
                  <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                    <Check className="w-8 h-8 text-green-600 dark:text-green-400" />
                  </div>
                  <div className="text-center space-y-2">
                    <p className="text-lg font-medium">Generation Complete</p>
                    <p className="text-sm text-muted-foreground">
                      Created {generationResult.sections.length} sections (version{" "}
                      {generationResult.version})
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-center space-y-4">
                    <p className="text-lg font-medium">Ready to Generate</p>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <p>Template: {selectedTemplate?.display_name}</p>
                      <p>Sources: {selectedSourceIds.length} selected</p>
                      {userPrompt && <p>Custom prompt provided</p>}
                    </div>
                    <Button onClick={handleGenerate} size="lg">
                      Start Generation
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 4: Review Moderation */}
          {step === 4 && generationResult && (
            <ModerationDashboard
              report={generationResult.moderation}
              micrositeId={micrositeId}
              onRerunModeration={() => {}}
            />
          )}

          {/* Step 5: Edit / Publish */}
          {step === 5 && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => onEdit?.(micrositeId, "visual")}
                >
                  <CardContent className="p-6 flex flex-col items-center text-center space-y-3">
                    <Pencil className="w-10 h-10 text-primary" />
                    <div>
                      <p className="font-medium">Visual Editor</p>
                      <p className="text-sm text-muted-foreground">
                        Edit with a WYSIWYG rich text editor
                      </p>
                    </div>
                    <Button variant="outline" size="sm">
                      Open Visual Editor
                    </Button>
                  </CardContent>
                </Card>

                <Card
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => onEdit?.(micrositeId, "code")}
                >
                  <CardContent className="p-6 flex flex-col items-center text-center space-y-3">
                    <span className="text-3xl font-mono text-primary">&lt;/&gt;</span>
                    <div>
                      <p className="font-medium">Code Editor</p>
                      <p className="text-sm text-muted-foreground">
                        Edit HTML, CSS, and JavaScript directly
                      </p>
                    </div>
                    <Button variant="outline" size="sm">
                      Open Code Editor
                    </Button>
                  </CardContent>
                </Card>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {generationResult && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const url = generationResult.preview_url;
                        if (url) window.open(url, "_blank");
                      }}
                    >
                      <ExternalLink className="w-4 h-4 mr-2" />
                      Preview
                    </Button>
                  )}
                </div>
                <Button onClick={() => onComplete?.(micrositeId)}>
                  <Globe className="w-4 h-4 mr-2" />
                  Publish Microsite
                </Button>
              </div>
            </div>
          )}
        </CardContent>

        <CardFooter className="justify-between">
          <Button
            variant="outline"
            onClick={() => setStep((s) => Math.max(s - 1, 0))}
            disabled={step === 0}
          >
            <ChevronLeft className="w-4 h-4 mr-2" />
            Back
          </Button>

          {step < 5 && (
            <Button
              onClick={handleNext}
              disabled={!canProceed() || (step === 3 && generateMutation.isPending)}
            >
              {step === 3 && !generationResult ? (
                generateMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  "Generate"
                )
              ) : (
                <>
                  Next
                  <ChevronRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}
