"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

interface SettingsHeaderProps {
  title: string;
  description?: string;
}

export function SettingsHeader({ title, description }: SettingsHeaderProps) {
  const router = useRouter();

  return (
    <div className="space-y-4 animate-fade-in-up">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push("/settings")}
        className="transition-all hover:scale-110"
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to Settings
      </Button>

      <div>
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
          {title}
        </h1>
        {description && (
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            {description}
          </p>
        )}
      </div>
    </div>
  );
}
