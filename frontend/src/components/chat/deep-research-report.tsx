"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { FileText, Clock, Search, Lightbulb, Download, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import { DeepResearchResult } from "@/lib/api/deep-research";

interface DeepResearchReportProps {
  result: DeepResearchResult;
}

export function DeepResearchReport({ result }: DeepResearchReportProps) {
  const handleExport = () => {
    const blob = new Blob([result.final_report], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `deep-research-report-${new Date().toISOString()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="border-purple-200 dark:border-purple-800 shadow-lg">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              <CardTitle className="text-xl">Deep Research Report</CardTitle>
            </div>

            <div className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                <span>{result.duration_seconds?.toFixed(1)}s</span>
              </div>

              <div className="flex items-center gap-1.5">
                <Search className="h-3.5 w-3.5" />
                <span>{result.search_results_count} results</span>
              </div>

              <div className="flex items-center gap-1.5">
                <Lightbulb className="h-3.5 w-3.5" />
                <span>{result.key_findings.length} findings</span>
              </div>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            className="flex items-center gap-1.5"
          >
            <Download className="h-4 w-4" />
            Export
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Key Findings Summary */}
        {result.key_findings.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-semibold text-sm flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <Lightbulb className="h-4 w-4 text-yellow-500" />
              Key Findings
            </h3>

            <div className="grid gap-3">
              {result.key_findings.map((finding, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 space-y-2"
                >
                  <div className="flex items-start gap-2">
                    <Badge variant="outline" className="text-xs font-mono mt-0.5">
                      {idx + 1}
                    </Badge>
                    <div className="flex-1 space-y-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {finding.finding}
                      </p>
                      <p className="text-xs text-gray-600 dark:text-gray-400">
                        {finding.supporting_evidence}
                      </p>
                      {finding.citations.length > 0 && (
                        <div className="flex items-center gap-1 flex-wrap mt-1">
                          {finding.citations.map((citNum) => (
                            <Badge
                              key={citNum}
                              variant="secondary"
                              className="text-xs h-5 px-1.5"
                            >
                              [{citNum}]
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <Separator />

        {/* Full Report */}
        <div className="space-y-3">
          <h3 className="font-semibold text-sm flex items-center gap-2 text-gray-900 dark:text-gray-100">
            <FileText className="h-4 w-4 text-purple-500" />
            Full Report
          </h3>

          <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:font-semibold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-p:text-gray-700 dark:prose-p:text-gray-300 prose-ul:text-gray-700 dark:prose-ul:text-gray-300 prose-li:text-gray-700 dark:prose-li:text-gray-300">
            <ReactMarkdown>{result.final_report}</ReactMarkdown>
          </div>
        </div>

        <Separator />

        {/* Citations */}
        {result.citations.length > 0 && (
          <div className="space-y-2">
            <h3 className="font-semibold text-sm flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <ExternalLink className="h-4 w-4 text-blue-500" />
              References ({result.citations.length})
            </h3>

            <div className="space-y-1.5 text-sm">
              {result.citations.map((citation) => (
                <div
                  key={citation.number}
                  className="flex items-start gap-2 text-gray-700 dark:text-gray-300"
                >
                  <Badge variant="outline" className="text-xs font-mono flex-shrink-0">
                    [{citation.number}]
                  </Badge>
                  <span className="text-xs">{citation.source}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
