"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Shield,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Type,
  Link2,
  RefreshCw,
  Eye,
  EyeOff,
  Loader2,
} from "lucide-react";
import type { ModerationReport, ModerationIssue } from "@/lib/types";

const STATUS_CONFIG = {
  passed: {
    icon: CheckCircle2,
    color: "text-green-600 dark:text-green-400",
    bg: "bg-green-50 dark:bg-green-950",
    border: "border-green-200 dark:border-green-800",
    label: "Passed",
    badgeVariant: "default" as const,
  },
  warning: {
    icon: AlertTriangle,
    color: "text-yellow-600 dark:text-yellow-400",
    bg: "bg-yellow-50 dark:bg-yellow-950",
    border: "border-yellow-200 dark:border-yellow-800",
    label: "Needs Review",
    badgeVariant: "secondary" as const,
  },
  blocked: {
    icon: XCircle,
    color: "text-red-600 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-950",
    border: "border-red-200 dark:border-red-800",
    label: "Blocked",
    badgeVariant: "destructive" as const,
  },
};

const SEVERITY_CONFIG = {
  high: { color: "text-red-600", bg: "bg-red-100 dark:bg-red-900", label: "High" },
  medium: { color: "text-yellow-600", bg: "bg-yellow-100 dark:bg-yellow-900", label: "Medium" },
  low: { color: "text-gray-600", bg: "bg-gray-100 dark:bg-gray-800", label: "Low" },
};

const LAYER_ICONS: Record<string, React.ReactNode> = {
  ai_filter: <Shield className="w-4 h-4" />,
  keyword_blocklist: <Type className="w-4 h-4" />,
  source_validation: <Link2 className="w-4 h-4" />,
  user_review: <Eye className="w-4 h-4" />,
};

const LAYER_LABELS: Record<string, string> = {
  ai_filter: "AI Filter",
  keyword_blocklist: "Keywords",
  source_validation: "Sources",
  user_review: "User Review",
};

interface ModerationDashboardProps {
  report: ModerationReport;
  micrositeId: string;
  onRerunModeration?: () => void;
  onFixIssue?: (issue: ModerationIssue) => void;
  onIgnoreIssue?: (issue: ModerationIssue) => void;
  isRerunning?: boolean;
}

