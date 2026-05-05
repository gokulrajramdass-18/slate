"use client";

import { useState, useCallback, useEffect } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Bold,
  Italic,
  Strikethrough,
  Heading1,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  Quote,
  Minus,
  Undo2,
  Redo2,
  Link2,
  Link2Off,
  Save,
  GripVertical,
  Eye,
  EyeOff,
  Trash2,
  Loader2,
  ChevronUp,
  ChevronDown,
} from "lucide-react";
import { toast } from "sonner";
import type { MicrositeContent } from "@/lib/types";

interface EditorToolbarProps {
  editor: ReturnType<typeof useEditor>;
}

function EditorToolbar({ editor }: EditorToolbarProps) {
  if (!editor) return null;

  const addLink = () => {
    const url = window.prompt("Enter URL:");
    if (url) {
      editor.chain().focus().setLink({ href: url }).run();
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-0.5 p-2 border-b bg-muted/30">
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleBold().run()}
        data-active={editor.isActive("bold") || undefined}
      >
        <Bold className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleItalic().run()}
        data-active={editor.isActive("italic") || undefined}
      >
        <Italic className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleStrike().run()}
        data-active={editor.isActive("strike") || undefined}
      >
        <Strikethrough className="w-4 h-4" />
      </Button>

      <Separator orientation="vertical" className="h-6 mx-1" />

      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        data-active={editor.isActive("heading", { level: 1 }) || undefined}
      >
        <Heading1 className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        data-active={editor.isActive("heading", { level: 2 }) || undefined}
      >
        <Heading2 className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        data-active={editor.isActive("heading", { level: 3 }) || undefined}
      >
        <Heading3 className="w-4 h-4" />
      </Button>

      <Separator orientation="vertical" className="h-6 mx-1" />

      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        data-active={editor.isActive("bulletList") || undefined}
      >
        <List className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        data-active={editor.isActive("orderedList") || undefined}
      >
        <ListOrdered className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        data-active={editor.isActive("blockquote") || undefined}
      >
        <Quote className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
      >
        <Minus className="w-4 h-4" />
      </Button>

      <Separator orientation="vertical" className="h-6 mx-1" />

      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={addLink}
        data-active={editor.isActive("link") || undefined}
      >
        <Link2 className="w-4 h-4" />
      </Button>
      {editor.isActive("link") && (
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          onClick={() => editor.chain().focus().unsetLink().run()}
        >
          <Link2Off className="w-4 h-4" />
        </Button>
      )}

      <Separator orientation="vertical" className="h-6 mx-1" />

      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
      >
        <Undo2 className="w-4 h-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0"
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
      >
        <Redo2 className="w-4 h-4" />
      </Button>
    </div>
  );
}

interface SectionEditorProps {
  section: MicrositeContent;
  onUpdate: (sectionId: string, html: string, json: string) => void;
  onToggleVisibility: (sectionId: string) => void;
  onDelete: (sectionId: string) => void;
  onMoveUp: (sectionId: string) => void;
  onMoveDown: (sectionId: string) => void;
  isFirst: boolean;
  isLast: boolean;
}

