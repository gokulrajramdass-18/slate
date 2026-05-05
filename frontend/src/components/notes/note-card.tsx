"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Pencil, Trash2, Link2, ArrowLeft, Copy, Check, Download, FileText, FileType } from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";
import { BookmarkButton } from "@/components/bookmarks/bookmark-button";
import { useState } from "react";
import { toast } from "sonner";
import { notesApi, downloadBlob } from "@/lib/api";

interface Note {
  id: string;
  title: string;
  content: string;
  content_html: string | null;
  linked_notes: Array<{ id: string; title: string }>;
  backlinks: Array<{ id: string; title: string }>;
  tags: string[];
  is_bookmarked?: boolean;
  created: string;
  updated: string;
}

interface NoteCardProps {
  note: Note;
  onEdit: (note: Note) => void;
  onDelete: (noteId: string) => void;
  onNoteClick?: (noteId: string) => void;
}

export function NoteCard({ note, onEdit, onDelete, onNoteClick }: NoteCardProps) {
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Are you sure you want to delete "${note.title}"?`)) {
      onDelete(note.id);
    }
  };

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    onEdit(note);
  };

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      // Create a clean text version by stripping HTML tags
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = note.content_html || note.content;
      const textContent = tempDiv.textContent || tempDiv.innerText || '';

      // Add title at the top
      const copyText = `${note.title}\n\n${textContent}`;

      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      toast.success("Note copied to clipboard");

      // Reset icon after 2 seconds
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
      toast.error("Failed to copy note");
    }
  };

  const handleDownloadMarkdown = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloading(true);
    try {
      const blob = await notesApi.exportMarkdown(note.id);
      const filename = `${note.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.md`;
      downloadBlob(blob, filename);
      toast.success("Markdown file downloaded");
    } catch (error) {
      console.error('Failed to download markdown:', error);
      toast.error("Failed to download markdown");
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadPdf = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloading(true);
    try {
      const blob = await notesApi.exportPdf(note.id);
      const filename = `${note.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.pdf`;
      downloadBlob(blob, filename);
      toast.success("PDF file downloaded");
    } catch (error) {
      console.error('Failed to download PDF:', error);
      toast.error("Failed to download PDF");
    } finally {
      setDownloading(false);
    }
  };

  const handleCardClick = () => {
    if (onNoteClick) {
      onNoteClick(note.id);
    }
  };

  // Check if this is a final deliverable
  const isFinalDeliverable = note.title.includes("🎯 FINAL DELIVERABLE") ||
                             note.title.includes("FINAL DELIVERABLE");

  return (
    <div
      className={`group relative border-b last:border-b-0 hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors cursor-pointer ${
        isFinalDeliverable ? 'border-l-4 border-l-purple-500 bg-purple-50/30 dark:bg-purple-950/10 pl-2' : 'border-gray-200 dark:border-gray-800'
      }`}
      onClick={handleCardClick}
    >
      {/* Single Row Compact Layout */}
      <div className="flex items-center gap-3 py-2.5 px-3">
        {/* Left: Title + Preview */}
        <div className="flex-1 min-w-0 space-y-0.5">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-sm truncate">{note.title}</h3>
            {isFinalDeliverable && (
              <Badge className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs px-1.5 py-0 h-4 shrink-0">
                FINAL
              </Badge>
            )}
            {/* Inline Tags */}
            {note.tags && note.tags.length > 0 && (
              <div className="flex gap-1">
                {note.tags.slice(0, 2).map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs px-1.5 py-0 h-4 font-normal">
                    {tag}
                  </Badge>
                ))}
                {note.tags.length > 2 && (
                  <Badge variant="secondary" className="text-xs px-1.5 py-0 h-4 font-normal">
                    +{note.tags.length - 2}
                  </Badge>
                )}
              </div>
            )}
          </div>

          {/* Inline Preview + Metadata */}
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <span className="shrink-0">{formatRelativeTime(note.updated)}</span>
            {/* Content Preview (truncated) */}
            <span className="truncate opacity-75">
              {note.content_html
                ? note.content_html.replace(/<[^>]*>/g, '').substring(0, 80)
                : note.content.substring(0, 80)}
              {(note.content_html?.length || note.content.length) > 80 ? '...' : ''}
            </span>
            {/* Links Stats */}
            {(note.linked_notes?.length > 0 || note.backlinks?.length > 0) && (
              <div className="flex items-center gap-2 shrink-0">
                {note.linked_notes && note.linked_notes.length > 0 && (
                  <div className="flex items-center gap-1">
                    <Link2 className="w-3 h-3" />
                    <span>{note.linked_notes.length}</span>
                  </div>
                )}
                {note.backlinks && note.backlinks.length > 0 && (
                  <div className="flex items-center gap-1">
                    <ArrowLeft className="w-3 h-3" />
                    <span>{note.backlinks.length}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: Actions (hidden by default) */}
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" onClick={(e) => e.stopPropagation()}>
          <BookmarkButton
            entityType="note"
            entityId={note.id}
            isBookmarked={note.is_bookmarked}
          />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                title="Download note"
                className="h-7 w-7 p-0"
                disabled={downloading}
              >
                <Download className="w-3.5 h-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleDownloadMarkdown}>
                <FileText className="w-4 h-4 mr-2" />
                Download as Markdown
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDownloadPdf}>
                <FileType className="w-4 h-4 mr-2" />
                Download as PDF
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            title="Copy note content"
            className="h-7 w-7 p-0"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-green-600" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleEdit} className="h-7 w-7 p-0">
            <Pencil className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDelete}
            className="h-7 w-7 p-0 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Expandable Links Section (shown on hover for notes with links) */}
      {(note.linked_notes?.length > 0 || note.backlinks?.length > 0) && (
        <div className="hidden group-hover:block border-t border-gray-100 dark:border-gray-800 px-3 py-2 space-y-1.5 bg-gray-50/50 dark:bg-gray-900/30">
          {note.linked_notes && note.linked_notes.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400 font-medium shrink-0">Links:</span>
              <div className="flex flex-wrap gap-1">
                {note.linked_notes.map((linked) => (
                  <Badge
                    key={linked.id}
                    variant="outline"
                    className="cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 text-xs px-1.5 py-0 h-5"
                    onClick={() => onNoteClick?.(linked.id)}
                  >
                    {linked.title}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {note.backlinks && note.backlinks.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400 font-medium shrink-0">Refs:</span>
              <div className="flex flex-wrap gap-1">
                {note.backlinks.map((backlink) => (
                  <Badge
                    key={backlink.id}
                    variant="outline"
                    className="cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 text-xs px-1.5 py-0 h-5"
                    onClick={() => onNoteClick?.(backlink.id)}
                  >
                    {backlink.title}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
