"use client";

import { FileText, Link, Type, Youtube, Database, Plug } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { SourceType } from "@/lib/types";

interface SourceTypeSelectorProps {
  selected: SourceType;
  onSelect: (type: SourceType) => void;
}

const sourceTypes = [
  {
    type: "file" as const,
    icon: FileText,
    label: "File Upload",
    description: "Upload PDF, Word, or other documents",
  },
  {
    type: "url" as const,
    icon: Link,
    label: "Web URL",
    description: "Import content from a web page",
  },
  {
    type: "text" as const,
    icon: Type,
    label: "Text",
    description: "Paste or type text directly",
  },
  {
    type: "youtube" as const,
    icon: Youtube,
    label: "YouTube",
    description: "Import from YouTube video",
  },
  {
    type: "hana_table" as const,
    icon: Database,
    label: "HANA Table",
    description: "Connect to SAP HANA database table",
  },
  {
    type: "api" as const,
    icon: Plug,
    label: "API",
    description: "Connect to authenticated REST API",
  },
];

export function SourceTypeSelector({ selected, onSelect }: SourceTypeSelectorProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {sourceTypes.map(({ type, icon: Icon, label, description }) => (
        <Card
          key={type}
          className={cn(
            "cursor-pointer transition-all hover:shadow-md",
            selected === type
              ? "border-primary-600 ring-2 ring-primary-600 ring-opacity-50"
              : "hover:border-gray-400"
          )}
          onClick={() => onSelect(type)}
        >
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div
                className={cn(
                  "p-3 rounded-lg",
                  selected === type
                    ? "bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300"
                    : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                )}
              >
                <Icon className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg mb-1">{label}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
