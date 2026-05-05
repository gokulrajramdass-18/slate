"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  FileText,
  BookOpen,
  Briefcase,
  Rocket,
  BarChart3,
  ExternalLink,
  Check,
} from "lucide-react";
import type { MicrositeTemplate } from "@/lib/types";

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  blog: <FileText className="w-5 h-5" />,
  documentation: <BookOpen className="w-5 h-5" />,
  portfolio: <Briefcase className="w-5 h-5" />,
  landing: <Rocket className="w-5 h-5" />,
  report: <BarChart3 className="w-5 h-5" />,
};

const CATEGORY_COLORS: Record<string, string> = {
  blog: "bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800",
  documentation: "bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800",
  portfolio: "bg-purple-50 border-purple-200 dark:bg-purple-950 dark:border-purple-800",
  landing: "bg-orange-50 border-orange-200 dark:bg-orange-950 dark:border-orange-800",
  report: "bg-gray-50 border-gray-200 dark:bg-gray-950 dark:border-gray-800",
};

interface TemplateSelectorProps {
  templates: MicrositeTemplate[];
  selectedId: string | null;
  onSelect: (template: MicrositeTemplate) => void;
  isLoading?: boolean;
}

export function TemplateSelector({
  templates,
  selectedId,
  onSelect,
  isLoading,
}: TemplateSelectorProps) {
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  const categories = useMemo(() => {
    const cats = new Set(templates.map((t) => t.name));
    return ["all", ...Array.from(cats)];
  }, [templates]);

  const filtered = useMemo(() => {
    return templates.filter((t) => {
      if (filter !== "all" && t.name !== filter) return false;
      if (search && !t.display_name.toLowerCase().includes(search.toLowerCase()) &&
          !t.description.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [templates, filter, search]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="h-48 rounded-lg border border-gray-200 dark:border-gray-800 animate-pulse bg-gray-100 dark:bg-gray-900"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3">
        <Input
          placeholder="Search templates..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="sm:max-w-xs"
        />
        <div className="flex gap-2 flex-wrap">
          {categories.map((cat) => (
            <Button
              key={cat}
              variant={filter === cat ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter(cat)}
              className="capitalize"
            >
              {cat === "all" ? "All" : cat}
            </Button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((template) => {
          const isSelected = selectedId === template.id;
          return (
            <Card
              key={template.id}
              className={`cursor-pointer transition-all hover:shadow-md ${
                isSelected
                  ? "ring-2 ring-primary border-primary"
                  : ""
              } ${CATEGORY_COLORS[template.name] || ""}`}
              onClick={() => onSelect(template)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {CATEGORY_ICONS[template.name]}
                    <CardTitle className="text-base">
                      {template.display_name}
                    </CardTitle>
                  </div>
                  {isSelected && (
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                      <Check className="w-4 h-4 text-primary-foreground" />
                    </div>
                  )}
                </div>
                <CardDescription className="text-xs">
                  {template.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center justify-between">
                  <Badge variant="secondary" className="capitalize text-xs">
                    {template.display_name}
                  </Badge>
                  {template.preview_image && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        window.open(template.preview_image, "_blank");
                      }}
                    >
                      <ExternalLink className="w-3 h-3 mr-1" />
                      Preview
                    </Button>
                  )}
                </div>
                {template.structure?.styles && (
                  <div className="flex gap-1 mt-3">
                    <div
                      className="w-4 h-4 rounded-full border"
                      style={{
                        backgroundColor: template.structure.styles.primary_color,
                      }}
                      title={`Primary: ${template.structure.styles.primary_color}`}
                    />
                    <span className="text-xs text-muted-foreground ml-1">
                      {template.structure.styles.font_heading}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          No templates match your search.
        </div>
      )}
    </div>
  );
}
