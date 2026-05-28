"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNotebookSources } from "@/lib/hooks/use-api";
import { apiClient } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, FileText, CheckSquare, Square, Sparkles } from "lucide-react";
import type { Source } from "@/lib/types";

interface ContextSelectorProps {
  selectedSources: string[];
  onSelectionChange: (sourceIds: string[]) => void;
  onNoteIdsChange?: (noteIds: string[]) => void;
  notebookId?: string;
}

export function ContextSelector({
  selectedSources,
  onSelectionChange,
  onNoteIdsChange,
  notebookId,
}: ContextSelectorProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [notes, setNotes] = useState<any[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);

  // Debug logging
  console.log("[ContextSelector] notebookId:", notebookId);

  // Use notebook-specific sources if notebookId is provided, otherwise all sources
  const notebookSourcesQuery = useNotebookSources(notebookId || "");
  const allSourcesQuery = useQuery({
    queryKey: ["sources"],
    queryFn: async () => {
      const { data } = await apiClient.get("/sources");
      return data;
    },
    enabled: !notebookId, // Only fetch all sources if no notebookId
  });

  const sources = notebookId ? (notebookSourcesQuery.data || []) : (allSourcesQuery.data || []);
  const isLoading = notebookId ? notebookSourcesQuery.isLoading : allSourcesQuery.isLoading;

  console.log("[ContextSelector] Using notebook sources:", notebookId ? true : false);
  console.log("[ContextSelector] Sources count:", sources.length);
  console.log("[ContextSelector] Sources:", sources);

  // Fetch notes when notebook is selected
  useEffect(() => {
    console.log("[ContextSelector] Notes fetch effect triggered:", { notebookId, hasCallback: !!onNoteIdsChange });
    if (notebookId) {
      setNotesLoading(true);
      fetch(`/api/notes?notebook_id=${notebookId}`)
        .then(res => res.json())
        .then(data => {
          console.log("[ContextSelector] Notes loaded:", data.length, "notes");
          console.log("[ContextSelector] Note IDs:", data.map((n: any) => n.id));
          setNotes(data);
          setNotesLoading(false);
          // Notify parent of note IDs
          if (onNoteIdsChange) {
            const noteIds = data.map((n: any) => n.id);
            console.log("[ContextSelector] Calling onNoteIdsChange with:", noteIds);
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
        console.log("[ContextSelector] Clearing note IDs (no notebook)");
        onNoteIdsChange([]);
      }
    }
  }, [notebookId, onNoteIdsChange]);

  // Auto-select all sources and notes when they first load (only once)
  const [hasAutoSelected, setHasAutoSelected] = useState(false);

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
    if (selectedSources.includes(sourceId)) {
      onSelectionChange(selectedSources.filter((id) => id !== sourceId));
    } else {
      onSelectionChange([...selectedSources, sourceId]);
    }
  };

  const selectAll = () => {
    const allIds = [
      ...filteredSources.map((s: Source) => s.id),
      ...filteredNotes.map((n: any) => n.id)
    ];
    onSelectionChange(allIds);
  };

  const deselectAll = () => {
    onSelectionChange([]);
  };

  const allSelected = (filteredSources.length + filteredNotes.length) > 0 &&
    [...filteredSources, ...filteredNotes].every((item: any) => selectedSources.includes(item.id));

  const totalItems = sources.length + notes.length;

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">Context Sources</CardTitle>
            <CardDescription>
              {selectedSources.length > 0
                ? `${selectedSources.length} of ${totalItems} source(s) selected for context`
                : "No sources selected - chat will work without context"}
            </CardDescription>
          </div>
          {(filteredSources.length + filteredNotes.length) > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={allSelected ? deselectAll : selectAll}
              className="text-xs flex-shrink-0 hover:bg-gray-100 dark:hover:bg-gray-800"
              type="button"
            >
              {allSelected ? (
                <>
                  <Square className="w-3 h-3 mr-1" />
                  Deselect All
                </>
              ) : (
                <>
                  <CheckSquare className="w-3 h-3 mr-1" />
                  Select All
                </>
              )}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search sources..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Selection count */}
        {selectedSources.length > 0 && (
          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              {selectedSources.length} selected
            </Badge>
            {selectedSources.length < sources.length && (
              <span className="text-xs text-gray-500">
                ({sources.length - selectedSources.length} excluded)
              </span>
            )}
          </div>
        )}

        {/* Sources and Notes list */}
        <ScrollArea className="h-[400px]">
          {isLoading || notesLoading ? (
            <div className="flex items-center justify-center py-8">
              <p className="text-sm text-gray-500">Loading...</p>
            </div>
          ) : (filteredNotes.length + filteredSources.length) > 0 ? (
            <div className="space-y-4">
              {/* Final Deliverable Note (if exists) */}
              {filteredNotes?.filter((note: any) => note.title.includes("🎯 FINAL DELIVERABLE") || note.title.includes("FINAL DELIVERABLE")).map((note: any) => (
                <div
                  key={note.id}
                  className={`flex items-start space-x-3 p-4 rounded-lg border-2 transition-all ${
                    selectedSources.includes(note.id)
                      ? "border-purple-500 bg-gradient-to-br from-purple-50 to-indigo-50"
                      : "border-purple-300 bg-purple-50/50 hover:border-purple-400"
                  }`}
                >
                  <Checkbox
                    id={note.id}
                    checked={selectedSources.includes(note.id)}
                    onCheckedChange={() => toggleSource(note.id)}
                  />
                  <Sparkles className="w-5 h-5 text-purple-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <label
                      htmlFor={note.id}
                      className="text-sm font-semibold cursor-pointer block"
                    >
                      {note.title}
                    </label>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs">
                        FINAL
                      </Badge>
                      <p className="text-xs text-purple-700">
                        ⚡ Comprehensive AI analysis
                      </p>
                    </div>
                  </div>
                </div>
              ))}

              {/* Regular Notes */}
              {filteredNotes?.filter((note: any) => !note.title.includes("FINAL DELIVERABLE")).length > 0 && (
                <>
                  {filteredNotes.filter((note: any) => note.title.includes("FINAL DELIVERABLE")).length > 0 && (
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground mt-2">
                      <FileText className="w-4 h-4" />
                      <span>Notes</span>
                    </div>
                  )}
                  {filteredNotes.filter((note: any) => !note.title.includes("FINAL DELIVERABLE")).map((note: any) => (
                    <div
                      key={note.id}
                      className={`flex items-start space-x-3 p-3 rounded-md ${
                        selectedSources.includes(note.id)
                          ? "bg-primary/5 border border-primary"
                          : "hover:bg-gray-50 dark:hover:bg-gray-800"
                      }`}
                    >
                      <Checkbox
                        id={note.id}
                        checked={selectedSources.includes(note.id)}
                        onCheckedChange={() => toggleSource(note.id)}
                      />
                      <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <label
                          htmlFor={note.id}
                          className="text-sm font-medium cursor-pointer block truncate"
                        >
                          {note.title}
                        </label>
                        <p className="text-xs text-gray-500 mt-1">Note</p>
                      </div>
                    </div>
                  ))}
                </>
              )}

              {/* Data Sources */}
              {filteredSources.length > 0 && (
                <>
                  {(filteredNotes.length > 0) && (
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground mt-2">
                      <span>Data Sources</span>
                    </div>
                  )}
                  {filteredSources.map((source: Source) => (
                    <div
                      key={source.id}
                      className={`flex items-start space-x-3 p-3 rounded-md ${
                        selectedSources.includes(source.id)
                          ? "bg-primary/5 border border-primary"
                          : "hover:bg-gray-50 dark:hover:bg-gray-800"
                      }`}
                    >
                      <Checkbox
                        id={source.id}
                        checked={selectedSources.includes(source.id)}
                        onCheckedChange={() => toggleSource(source.id)}
                      />
                      <div className="flex-1 min-w-0">
                        <label
                          htmlFor={source.id}
                          className="text-sm font-medium cursor-pointer block truncate"
                        >
                          {source.title}
                        </label>
                        <div className="flex items-center gap-2 mt-1">
                          <p className="text-xs text-gray-500">{source.source_type}</p>
                          {source.chunk_count && source.chunk_count > 0 && (
                            <Badge variant="outline" className="text-xs">
                              {source.chunk_count} chunks
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8">
              <FileText className="w-12 h-12 text-gray-400 mb-3" />
              <p className="text-sm text-gray-500 text-center">
                {searchQuery ? "No sources or notes found" : notebookId ? "No sources or notes in this workspace" : "No sources available"}
              </p>
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
