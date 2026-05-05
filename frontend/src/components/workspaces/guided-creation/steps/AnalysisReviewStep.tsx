/**
 * Analysis Review Step
 *
 * Shows the AI's analysis of the user's goal.
 */

'use client';

import { useGuidedCreationStore } from '@/lib/stores/guided-creation-store';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Brain, Target, Layers, Tag, CheckCircle } from 'lucide-react';

export function AnalysisReviewStep() {
  const { analysis, goal } = useGuidedCreationStore();

  if (!analysis) {
    return <div>Loading analysis...</div>;
  }

  const complexityColors = {
    simple: 'bg-green-100 text-green-800 border-green-200',
    moderate: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    complex: 'bg-red-100 text-red-800 border-red-200',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="p-3 bg-primary/10 rounded-lg">
          <Brain className="h-6 w-6 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold mb-2">Goal Analysis</h2>
          <p className="text-muted-foreground">
            We've analyzed your goal to understand what you need. Review the analysis below to ensure
            we're on the right track.
          </p>
        </div>
      </div>

      {/* Your Goal (Recap) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Target className="h-5 w-5" />
            Your Goal
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{goal}</p>
        </CardContent>
      </Card>

      {/* Analysis Results */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Intent */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />
              Intent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="outline" className="text-sm">
              {analysis.intent}
            </Badge>
            <p className="text-xs text-muted-foreground mt-2">
              What you're trying to accomplish
            </p>
          </CardContent>
        </Card>

        {/* Domain */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4" />
              Domain
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="outline" className="text-sm">
              {analysis.domain}
            </Badge>
            <p className="text-xs text-muted-foreground mt-2">
              Industry or field of work
            </p>
          </CardContent>
        </Card>

        {/* Complexity */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Complexity</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge
              className={`text-sm ${complexityColors[analysis.complexity]}`}
            >
              {analysis.complexity}
            </Badge>
            <p className="text-xs text-muted-foreground mt-2">
              Estimated project complexity
            </p>
          </CardContent>
        </Card>

        {/* Keywords */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Tag className="h-4 w-4" />
              Keywords
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {analysis.keywords.map((keyword, index) => (
                <Badge key={index} variant="secondary" className="text-xs">
                  {keyword}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Requirements */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Required Capabilities</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-3">
            Based on your goal, you'll need these capabilities:
          </p>
          <ul className="space-y-2">
            {analysis.requirements.map((requirement, index) => (
              <li key={index} className="flex items-start gap-2 text-sm">
                <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span>{requirement}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