export function ModerationDashboard({
  report,
  micrositeId,
  onRerunModeration,
  onFixIssue,
  onIgnoreIssue,
  isRerunning,
}: ModerationDashboardProps) {
  const [ignoredIssues, setIgnoredIssues] = useState<Set<number>>(new Set());
  const statusConfig = STATUS_CONFIG[report.status];
  const StatusIcon = statusConfig.icon;

  const issuesByLayer = {
    all: report.issues,
    ai_filter: report.issues.filter((i) => i.type === "ai_filter"),
    keyword_blocklist: report.issues.filter((i) => i.type === "keyword_blocklist"),
    source_validation: report.issues.filter((i) => i.type === "source_validation"),
  };

  const handleIgnore = (index: number, issue: ModerationIssue) => {
    setIgnoredIssues((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
    onIgnoreIssue?.(issue);
  };

  return (
    <div className="space-y-4">
      {/* Status Header */}
      <div className={`rounded-lg border p-4 ${statusConfig.bg} ${statusConfig.border}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <StatusIcon className={`w-6 h-6 ${statusConfig.color}`} />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{statusConfig.label}</h3>
                <Badge variant={statusConfig.badgeVariant}>
                  Score: {Math.round(report.overall_score * 100)}%
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">
                {report.issues.length} issue{report.issues.length !== 1 ? "s" : ""} found
                {ignoredIssues.size > 0 && ` (${ignoredIssues.size} ignored)`}
              </p>
            </div>
          </div>
          {onRerunModeration && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRerunModeration}
              disabled={isRerunning}
            >
              {isRerunning ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              Re-run
            </Button>
          )}
        </div>
      </div>

      {/* Layer Scores */}
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(report.layers).map(([layer, data]) => {
          if (!data) return null;
          return (
            <Card key={layer} className="p-3">
              <div className="flex items-center gap-2 mb-2">
                {LAYER_ICONS[layer]}
                <span className="text-sm font-medium">{LAYER_LABELS[layer]}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      data.score >= 0.8
                        ? "bg-green-500"
                        : data.score >= 0.5
                        ? "bg-yellow-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${data.score * 100}%` }}
                  />
                </div>
                <span className="text-xs text-muted-foreground">
                  {Math.round(data.score * 100)}%
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {data.issues.length} issue{data.issues.length !== 1 ? "s" : ""}
              </p>
            </Card>
          );
        })}
      </div>

      {/* Issues Tabs */}
      {report.issues.length > 0 && (
        <Tabs defaultValue="all">
          <TabsList>
            <TabsTrigger value="all">
              All Issues ({issuesByLayer.all.length})
            </TabsTrigger>
            <TabsTrigger value="ai_filter">
              AI Filter ({issuesByLayer.ai_filter.length})
            </TabsTrigger>
            <TabsTrigger value="keyword_blocklist">
              Keywords ({issuesByLayer.keyword_blocklist.length})
            </TabsTrigger>
            <TabsTrigger value="source_validation">
              Sources ({issuesByLayer.source_validation.length})
            </TabsTrigger>
          </TabsList>

          {(["all", "ai_filter", "keyword_blocklist", "source_validation"] as const).map(
            (tab) => (
              <TabsContent key={tab} value={tab}>
                <ScrollArea className="max-h-[400px]">
                  <div className="space-y-2">
                    {issuesByLayer[tab].map((issue, index) => {
                      const globalIndex = report.issues.indexOf(issue);
                      const isIgnored = ignoredIssues.has(globalIndex);
                      const severity = SEVERITY_CONFIG[issue.severity];

                      return (
                        <div
                          key={index}
                          className={`flex items-start gap-3 p-3 rounded-lg border transition-opacity ${
                            isIgnored ? "opacity-50" : ""
                          }`}
                        >
                          <div className="flex-shrink-0 mt-0.5">
                            {LAYER_ICONS[issue.type]}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge
                                variant="secondary"
                                className={`text-xs ${severity.bg} ${severity.color}`}
                              >
                                {severity.label}
                              </Badge>
                              <span className="text-xs text-muted-foreground capitalize">
                                {LAYER_LABELS[issue.type]}
                              </span>
                              {issue.location && (
                                <span className="text-xs text-muted-foreground">
                                  in section: {issue.location}
                                </span>
                              )}
                            </div>
                            <p className="text-sm">{issue.description}</p>
                          </div>
                          <div className="flex gap-1 flex-shrink-0">
                            {onFixIssue && !isIgnored && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => onFixIssue(issue)}
                              >
                                Fix
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs"
                              onClick={() => handleIgnore(globalIndex, issue)}
                            >
                              {isIgnored ? (
                                <>
                                  <Eye className="w-3 h-3 mr-1" /> Restore
                                </>
                              ) : (
                                <>
                                  <EyeOff className="w-3 h-3 mr-1" /> Ignore
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </TabsContent>
            )
          )}
        </Tabs>
      )}

      {/* Manual Review Alert */}
      {report.requires_review && (
        <div className="flex items-start gap-3 p-4 rounded-lg border border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950">
          <AlertCircle className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-yellow-800 dark:text-yellow-200">
              Manual Review Required
            </h4>
            <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
              Please review flagged issues before publishing. You can ignore false
              positives or fix issues using the editor.
            </p>
          </div>
        </div>
      )}

      {report.issues.length === 0 && (
        <div className="text-center py-6 text-muted-foreground">
          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-green-500" />
          <p>No issues found. Your content looks good!</p>
        </div>
      )}
    </div>
  );
}
