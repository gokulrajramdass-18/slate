/**
 * Slide Editor Component
 *
 * Visual editor for individual slides with layout and content editing.
 */

"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Save, X, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { presentationApi, type SlideContent } from "@/lib/api/presentations";
import { cn } from "@/lib/utils";

const SLIDE_LAYOUTS = [
  {
    type: "title",
    label: "Title Slide",
    description: "Large title with optional subtitle",
  },
  {
    type: "bullets",
    label: "Bullet Points",
    description: "Title with bullet point list",
  },
  {
    type: "two_column",
    label: "Two Columns",
    description: "Side-by-side content layout",
  },
  {
    type: "content",
    label: "Content",
    description: "Title with paragraph content",
  },
  {
    type: "image_text",
    label: "Image & Text",
    description: "Text with image placeholder",
  },
  {
    type: "chart",
    label: "Chart",
    description: "Title with chart placeholder",
  },
];

interface SlideEditorProps {
  presentationId: string;
  slideNumber: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SlideEditor({
  presentationId,
  slideNumber,
  open,
  onOpenChange,
}: SlideEditorProps) {
  const queryClient = useQueryClient();

  // Fetch slide data
  const { data: slide, isLoading } = useQuery({
    queryKey: ["slide", presentationId, slideNumber],
    queryFn: () => presentationApi.getSlide(presentationId, slideNumber),
    enabled: open,
  });

  // Local state
  const [selectedLayout, setSelectedLayout] = useState<string>("bullets");
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [elements, setElements] = useState<Array<{ content: string; column?: string }>>([]);
  const [speakerNotes, setSpeakerNotes] = useState("");

  // Initialize from slide data
  useEffect(() => {
    if (slide) {
      setSelectedLayout(slide.slide_type);

      const contentJson =
        typeof slide.content_json === "string"
          ? JSON.parse(slide.content_json)
          : slide.content_json;

      setTitle(contentJson.title || "");
      setSubtitle(contentJson.subtitle || "");
      setElements(contentJson.elements || []);
      setSpeakerNotes(slide.speaker_notes || "");
    }
  }, [slide]);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async () => {
      const content_json: any = {
        title,
        elements: elements.map((el, idx) => ({
          type:
            selectedLayout === "bullets"
              ? "bullet"
              : selectedLayout === "two_column"
              ? "bullet"
              : "paragraph",
          content: el.content,
          column: el.column,
          level: 0,
        })),
      };

      if (selectedLayout === "title") {
        content_json.subtitle = subtitle;
      }

      await presentationApi.updateSlide(presentationId, slideNumber, {
        slide_type: selectedLayout,
        content_json,
        speaker_notes: speakerNotes,
      });
    },
    onSuccess: () => {
      toast.success("Slide updated successfully");
      queryClient.invalidateQueries({
        queryKey: ["presentation-slides", presentationId],
      });
      queryClient.invalidateQueries({
        queryKey: ["slide", presentationId, slideNumber],
      });
      onOpenChange(false);
    },
    onError: (error) => {
      console.error("Update failed:", error);
      toast.error("Failed to update slide");
    },
  });

  const handleAddElement = () => {
    setElements([...elements, { content: "" }]);
  };

  const handleRemoveElement = (index: number) => {
    setElements(elements.filter((_, i) => i !== index));
  };

  const handleUpdateElement = (index: number, content: string) => {
    const updated = [...elements];
    updated[index] = { ...updated[index], content };
    setElements(updated);
  };

  const handleUpdateElementColumn = (index: number, column: string) => {
    const updated = [...elements];
    updated[index] = { ...updated[index], column };
    setElements(updated);
  };

  const handleSave = () => {
    updateMutation.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Slide {slideNumber}</DialogTitle>
          <DialogDescription>
            Modify the content and layout of this slide
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Layout Selection */}
            <div>
              <Label>Slide Layout</Label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
                {SLIDE_LAYOUTS.map((layout) => (
                  <button
                    key={layout.type}
                    onClick={() => setSelectedLayout(layout.type)}
                    className={cn(
                      "p-3 border rounded-lg text-left transition-all hover:border-primary",
                      selectedLayout === layout.type &&
                        "border-primary bg-primary/5"
                    )}
                  >
                    <p className="font-medium text-sm">{layout.label}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {layout.description}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {/* Title */}
            <div>
              <Label htmlFor="slide-title">Slide Title</Label>
              <Input
                id="slide-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter slide title"
                className="mt-1.5"
              />
            </div>

            {/* Subtitle (for title slide) */}
            {selectedLayout === "title" && (
              <div>
                <Label htmlFor="slide-subtitle">Subtitle</Label>
                <Input
                  id="slide-subtitle"
                  value={subtitle}
                  onChange={(e) => setSubtitle(e.target.value)}
                  placeholder="Enter subtitle (optional)"
                  className="mt-1.5"
                />
              </div>
            )}

            {/* Content Elements */}
            {selectedLayout !== "title" && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <Label>
                    {selectedLayout === "bullets" || selectedLayout === "two_column"
                      ? "Bullet Points"
                      : "Content"}
                  </Label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleAddElement}
                    className="gap-1"
                  >
                    <Plus className="h-3 w-3" />
                    Add {selectedLayout === "bullets" ? "Bullet" : "Paragraph"}
                  </Button>
                </div>

                <div className="space-y-2">
                  {elements.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground text-sm border-2 border-dashed rounded-lg">
                      No content yet. Click "Add" to create content.
                    </div>
                  ) : (
                    elements.map((element, index) => (
                      <div key={index} className="flex gap-2">
                        {selectedLayout === "two_column" && (
                          <Select
                            value={element.column || "left"}
                            onValueChange={(v) =>
                              handleUpdateElementColumn(index, v)
                            }
                          >
                            <SelectTrigger className="w-24">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="left">Left</SelectItem>
                              <SelectItem value="right">Right</SelectItem>
                            </SelectContent>
                          </Select>
                        )}

                        <Textarea
                          value={element.content}
                          onChange={(e) =>
                            handleUpdateElement(index, e.target.value)
                          }
                          placeholder={
                            selectedLayout === "bullets" ||
                            selectedLayout === "two_column"
                              ? "Bullet point text"
                              : "Paragraph content"
                          }
                          rows={2}
                          className="flex-1"
                        />

                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveElement(index)}
                          className="flex-shrink-0"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Speaker Notes */}
            <div>
              <Label htmlFor="speaker-notes">Speaker Notes</Label>
              <Textarea
                id="speaker-notes"
                value={speakerNotes}
                onChange={(e) => setSpeakerNotes(e.target.value)}
                placeholder="Add notes for the presenter..."
                rows={3}
                className="mt-1.5"
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={updateMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={updateMutation.isPending || !title}
            className="gap-2"
          >
            {updateMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                Save Changes
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
