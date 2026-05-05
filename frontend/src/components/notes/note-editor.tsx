"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { X, Link2, Tag } from "lucide-react";
import { RichTextEditor } from "./rich-text-editor";
import { toast } from "sonner";

interface Note {
  id: string;
  title: string;
  content: string;
  content_html: string | null;
  linked_notes: Array<{ id: string; title: string }>;
  backlinks: Array<{ id: string; title: string }>;
  tags: string[];
}

interface NoteEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  notebookId: string;
  note?: Note | null;
  availableNotes: Note[];
  onSave: () => void;
}

export function NoteEditor({
  open,
  onOpenChange,
  notebookId,
  note,
  availableNotes,
  onSave,
}: NoteEditorProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [contentHtml, setContentHtml] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [linkedNoteIds, setLinkedNoteIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  // Check if this is an execution result note (readonly)
  const isExecutionResult = note?.title?.startsWith("Execution Results -");

  // Clean up HTML for execution results (remove excessive <br> tags)
  const cleanedHtml = isExecutionResult && contentHtml
    ? contentHtml
        .replace(/<br>\s*</g, '<')  // Remove <br> before opening tags
        .replace(/>\s*<br>/g, '>')  // Remove <br> after closing tags
        .replace(/<br><br>/g, '<br>') // Replace double <br> with single
        .replace(/class='execution-output'/g, 'class="execution-output"') // Fix quotes
    : contentHtml;

  useEffect(() => {
    if (note) {
      setTitle(note.title);
      setContent(note.content);
      setContentHtml(note.content_html || "");
      setTags(note.tags || []);
      setLinkedNoteIds(note.linked_notes?.map((n) => n.id) || []);
    } else {
      // Reset for new note
      setTitle("");
      setContent("");
      setContentHtml("");
      setTags([]);
      setLinkedNoteIds([]);
    }
  }, [note, open]);

  const handleEditorChange = (text: string, html: string) => {
    setContent(text);
    setContentHtml(html);
  };

  const handleAddTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags([...tags, tagInput.trim()]);
      setTagInput("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const toggleLinkedNote = (noteId: string) => {
    if (linkedNoteIds.includes(noteId)) {
      setLinkedNoteIds(linkedNoteIds.filter((id) => id !== noteId));
    } else {
      setLinkedNoteIds([...linkedNoteIds, noteId]);
    }
  };

  const handleSave = async () => {
    if (!title.trim()) {
      toast.error("Please enter a title");
      return;
    }

    if (!content.trim()) {
      toast.error("Please enter some content");
      return;
    }

    try {
      setSaving(true);

      const payload = {
        title: title.trim(),
        content: content,
        content_html: contentHtml,
        notebook_id: notebookId,
        tags,
        linked_note_ids: linkedNoteIds,
      };

      const url = note
        ? `http://localhost:5055/api/notes/${note.id}`
        : "http://localhost:5055/api/notes";
      const method = note ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        toast.success(note ? "Note updated" : "Note created");
        onSave();
        onOpenChange(false);
      } else {
        const error = await response.json();
        toast.error(error.detail || "Failed to save note");
      }
    } catch (error) {
      toast.error("Failed to save note");
    } finally {
      setSaving(false);
    }
  };

  // Filter out current note from linkable notes
  const linkableNotes = availableNotes.filter((n) => n.id !== note?.id);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{note ? (isExecutionResult ? title : "Edit Note") : "Create Note"}</DialogTitle>
        </DialogHeader>

        {isExecutionResult ? (
          /* Execution Result Display - Beautiful HTML Rendering */
          <div className="space-y-4">
            <div
              className="prose prose-lg dark:prose-invert max-w-none bg-white dark:bg-gray-900 rounded-lg p-8 shadow-sm border border-gray-200 dark:border-gray-800"
              dangerouslySetInnerHTML={{ __html: cleanedHtml }}
              style={{
                fontSize: '14px',
                lineHeight: '1.6',
              }}
            />
            <style dangerouslySetInnerHTML={{
              __html: `
                .prose h1 {
                  font-size: 2rem;
                  font-weight: 700;
                  margin-top: 1.5rem;
                  margin-bottom: 1rem;
                  color: #1f2937;
                  border-bottom: 2px solid #e5e7eb;
                  padding-bottom: 0.5rem;
                }
                .dark .prose h1 {
                  color: #f9fafb;
                  border-bottom-color: #374151;
                }
                .prose h2 {
                  font-size: 1.75rem;
                  font-weight: 600;
                  margin-top: 1.5rem;
                  margin-bottom: 0.75rem;
                  color: #374151;
                  border-bottom: 1px solid #e5e7eb;
                  padding-bottom: 0.375rem;
                }
                .dark .prose h2 {
                  color: #e5e7eb;
                  border-bottom-color: #4b5563;
                }
                .prose h3 {
                  font-size: 1.5rem;
                  font-weight: 600;
                  margin-top: 1.25rem;
                  margin-bottom: 0.5rem;
                  color: #4b5563;
                }
                .dark .prose h3 {
                  color: #d1d5db;
                }
                .prose h4 {
                  font-size: 1.25rem;
                  font-weight: 600;
                  margin-top: 1rem;
                  margin-bottom: 0.5rem;
                  color: #6b7280;
                }
                .dark .prose h4 {
                  color: #9ca3af;
                }
                .prose table {
                  width: 100%;
                  border-collapse: collapse;
                  margin: 1.5rem 0;
                  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
                  border-radius: 0.5rem;
                  overflow: hidden;
                }
                .prose thead {
                  background: linear-gradient(to bottom, #1e3a5f, #16304d);
                }
                .dark .prose thead {
                  background: linear-gradient(to bottom, #1e3a5f, #16304d);
                }
                .prose th {
                  padding: 12px 16px;
                  text-align: left;
                  font-weight: 600;
                  color: white !important;
                  border: 1px solid #ccc;
                }
                .dark .prose th {
                  color: white !important;
                }
                .prose td {
                  padding: 10px 16px;
                  border: 1px solid #e5e7eb;
                  color: #374151;
                }
                .dark .prose td {
                  border-color: #4b5563;
                  color: #d1d5db;
                }
                .prose tr:nth-child(even) {
                  background-color: #f0f4ff;
                }
                .dark .prose tr:nth-child(even) {
                  background-color: #1f2937;
                }
                .prose tr:hover {
                  background-color: #e0f2fe;
                }
                .dark .prose tr:hover {
                  background-color: #374151;
                }
                .prose strong {
                  font-weight: 600;
                  color: #1f2937;
                }
                .dark .prose strong {
                  color: #f9fafb;
                }
                .prose em {
                  font-style: italic;
                  color: #6b7280;
                }
                .dark .prose em {
                  color: #9ca3af;
                }
                .prose p {
                  margin: 0.75rem 0;
                  line-height: 1.6;
                }
                .prose ul, .prose ol {
                  margin: 1rem 0;
                  padding-left: 1.5rem;
                }
                .prose li {
                  margin: 0.5rem 0;
                }
                .prose hr {
                  margin: 2rem 0;
                  border: none;
                  border-top: 2px solid #e5e7eb;
                }
                .dark .prose hr {
                  border-top-color: #374151;
                }
              `
            }} />
          </div>
        ) : (
          /* Regular Note Editor */
          <div className="space-y-4">
            {/* Title */}
            <div>
              <Label>Title *</Label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Note title..."
                className="text-lg font-semibold"
              />
            </div>

            {/* Rich Text Editor */}
            <div>
              <Label>Content *</Label>
              <RichTextEditor
                content={contentHtml || content}
                onChange={handleEditorChange}
                placeholder="Start writing your note..."
              />
            </div>

          {/* Tags */}
          <div>
            <Label className="flex items-center gap-2">
              <Tag className="w-4 h-4" />
              Tags
            </Label>
            <div className="flex gap-2 mt-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddTag();
                  }
                }}
                placeholder="Add tag..."
                className="flex-1"
              />
              <Button onClick={handleAddTag} variant="outline">
                Add
              </Button>
            </div>
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="flex items-center gap-1">
                    {tag}
                    <button onClick={() => handleRemoveTag(tag)} className="hover:text-red-600">
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Link to other notes */}
          {linkableNotes.length > 0 && (
            <div>
              <Label className="flex items-center gap-2">
                <Link2 className="w-4 h-4" />
                Link to Notes
              </Label>
              <p className="text-sm text-gray-500 mb-2">
                Create connections between related notes
              </p>
              <div className="max-h-48 overflow-y-auto space-y-2">
                {linkableNotes.map((n) => (
                  <Card
                    key={n.id}
                    className={`p-3 cursor-pointer transition-colors ${
                      linkedNoteIds.includes(n.id)
                        ? "border-primary-600 bg-primary-50 dark:bg-primary-950"
                        : "hover:bg-gray-50 dark:hover:bg-gray-800"
                    }`}
                    onClick={() => toggleLinkedNote(n.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <p className="font-medium">{n.title}</p>
                        <p className="text-sm text-gray-500 line-clamp-1">{n.content}</p>
                      </div>
                      {linkedNoteIds.includes(n.id) && (
                        <Badge variant="default" className="ml-2">
                          Linked
                        </Badge>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : note ? "Update Note" : "Create Note"}
            </Button>
          </div>
        </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