function SectionEditor({
  section,
  onUpdate,
  onToggleVisibility,
  onDelete,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: SectionEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder: "Start writing..." }),
    ],
    content: section.content_html,
    onUpdate: ({ editor }) => {
      onUpdate(section.section_id, editor.getHTML(), JSON.stringify(editor.getJSON()));
    },
  });

  return (
    <div className={`rounded-lg border ${!section.is_visible ? "opacity-50" : ""}`}>
      <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/30">
        <GripVertical className="w-4 h-4 text-muted-foreground cursor-grab" />
        <Badge variant="outline" className="text-xs capitalize">
          {section.section_type}
        </Badge>
        <span className="text-xs text-muted-foreground flex-1">
          {section.section_id}
        </span>
        <div className="flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => onMoveUp(section.section_id)}
            disabled={isFirst}
          >
            <ChevronUp className="w-3 h-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => onMoveDown(section.section_id)}
            disabled={isLast}
          >
            <ChevronDown className="w-3 h-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => onToggleVisibility(section.section_id)}
          >
            {section.is_visible ? (
              <Eye className="w-3 h-3" />
            ) : (
              <EyeOff className="w-3 h-3" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-red-500 hover:text-red-700"
            onClick={() => {
              if (confirm("Delete this section?")) {
                onDelete(section.section_id);
              }
            }}
          >
            <Trash2 className="w-3 h-3" />
          </Button>
        </div>
      </div>
      {section.is_visible && (
        <>
          <EditorToolbar editor={editor} />
          <div className="p-4 prose prose-sm max-w-none dark:prose-invert">
            <EditorContent editor={editor} />
          </div>
        </>
      )}
    </div>
  );
}

interface WYSIWYGEditorProps {
  micrositeId: string;
  sections: MicrositeContent[];
  onSave: (sections: { section_id: string; content_html: string; content_json: string }[]) => Promise<void>;
  isSaving?: boolean;
}

export function WYSIWYGEditor({
  micrositeId,
  sections: initialSections,
  onSave,
  isSaving,
}: WYSIWYGEditorProps) {
  const [sections, setSections] = useState<MicrositeContent[]>(initialSections);
  const [pendingChanges, setPendingChanges] = useState<
    Map<string, { html: string; json: string }>
  >(new Map());
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    setSections(initialSections);
  }, [initialSections]);

  const handleUpdate = useCallback(
    (sectionId: string, html: string, json: string) => {
      setPendingChanges((prev) => {
        const next = new Map(prev);
        next.set(sectionId, { html, json });
        return next;
      });
      setHasChanges(true);
    },
    []
  );

  const handleToggleVisibility = useCallback((sectionId: string) => {
    setSections((prev) =>
      prev.map((s) =>
        s.section_id === sectionId ? { ...s, is_visible: !s.is_visible } : s
      )
    );
    setHasChanges(true);
  }, []);

  const handleDelete = useCallback((sectionId: string) => {
    setSections((prev) => prev.filter((s) => s.section_id !== sectionId));
    setPendingChanges((prev) => {
      const next = new Map(prev);
      next.delete(sectionId);
      return next;
    });
    setHasChanges(true);
  }, []);

  const handleMoveUp = useCallback((sectionId: string) => {
    setSections((prev) => {
      const index = prev.findIndex((s) => s.section_id === sectionId);
      if (index <= 0) return prev;
      const next = [...prev];
      [next[index - 1], next[index]] = [next[index], next[index - 1]];
      return next;
    });
    setHasChanges(true);
  }, []);

  const handleMoveDown = useCallback((sectionId: string) => {
    setSections((prev) => {
      const index = prev.findIndex((s) => s.section_id === sectionId);
      if (index < 0 || index >= prev.length - 1) return prev;
      const next = [...prev];
      [next[index], next[index + 1]] = [next[index + 1], next[index]];
      return next;
    });
    setHasChanges(true);
  }, []);

  const handleSave = async () => {
    const updates = sections.map((section) => {
      const change = pendingChanges.get(section.section_id);
      return {
        section_id: section.section_id,
        content_html: change?.html || section.content_html,
        content_json: change?.json || section.content_json || "",
      };
    });

    try {
      await onSave(updates);
      setPendingChanges(new Map());
      setHasChanges(false);
      toast.success("Content saved");
    } catch {
      toast.error("Failed to save content");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-medium">Visual Editor</h3>
          {hasChanges && (
            <Badge variant="secondary" className="text-xs">
              Unsaved changes
            </Badge>
          )}
        </div>
        <Button onClick={handleSave} disabled={!hasChanges || isSaving}>
          {isSaving ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          Save
        </Button>
      </div>

      <div className="space-y-4">
        {sections.map((section, index) => (
          <SectionEditor
            key={section.section_id}
            section={section}
            onUpdate={handleUpdate}
            onToggleVisibility={handleToggleVisibility}
            onDelete={handleDelete}
            onMoveUp={handleMoveUp}
            onMoveDown={handleMoveDown}
            isFirst={index === 0}
            isLast={index === sections.length - 1}
          />
        ))}
      </div>

      {sections.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No content sections. Generate content first.
        </div>
      )}
    </div>
  );
}
