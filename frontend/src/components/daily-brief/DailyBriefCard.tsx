"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Sparkles, AlertCircle } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuthStore } from "@/lib/stores/auth-store";
import { dailyBriefApi } from "@/lib/api/daily-brief";
import { toast } from "sonner";
import Link from "next/link";
import { useState, useEffect } from "react";

export function DailyBriefCard() {
  const { user } = useAuthStore();
  const [displayedText, setDisplayedText] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const { data: brief, isLoading, refetch, error } = useQuery({
    queryKey: ["daily-brief"],
    queryFn: dailyBriefApi.get,
    refetchOnMount: true,
    staleTime: 5 * 60 * 1000,
    retry: 1,
    enabled: true,
  });

  // Generate plain text for typing animation
  const generateBriefText = () => {
    if (!brief) return "";

    const executions = brief.executions_since_login;
    const approvals = brief.pending_approvals || [];
    const schedules = brief.upcoming_schedules || [];
    const notifications = brief.notifications;
    const orchestrations = brief.orchestrations;

    let text = "";

    // Start with AI summary if available
    if (brief.ai_summary) {
      text += brief.ai_summary + "\n\n";
    }

    // Add detailed breakdown with markers for bold sections
    text += "**📊 Activity Summary:**\n\n";

    if (executions && executions.total > 0) {
      text += `• ${executions.total} workflow execution${executions.total !== 1 ? 's' : ''} (${executions.completed} completed, ${executions.failed} failed, ${executions.success_rate}% success rate)\n`;
    } else {
      text += `• No workflow executions since your last login\n`;
    }

    if (approvals.length > 0) {
      text += `• ${approvals.length} pending approval${approvals.length !== 1 ? 's' : ''} requiring your attention\n`;
    } else {
      text += `• No pending approvals\n`;
    }

    if (notifications && notifications.total > 0) {
      text += `• ${notifications.unread} unread notification${notifications.unread !== 1 ? 's' : ''} out of ${notifications.total} total\n`;
    }

    if (schedules.length > 0) {
      text += `• ${schedules.length} upcoming scheduled workflow${schedules.length !== 1 ? 's' : ''}\n`;
    }

    if (orchestrations && orchestrations.total > 0) {
      text += `• ${orchestrations.total} orchestration run${orchestrations.total !== 1 ? 's' : ''} (${orchestrations.completed} completed, ${orchestrations.failed} failed)\n`;
    }

    // Add pending approvals details
    if (approvals.length > 0) {
      text += "\n**🔔 Pending Approvals:**\n\n";
      approvals.forEach((approval, index) => {
        const promptPreview = approval.approval_prompt.substring(0, 100);
        text += `${index + 1}. ${approval.workflow_name}\n   ${promptPreview}${approval.approval_prompt.length > 100 ? '...' : ''}\n\n`;
      });
    }

    // Add upcoming schedules
    if (schedules.length > 0) {
      text += "\n**⏰ Upcoming Schedules:**\n\n";
      schedules.forEach((schedule, index) => {
        const scheduleTime = new Date(schedule.next_run_at).toLocaleString();
        text += `${index + 1}. ${schedule.workflow_name}\n   Next run: ${scheduleTime}\n\n`;
      });
    }

    return text;
  };

  // Typing animation effect
  useEffect(() => {
    if (!brief || isLoading) return;

    const fullText = generateBriefText();
    setIsTyping(true);
    setDisplayedText("");

    let currentIndex = 0;
    const typingSpeed = 5; // milliseconds per character (faster)

    const timer = setInterval(() => {
      if (currentIndex < fullText.length) {
        setDisplayedText(fullText.substring(0, currentIndex + 1));
        currentIndex++;
      } else {
        setIsTyping(false);
        clearInterval(timer);
      }
    }, typingSpeed);

    return () => clearInterval(timer);
  }, [brief, isLoading]);

  // Render text with bold formatting
  const renderFormattedText = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);

    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        // Bold section
        return (
          <span key={index} className="font-bold">
            {part.slice(2, -2)}
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  const handleRefresh = () => {
    setDisplayedText("");
    setIsTyping(true);
    refetch();
    toast.success("Refreshing daily brief...");
  };

  if (!user) {
    return null;
  }

  if (error) {
    return (
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">
            <AlertCircle className="mx-auto h-8 w-8 mb-2 text-destructive" />
            <p>Failed to load daily brief</p>
            <Button onClick={handleRefresh} variant="outline" size="sm" className="mt-2">
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-48 mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!brief) return null;

  const approvals = brief.pending_approvals || [];

  return (
    <Card className="mb-8 shadow-lg border-2 border-blue-500 bg-white dark:bg-gray-900">
      <CardHeader className="pb-4 px-6 pt-5 border-b-2 border-blue-300 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-950 dark:to-purple-950">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-2xl font-extrabold text-blue-900 dark:text-blue-100 flex items-center gap-2">
              <span>Welcome back, {user?.full_name || user?.username}! 👋</span>
            </CardTitle>
            <CardDescription className="mt-1.5 text-sm text-gray-600 dark:text-gray-400">
              Last login: {brief.time_since_login}
            </CardDescription>
          </div>
          <Button
            onClick={handleRefresh}
            variant="outline"
            size="sm"
            disabled={isLoading}
            className="h-9 px-4 text-sm font-medium"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>

      <CardContent className="px-6 pb-5 pt-5">
        {/* AI-style typing text display */}
        <div className="p-5 bg-blue-50 dark:bg-blue-950/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <div className="flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="whitespace-pre-wrap text-base leading-relaxed text-gray-800 dark:text-gray-200" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
                {renderFormattedText(displayedText)}
                {isTyping && (
                  <span className="inline-block w-0.5 h-4 bg-blue-600 dark:bg-blue-400 animate-pulse ml-1 align-middle">|</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Quick action buttons for pending approvals */}
        {approvals.length > 0 && !isTyping && (
          <div className="flex flex-wrap gap-2 pt-4 mt-1">
            {approvals.map((approval) => (
              <Link key={approval.id} href={approval.action_url}>
                <Button variant="default" size="sm" className="h-9 px-4 font-semibold">
                  Review: {approval.workflow_name}
                </Button>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
