"use client";

import { SystemPromptsManager } from "@/components/agents/SystemPromptsManager";

export default function PromptsSettingsPage() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="animate-fade-in-up">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
          Prompt Management
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          Manage AI prompts and system templates across all categories
        </p>
      </div>

      <SystemPromptsManager />
    </div>
  );
}
