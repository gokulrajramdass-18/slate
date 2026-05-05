"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { MessageSquare, FlaskConical, Workflow, Globe, Briefcase, Shield, Users, Bot } from "lucide-react";
import { SystemPromptEditor } from "./SystemPromptEditor";
import * as systemPromptsApi from "@/lib/api/system-prompts";

type Category = "chat" | "research" | "orchestration" | "microsite" | "guided_workspace" | "safety" | "agent_analysis" | "agent_roles";

const CATEGORY_INFO: Record<Category, { label: string; icon: React.ReactNode; description: string; count?: number }> = {
  chat: {
    label: "Chat",
    icon: <MessageSquare className="h-4 w-4" />,
    description: "Chat system messages with context and citations",
    count: 4,
  },
  research: {
    label: "Research",
    icon: <FlaskConical className="h-4 w-4" />,
    description: "Deep research agent phase prompts",
    count: 4,
  },
  orchestration: {
    label: "Orchestration",
    icon: <Workflow className="h-4 w-4" />,
    description: "Multi-agent orchestration and planning prompts",
    count: 6,
  },
  guided_workspace: {
    label: "Guided Workspace",
    icon: <Briefcase className="h-4 w-4" />,
    description: "AI-powered workspace creation wizard prompts",
    count: 5,
  },
  agent_analysis: {
    label: "Agent Analysis",
    icon: <Bot className="h-4 w-4" />,
    description: "Query analysis, planning, and synthesis prompts",
    count: 3,
  },
  agent_roles: {
    label: "Agent Roles",
    icon: <Users className="h-4 w-4" />,
    description: "System prompts for different agent roles",
    count: 4,
  },
  safety: {
    label: "Safety",
    icon: <Shield className="h-4 w-4" />,
    description: "Content moderation and safety prompts",
    count: 1,
  },
  microsite: {
    label: "Microsite",
    icon: <Globe className="h-4 w-4" />,
    description: "Microsite section generation prompts",
    count: 16,
  },
};

export function SystemPromptsManager() {
  const [selectedCategory, setSelectedCategory] = useState<Category>("chat");
  const [selectedKey, setSelectedKey] = useState<string>("");

  // Fetch templates for selected category
  const { data: templates, isLoading } = useQuery({
    queryKey: ["system-prompts", selectedCategory],
    queryFn: () => systemPromptsApi.listTemplates(selectedCategory),
  });

  // Auto-select first template when category changes
  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category as Category);
    setSelectedKey(""); // Clear selection when switching categories
  };

  // Auto-select first template when templates load
  useState(() => {
    if (templates?.templates && templates.templates.length > 0 && !selectedKey) {
      setSelectedKey(templates.templates[0].template_key);
    }
  });

  return (
    <div className="space-y-6">
      {/* Category tabs */}
      <div className="space-y-2">
        <Tabs value={selectedCategory} onValueChange={handleCategoryChange}>
          <TabsList className="grid w-full grid-cols-4 lg:grid-cols-8 gap-1">
            {Object.entries(CATEGORY_INFO).map(([key, info]) => (
              <TabsTrigger key={key} value={key} className="flex items-center gap-1.5 text-xs">
                {info.icon}
                <span className="hidden sm:inline">{info.label}</span>
                {info.count && (
                  <Badge variant="secondary" className="ml-auto text-[10px] px-1 py-0">
                    {info.count}
                  </Badge>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <p className="text-sm text-muted-foreground">
          {CATEGORY_INFO[selectedCategory].description}
        </p>
      </div>

      {/* Template selector */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Select Template</label>
        <Select
          value={selectedKey}
          onValueChange={setSelectedKey}
          disabled={isLoading || !templates?.templates.length}
        >
          <SelectTrigger>
            <SelectValue placeholder={isLoading ? "Loading..." : "Select a template..."} />
          </SelectTrigger>
          <SelectContent>
            {templates?.templates.map((template) => (
              <SelectItem key={template.template_key} value={template.template_key}>
                <div className="flex items-center gap-2">
                  <span>{template.name}</span>
                  {!template.is_default && (
                    <Badge variant="default" className="text-xs">
                      Custom
                    </Badge>
                  )}
                  {!template.is_active && (
                    <Badge variant="destructive" className="text-xs">
                      Disabled
                    </Badge>
                  )}
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {templates && (
          <p className="text-xs text-muted-foreground">
            {templates.total} template{templates.total !== 1 ? "s" : ""} in this category
          </p>
        )}
      </div>

      {/* Editor */}
      {selectedKey ? (
        <SystemPromptEditor templateKey={selectedKey} category={selectedCategory} />
      ) : (
        <div className="flex items-center justify-center py-12 border rounded-lg bg-muted/50">
          <div className="text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              {isLoading
                ? "Loading templates..."
                : templates?.templates.length === 0
                ? "No templates in this category"
                : "Select a template to edit"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
