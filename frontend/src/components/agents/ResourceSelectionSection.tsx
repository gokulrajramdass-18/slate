"use client";

import { useState } from "react";
import { Search, Loader2, AlertCircle } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ResourceItem {
  id: string;
  name: string;
  description?: string;
  badge?: string;
}

interface ResourceSelectionSectionProps {
  type: "tools" | "datasources" | "skills" | "mcp";
  items: ResourceItem[];
  selectedIds: string[];
  onSelect: (id: string) => void;
  onDeselect: (id: string) => void;
  loading?: boolean;
  error?: Error | null;
  /** Hide the header row — useful when the surrounding container (e.g. a tab label) already shows the title and count. */
  hideHeader?: boolean;
  /** Override the scroll-area height. Defaults to 240px to preserve current behavior. */
  listHeight?: number;
}

const TYPE_CONFIG = {
  tools: {
    title: "Tools",
    searchPlaceholder: "Search tools...",
    emptyMessage: "No tools available",
    noResultsMessage: "No tools found",
  },
  datasources: {
    title: "Data Sources",
    searchPlaceholder: "Search data sources...",
    emptyMessage: "No data sources available",
    noResultsMessage: "No data sources found",
  },
  skills: {
    title: "Skills",
    searchPlaceholder: "Search skills...",
    emptyMessage: "No skills available",
    noResultsMessage: "No skills found",
  },
  mcp: {
    title: "MCP Servers",
    searchPlaceholder: "Search MCP servers...",
    emptyMessage: "No MCP servers available",
    noResultsMessage: "No MCP servers found",
  },
};

export function ResourceSelectionSection({
  type,
  items,
  selectedIds,
  onSelect,
  onDeselect,
  loading = false,
  error = null,
  hideHeader = false,
  listHeight = 240,
}: ResourceSelectionSectionProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const config = TYPE_CONFIG[type];

  const filteredItems = items.filter((item) => {
    const query = searchQuery.toLowerCase();
    return (
      item.name.toLowerCase().includes(query) ||
      item.description?.toLowerCase().includes(query) ||
      false
    );
  });

  const handleToggle = (id: string) => {
    if (selectedIds.includes(id)) {
      onDeselect(id);
    } else {
      onSelect(id);
    }
  };

  return (
    <div className="space-y-3">
      {/* Header (hidden when caller already renders one) */}
      {!hideHeader && (
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">
            {config.title}{" "}
            <span className="text-muted-foreground">
              ({selectedIds.length} selected)
            </span>
          </Label>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={config.searchPlaceholder}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* List */}
      <div className="border rounded-lg">
        <ScrollArea style={{ height: listHeight }}>
          <div className="p-2">
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-32 text-center">
                <AlertCircle className="h-8 w-8 text-destructive mb-2" />
                <p className="text-sm text-muted-foreground">
                  Error loading {config.title.toLowerCase()}
                </p>
              </div>
            ) : items.length === 0 ? (
              <div className="flex items-center justify-center h-32">
                <p className="text-sm text-muted-foreground">
                  {config.emptyMessage}
                </p>
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="flex items-center justify-center h-32">
                <p className="text-sm text-muted-foreground">
                  {config.noResultsMessage}
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {filteredItems.map((item) => {
                  const isSelected = selectedIds.includes(item.id);
                  return (
                    <div
                      key={item.id}
                      className={`p-3 rounded-lg cursor-pointer transition-all hover:bg-accent ${
                        isSelected ? "bg-accent/50 border border-primary/30" : ""
                      }`}
                      onClick={() => handleToggle(item.id)}
                    >
                      <div className="flex items-start gap-3">
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => handleToggle(item.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-0.5"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <h4 className="text-sm font-medium leading-tight">
                                {item.name}
                              </h4>
                              {item.description && (
                                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                  {item.description}
                                </p>
                              )}
                            </div>
                            {item.badge && (
                              <Badge
                                variant="secondary"
                                className="text-xs shrink-0"
                              >
                                {item.badge}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
