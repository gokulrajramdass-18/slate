"use client";

import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Info, Brain } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";

interface DeepResearchToggleProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  disabled?: boolean;
  compact?: boolean; // New prop for compact header mode
}

export function DeepResearchToggle({
  enabled,
  onToggle,
  disabled = false,
  compact = false,
}: DeepResearchToggleProps) {
  // Compact version for header
  if (compact) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 border rounded-lg bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/20 dark:to-blue-950/20 border-purple-200 dark:border-purple-800 transition-all hover:scale-105 hover:shadow-md">
        <Brain className="h-4 w-4 text-purple-600 dark:text-purple-400" />
        <Label
          htmlFor="deep-research-compact"
          className="cursor-pointer font-medium text-xs text-gray-900 dark:text-gray-100 whitespace-nowrap"
        >
          Deep Research
        </Label>
        <Badge variant={enabled ? "default" : "outline"} className="text-xs px-1.5 py-0">
          {enabled ? "ON" : "OFF"}
        </Badge>
        <Switch
          id="deep-research-compact"
          checked={enabled}
          onCheckedChange={onToggle}
          disabled={disabled}
          className="data-[state=checked]:bg-purple-600 scale-75"
        />
      </div>
    );
  }

  // Full version for main content area
  return (
    <div className="flex items-center justify-between px-4 py-3 border rounded-lg bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/20 dark:to-blue-950/20 border-purple-200 dark:border-purple-800 transition-all hover:shadow-lg animate-fade-in">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900 transition-transform hover:scale-110">
          <Brain className="h-4 w-4 text-purple-600 dark:text-purple-400" />
        </div>

        <div className="flex items-center gap-2">
          <Label
            htmlFor="deep-research"
            className="cursor-pointer font-semibold text-sm text-gray-900 dark:text-gray-100"
          >
            Deep Research Mode
          </Label>

          <Badge variant={enabled ? "default" : "outline"} className="text-xs animate-pulse-slow">
            {enabled ? "ON" : "OFF"}
          </Badge>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-4 w-4 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 cursor-help transition-all hover:scale-110" />
              </TooltipTrigger>
              <TooltipContent className="max-w-sm animate-fade-in">
                <div className="space-y-2">
                  <p className="font-semibold">Autonomous Deep Research</p>
                  <p className="text-sm">
                    Enables multi-phase research workflow that:
                  </p>
                  <ul className="text-sm list-disc list-inside space-y-1">
                    <li>Analyzes and decomposes your question</li>
                    <li>Searches across multiple sources</li>
                    <li>Synthesizes key findings</li>
                    <li>Generates comprehensive report</li>
                  </ul>
                  <p className="text-xs text-muted-foreground mt-2">
                    ⏱️ Takes 2-5 minutes • 🔒 Blocks chat during research
                  </p>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      <Switch
        id="deep-research"
        checked={enabled}
        onCheckedChange={onToggle}
        disabled={disabled}
        className="data-[state=checked]:bg-purple-600 transition-all"
      />
    </div>
  );
}
