"use client";

import * as React from "react";
import {
  Search,
  FileText,
  Globe,
  Type,
  Youtube,
  Database,
  Plug,
  Eye,
  EyeOff,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import {
  useSourceGraphStore,
  useGraphFilters,
  useGraphMetadata,
} from "@/lib/stores/source-graph-store";
import type { SourceType } from "@/lib/types";
import type { EdgeType } from "@/lib/api/graph";
import { workspacesApi } from "@/lib/api/workspaces";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SOURCE_TYPE_CONFIG: Record<
  SourceType,
  { label: string; icon: React.ElementType }
> = {
  file: { label: "File", icon: FileText },
  url: { label: "URL", icon: Globe },
  text: { label: "Text", icon: Type },
  youtube: { label: "YouTube", icon: Youtube },
  hana_table: { label: "HANA Table", icon: Database },
  api: { label: "API", icon: Plug },
};

const EDGE_TYPE_CONFIG: Record<EdgeType, { label: string; color: string }> = {
  semantic: { label: "Semantic", color: "#8b5cf6" },
  notebook: { label: "Notebook", color: "#3b82f6" },
  topic: { label: "Topic", color: "#14b8a6" },
  note_link: { label: "Note Link", color: "#6366f1" },
  hana_schema: { label: "HANA Schema", color: "#f59e0b" },
  api_relation: { label: "API Relation", color: "#ef4444" },
};

const ALL_SOURCE_TYPES: SourceType[] = [
  "file",
  "url",
  "text",
  "youtube",
  "hana_table",
  "api",
];

const ALL_EDGE_TYPES: EdgeType[] = [
  "semantic",
  "notebook",
  "topic",
  "note_link",
  "hana_schema",
  "api_relation",
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface GraphSidebarProps {
  className?: string;
  onCollapsedChange?: (collapsed: boolean) => void;
}

// ---------------------------------------------------------------------------
// Debounce hook
// ---------------------------------------------------------------------------

function useDebouncedCallback<T extends (...args: any[]) => void>(
  callback: T,
  delay: number,
) {
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return React.useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => callback(...args), delay);
    },
    [callback, delay],
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const GraphSidebar = React.memo(function GraphSidebar({ className, onCollapsedChange }: GraphSidebarProps) {
  const filters = useGraphFilters();
  const metadata = useGraphMetadata();
  const updateFilters = useSourceGraphStore((s) => s.updateFilters);

  // Debounced filter updates to avoid excessive re-renders/re-fetches
  const debouncedUpdateFilters = useDebouncedCallback(
    (partial: Parameters<typeof updateFilters>[0]) => updateFilters(partial),
    300,
  );

  // Local UI state
  const [collapsed, setCollapsed] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [tagInput, setTagInput] = React.useState("");
  const [notebookSearch, setNotebookSearch] = React.useState("");

  // Notify parent when collapsed state changes
  React.useEffect(() => {
    onCollapsedChange?.(collapsed);
  }, [collapsed, onCollapsedChange]);

  // Fetch notebooks for multi-select
  const { data: notebooks = [] } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => workspacesApi.list(),
    staleTime: 60_000,
  });

  // Collect unique tags from notebooks
  const availableTags = React.useMemo(() => {
    const tagSet = new Set<string>();
    notebooks.forEach((nb) => nb.tags?.forEach((t) => tagSet.add(t)));
    return Array.from(tagSet).sort();
  }, [notebooks]);

  // Debounced search -- filters sources client-side via node label matching
  // (the store doesn't have a searchQuery field, so this is handled via
  //  node visibility in the parent canvas; we emit a custom event)
  const debouncedSearch = useDebouncedCallback((value: string) => {
    window.dispatchEvent(
      new CustomEvent("graph:search", { detail: value }),
    );
  }, 300);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
    debouncedSearch(value);
  };

  // Toggle helpers (debounced to avoid excessive re-renders)
  const toggleSourceType = (type: SourceType) => {
    const current = filters.sourceTypes;
    const next = current.includes(type)
      ? current.filter((t) => t !== type)
      : [...current, type];
    debouncedUpdateFilters({ sourceTypes: next });
  };

  const toggleEdgeType = (type: EdgeType) => {
    const current = filters.edgeTypes;
    const next = current.includes(type)
      ? current.filter((t) => t !== type)
      : [...current, type];
    debouncedUpdateFilters({ edgeTypes: next });
  };

  const toggleNotebook = (id: string) => {
    const current = filters.notebookIds;
    const next = current.includes(id)
      ? current.filter((n) => n !== id)
      : [...current, id];
    debouncedUpdateFilters({ notebookIds: next });
  };

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !filters.tags.includes(trimmed)) {
      debouncedUpdateFilters({ tags: [...filters.tags, trimmed] });
    }
    setTagInput("");
  };

  const removeTag = (tag: string) => {
    debouncedUpdateFilters({ tags: filters.tags.filter((t) => t !== tag) });
  };

  // Filtered notebooks for search
  const filteredNotebooks = React.useMemo(() => {
    if (!notebookSearch) return notebooks;
    const q = notebookSearch.toLowerCase();
    return notebooks.filter((n) => n.name.toLowerCase().includes(q));
  }, [notebooks, notebookSearch]);

  // Tag suggestions
  const tagSuggestions = React.useMemo(() => {
    if (!tagInput) return [];
    const q = tagInput.toLowerCase();
    return availableTags
      .filter((t) => t.toLowerCase().includes(q) && !filters.tags.includes(t))
      .slice(0, 8);
  }, [tagInput, availableTags, filters.tags]);

  // Counts from metadata
  const sourceTypeCounts = metadata.source_type_counts;
  const edgeTypeCounts = metadata.edge_type_counts;

  if (collapsed) {
    return (
      <div
        className={cn(
          "flex flex-col items-center border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 py-2 transition-all duration-200 ease-in-out",
          className,
        )}
        style={{ width: '48px' }}
      >
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed(false)}
          className="h-8 w-8"
          title="Show filters"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col w-72 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 transition-all duration-200 ease-in-out",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-800">
        <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          Filters
        </span>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed(true)}
          className="h-7 w-7"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="px-3 pb-4">
          <Accordion
            type="multiple"
            defaultValue={[
              "search",
              "source-types",
              "edge-types",
              "threshold",
            ]}
            className="w-full"
          >
            {/* 1. Search */}
            <AccordionItem value="search">
              <AccordionTrigger className="py-3 text-sm">
                <div className="flex items-center gap-2">
                  <Search className="h-4 w-4 text-gray-500" />
                  Search
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <Input
                  placeholder="Search sources..."
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="h-8 text-sm"
                />
              </AccordionContent>
            </AccordionItem>

            {/* 2. Source Types */}
            <AccordionItem value="source-types">
              <AccordionTrigger className="py-3 text-sm">
                Source Types
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  {ALL_SOURCE_TYPES.map((type) => {
                    const cfg = SOURCE_TYPE_CONFIG[type];
                    const Icon = cfg.icon;
                    const count = sourceTypeCounts[type] ?? 0;
                    return (
                      <label
                        key={type}
                        className="flex items-center gap-2 cursor-pointer"
                      >
                        <Checkbox
                          checked={filters.sourceTypes.includes(type)}
                          onCheckedChange={() => toggleSourceType(type)}
                        />
                        <Icon className="h-3.5 w-3.5 text-gray-500" />
                        <span className="text-sm flex-1">{cfg.label}</span>
                        <Badge
                          variant="secondary"
                          className="h-5 min-w-[1.5rem] justify-center text-xs px-1.5"
                        >
                          {count}
                        </Badge>
                      </label>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 3. Edge Types */}
            <AccordionItem value="edge-types">
              <AccordionTrigger className="py-3 text-sm">
                Edge Types
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  {ALL_EDGE_TYPES.map((type) => {
                    const cfg = EDGE_TYPE_CONFIG[type];
                    const count = edgeTypeCounts[type] ?? 0;
                    return (
                      <label
                        key={type}
                        className="flex items-center gap-2 cursor-pointer"
                      >
                        <Checkbox
                          checked={filters.edgeTypes.includes(type)}
                          onCheckedChange={() => toggleEdgeType(type)}
                        />
                        <span
                          className="h-2.5 w-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: cfg.color }}
                        />
                        <span className="text-sm flex-1">{cfg.label}</span>
                        <Badge
                          variant="secondary"
                          className="h-5 min-w-[1.5rem] justify-center text-xs px-1.5"
                        >
                          {count}
                        </Badge>
                      </label>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 4. Semantic Threshold */}
            <AccordionItem value="threshold">
              <AccordionTrigger className="py-3 text-sm">
                Semantic Threshold
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-3">
                  <Slider
                    value={[filters.semanticThreshold]}
                    min={0.7}
                    max={1.0}
                    step={0.05}
                    onValueChange={([val]) =>
                      debouncedUpdateFilters({ semanticThreshold: val })
                    }
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>0.70</span>
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      {filters.semanticThreshold.toFixed(2)}
                    </span>
                    <span>1.00</span>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 5. Notebooks */}
            <AccordionItem value="notebooks">
              <AccordionTrigger className="py-3 text-sm">
                Notebooks
                {filters.notebookIds.length > 0 && (
                  <Badge
                    variant="secondary"
                    className="ml-2 h-5 text-xs px-1.5"
                  >
                    {filters.notebookIds.length}
                  </Badge>
                )}
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  <Input
                    placeholder="Search notebooks..."
                    value={notebookSearch}
                    onChange={(e) => setNotebookSearch(e.target.value)}
                    className="h-8 text-sm"
                  />
                  <div className="max-h-36 overflow-y-auto space-y-1">
                    {filteredNotebooks.length === 0 ? (
                      <p className="text-xs text-gray-400 py-1">
                        No notebooks found
                      </p>
                    ) : (
                      filteredNotebooks.map((nb) => (
                        <label
                          key={nb.id}
                          className="flex items-center gap-2 cursor-pointer"
                        >
                          <Checkbox
                            checked={filters.notebookIds.includes(nb.id)}
                            onCheckedChange={() => toggleNotebook(nb.id)}
                          />
                          <span className="text-sm truncate">{nb.name}</span>
                        </label>
                      ))
                    )}
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 6. Tags */}
            <AccordionItem value="tags">
              <AccordionTrigger className="py-3 text-sm">
                Tags
                {filters.tags.length > 0 && (
                  <Badge
                    variant="secondary"
                    className="ml-2 h-5 text-xs px-1.5"
                  >
                    {filters.tags.length}
                  </Badge>
                )}
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  <div className="relative">
                    <Input
                      placeholder="Add tag..."
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addTag(tagInput);
                        }
                      }}
                      className="h-8 text-sm"
                    />
                    {tagSuggestions.length > 0 && (
                      <div className="absolute top-full left-0 right-0 z-10 mt-1 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-md">
                        {tagSuggestions.map((t) => (
                          <button
                            key={t}
                            type="button"
                            className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
                            onClick={() => addTag(t)}
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  {filters.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {filters.tags.map((tag) => (
                        <Badge
                          key={tag}
                          variant="outline"
                          className="cursor-pointer text-xs"
                          onClick={() => removeTag(tag)}
                        >
                          {tag} &times;
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 7. Date Range */}
            <AccordionItem value="date-range">
              <AccordionTrigger className="py-3 text-sm">
                Date Range
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  <div>
                    <Label className="text-xs text-gray-500">From</Label>
                    <Input
                      type="date"
                      value={
                        filters.dateRange.from
                          ? filters.dateRange.from
                              .toISOString()
                              .split("T")[0]
                          : ""
                      }
                      onChange={(e) => {
                        const val = e.target.value;
                        debouncedUpdateFilters({
                          dateRange: {
                            ...filters.dateRange,
                            from: val ? new Date(val) : null,
                          },
                        });
                      }}
                      className="h-8 text-sm"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-gray-500">To</Label>
                    <Input
                      type="date"
                      value={
                        filters.dateRange.to
                          ? filters.dateRange.to.toISOString().split("T")[0]
                          : ""
                      }
                      onChange={(e) => {
                        const val = e.target.value;
                        debouncedUpdateFilters({
                          dateRange: {
                            ...filters.dateRange,
                            to: val ? new Date(val) : null,
                          },
                        });
                      }}
                      className="h-8 text-sm"
                    />
                  </div>
                  {(filters.dateRange.from || filters.dateRange.to) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() =>
                        debouncedUpdateFilters({
                          dateRange: { from: null, to: null },
                        })
                      }
                    >
                      Clear dates
                    </Button>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 8. Show Options */}
            <AccordionItem value="show-options">
              <AccordionTrigger className="py-3 text-sm">
                Show Options
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <Checkbox
                      checked={filters.showIsolated}
                      onCheckedChange={(checked) =>
                        debouncedUpdateFilters({ showIsolated: checked === true })
                      }
                    />
                    <EyeOff className="h-3.5 w-3.5 text-gray-500" />
                    <span className="text-sm">Show isolated nodes</span>
                  </label>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </ScrollArea>
    </div>
  );
});
