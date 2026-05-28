"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNotebookSources } from "@/lib/hooks/use-api";
import { apiClient } from "@/lib/api/client";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Search, FileText, Folder, Sparkles } from "lucide-react";
import type { Source } from "@/lib/types";

interface SourcesPopoverSelectorProps {
  selectedSources: string[];
  onSelectionChange: (sourceIds: string[]) => void;
  onNoteIdsChange?: (noteIds: string[]) => void;
  notebookId?: string;
  disabled?: boolean;
}

export function SourcesPopoverSelector({
  selectedSources,
  onSelectionChange,
  onNoteIdsChange,
  notebookId,
  disabled = false,
}: SourcesPopoverSelectorProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [notes, setNotes] = useState<any[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [hasAutoSelected, setHasAutoSelected] = useState(false);

  // Use notebook-specific sources if notebookId is provided, otherwise all sources
  const notebookSourcesQuery = useNotebookSources(notebookId || "");
  const allSourcesQuery = useQuery({
    queryKey: ["sources"],
    queryFn: async () => {
      const { data } = await apiClient.get("/sources");
      return data;
    },
    enabled: !notebookId,
  });

  const sources = notebookId ? (notebookSourcesQuery.data || []) : (allSourcesQuery.data || []);
  const isLoading = notebookId ? notebookSourcesQuery.isLoading : allSourcesQuery.isLoading;

  // Fetch notes when notebook is selected
  useEffect(() => {
    if (notebookId) {
      setNotesLoading(true);
      fetch(`/api/notes?notebook_id=${notebookId}`)
        .then(res => res.json())
        .then(data => {
          setNotes(data);
          setNotesLoading(false);
          if (onNoteIdsChange) {
            const noteIds = data.map((n: any) => n.id);
            onNoteIdsChange(noteIds);
          }
        })
        .catch(err => {
          console.error('Failed to load notes:', err);
          setNotesLoading(false);
        });
    } else {
      setNotes([]);
      if (onNoteIdsChange) {
        onNoteIdsChange([]);
      }
    }
  }, [notebookId, onNoteIdsChange]);

  // Auto-select all sources and notes when they first load
  useEffect(() => {
    if ((sources.length > 0 || notes.length > 0) && selectedSources.length === 0 && !hasAutoSelected) {
      const allIds = [
        ...sources.map((s: Source) => s.id),
        ...notes.map((n: any) => n.id)
      ];
      onSelectionChange(allIds);
      setHasAutoSelected(true);
    }
  }, [sources, notes, selectedSources.length, onSelectionChange, hasAutoSelected]);

  const filteredSources = sources.filter((source: Source) =>
    source.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredNotes = notes.filter((note: any) =>
    note.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleSource = (sourceId: string) => {
    if (disabled) return;
    if (selectedSources.includes(sourceId)) {
      onSelectionChange(selectedSources.filter((id) => id !== sourceId));
    } else {
      onSelectionChange([...selectedSources, sourceId]);
    }
  };

  const selectAll = () => {
    if (disabled) return;
    const allIds = [
      ...filteredSources.map((s: Source) => s.id),
      ...filteredNotes.map((n: any) => n.id)
    ];
    onSelectionChange(allIds);
  };

  const deselectAll = () => {
    if (disabled) return;
    onSelectionChange([]);
  };

  const totalItems = sources.length + notes.length;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          disabled={disabled}
          className="h-8 w-8 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 relative"
          title={`Sources (${selectedSources.length} selected)`}
        >
          <FileText className="w-4 h-4 text-gray-600 dark:text-gray-400" />
          {selectedSources.length > 0 && (
            <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-blue-500 text-white text-[10px] font-medium flex items-center justify-center">
              {selectedSources.length}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700" align="start">
        <div className="flex items-center justify-between p-3 border-b">
          <div className="flex items-center gap-2">
            <Folder className="w-4 h-4" />
            <span className="text-sm font-medium">Context Sources</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={selectAll}
              disabled={disabled}
              className="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400"
            >
              All
            </button>
            <span className="text-xs text-gray-400">|</span>
            <button
              onClick={deselectAll}
              disabled={disabled}
              className="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400"
            >
              None
            </button>
          </div>
        </div>

        <div className="p-3 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="Search sources..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 h-8 text-sm"
            />
          </div>
        </div>

        {isLoading || notesLoading ? (
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-gray-500">Loading...</p>
          </div>
        ) : totalItems === 0 ? (
          <div className="p-3 text-sm text-gray-500">
            {notebookId ? "No sources or notes in this workspace" : "No sources available"}
          </div>
        ) : (
          <>
            <div className="px-3 py-2 text-xs text-gray-500">
              {selectedSources.length} of {totalItems} selected
            </div>
            <ScrollArea className="h-[400px]">
              <div className="space-y-2 p-3">
                {/* Final Deliverable Note (if exists) */}
                {filteredNotes?.filter((note: any) => note.title.includes("🎯 FINAL DELIVERABLE") || note.title.includes("FINAL DELIVERABLE")).map((note: any) => (
                  <div
                    key={note.id}
                    className={`flex items-start space-x-2 p-2 rounded-lg border transition-all ${
                      selectedSources.includes(note.id)
                        ? "border-purple-500 bg-purple-50 dark:bg-purple-950"
                        : "border-purple-300 bg-purple-50/50 hover:border-purple-400"
                    } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                    onClick={() => toggleSource(note.id)}
                  >
                    <Checkbox
                      id={`source-popover-${note.id}`}
                      checked={selectedSources.includes(note.id)}
                      onCheckedChange={() => toggleSource(note.id)}
                      disabled={disabled}
                    />
                    <Sparkles className="w-4 h-4 text-purple-600 flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <label
                        htmlFor={`source-popover-${note.id}`}
                        className="text-xs font-semibold cursor-pointer block line-clamp-1"
                      >
                        {note.title}
                      </label>
                      <Badge className="mt-1 bg-purple-600 text-white text-xs h-4 px-1">
                        FINAL
                      </Badge>
                    </div>
                  </div>
                ))}

                {/* Regular Notes */}
                {filteredNotes?.filter((note: any) => !note.title.includes("FINAL DELIVERABLE")).length > 0 && (
                  <>
                    {filteredNotes.filter((note: any) => note.title.includes("FINAL DELIVERABLE")).length > 0 && (
                      <div className="flex items-center gap-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 mt-2 mb-1 px-1">
                        <FileText className="w-3 h-3" />
                        <span>Notes</span>
                      </div>
                    )}
                    {filteredNotes.filter((note: any) => !note.title.includes("FINAL DELIVERABLE")).map((note: any) => (
                      <div
                        key={note.id}
                        className={`flex items-start space-x-2 p-2 rounded-md ${
                          selectedSources.includes(note.id)
                            ? "bg-blue-50 dark:bg-blue-950"
                            : "hover:bg-gray-50 dark:hover:bg-gray-800"
                        } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                        onClick={() => toggleSource(note.id)}
                      >
                        <Checkbox
                          id={`source-popover-${note.id}`}
                          checked={selectedSources.includes(note.id)}
                          onCheckedChange={() => toggleSource(note.id)}
                          disabled={disabled}
                        />
                        <FileText className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <label
                            htmlFor={`source-popover-${note.id}`}
                            className="text-xs font-medium cursor-pointer block line-clamp-2"
                          >
                            {note.title}
                          </label>
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {/* Data Sources */}
                {filteredSources.length > 0 && (
                  <>
                    {filteredNotes.length > 0 && (
                      <div className="flex items-center gap-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 mt-2 mb-1 px-1">
                        <span>Data Sources</span>
                      </div>
                    )}
                    {filteredSources.map((source: Source) => (
                      <div
                        key={source.id}
                        className={`flex items-start space-x-2 p-2 rounded-md ${
                          selectedSources.includes(source.id)
                            ? "bg-blue-50 dark:bg-blue-950"
                            : "hover:bg-gray-50 dark:hover:bg-gray-800"
                        } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                        onClick={() => toggleSource(source.id)}
                      >
                        <Checkbox
                          id={`source-popover-${source.id}`}
                          checked={selectedSources.includes(source.id)}
                          onCheckedChange={() => toggleSource(source.id)}
                          disabled={disabled}
                        />
                        <div className="flex-1 min-w-0">
                          <label
                            htmlFor={`source-popover-${source.id}`}
                            className="text-xs font-medium cursor-pointer block line-clamp-2"
                          >
                            {source.title}
                          </label>
                          <div className="flex items-center gap-1.5 mt-1">
                            <p className="text-xs text-gray-500">{source.source_type}</p>
                            {source.chunk_count && source.chunk_count > 0 && (
                              <Badge variant="outline" className="text-xs h-4 px-1">
                                {source.chunk_count}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {(filteredSources.length === 0 && filteredNotes.length === 0) && searchQuery && (
                  <div className="flex flex-col items-center justify-center py-8">
                    <FileText className="w-8 h-8 text-gray-400 mb-2" />
                    <p className="text-xs text-gray-500 text-center">
                      No sources or notes found
                    </p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
