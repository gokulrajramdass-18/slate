"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Filter, X } from "lucide-react";
import type { SearchRequest, SourceType } from "@/lib/types";

interface FilterPanelProps {
  filters: SearchRequest["filters"];
  onFiltersChange: (filters: SearchRequest["filters"]) => void;
  notebooks?: Array<{ id: string; name: string }>;
}

const sourceTypes: SourceType[] = ["file", "url", "text", "youtube"];

export function FilterPanel({ filters, onFiltersChange, notebooks }: FilterPanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  const hasActiveFilters =
    filters?.notebook_ids?.length || filters?.source_types?.length || filters?.date_from || filters?.date_to;

  const clearFilters = () => {
    onFiltersChange(undefined);
  };

  const updateFilter = (key: string, value: any) => {
    onFiltersChange({
      ...filters,
      [key]: value || undefined,
    });
  };

  if (!isOpen) {
    return (
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2"
        >
          <Filter className="w-4 h-4" />
          Filters
          {hasActiveFilters && (
            <span className="ml-1 px-1.5 py-0.5 text-xs bg-primary-100 text-primary-700 rounded-full">
              {Object.values(filters || {}).filter(Boolean).length}
            </span>
          )}
        </Button>
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            Clear all
          </Button>
        )}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-base flex items-center gap-2">
          <Filter className="w-4 h-4" />
          Filters
        </CardTitle>
        <Button variant="ghost" size="sm" onClick={() => setIsOpen(false)}>
          <X className="w-4 h-4" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Workspace Filter */}
        {notebooks && notebooks.length > 0 && (
          <div className="space-y-2">
            <Label htmlFor="notebook">Workspace</Label>
            <Select
              value={filters?.notebook_ids?.[0] || "all"}
              onValueChange={(value) => updateFilter("notebook_ids", value === "all" ? undefined : [value])}
            >
              <SelectTrigger id="notebook">
                <SelectValue placeholder="All workspaces" />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                <SelectItem value="all">All workspaces</SelectItem>
                {notebooks.map((notebook) => (
                  <SelectItem key={notebook.id} value={notebook.id}>
                    {notebook.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Source Type Filter */}
        <div className="space-y-2">
          <Label htmlFor="source-type">Source Type</Label>
          <Select
            value={filters?.source_types?.[0] || "all"}
            onValueChange={(value) => updateFilter("source_types", value === "all" ? undefined : [value])}
          >
            <SelectTrigger id="source-type">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
              <SelectItem value="all">All types</SelectItem>
              {sourceTypes.map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Date Range Filter */}
        <div className="space-y-2">
          <Label>Date Range</Label>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Input
                type="date"
                value={filters?.date_from || ""}
                onChange={(e) => updateFilter("date_from", e.target.value)}
                placeholder="From"
              />
            </div>
            <div>
              <Input
                type="date"
                value={filters?.date_to || ""}
                onChange={(e) => updateFilter("date_to", e.target.value)}
                placeholder="To"
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={clearFilters} className="flex-1">
            Clear
          </Button>
          <Button size="sm" onClick={() => setIsOpen(false)} className="flex-1">
            Apply
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
