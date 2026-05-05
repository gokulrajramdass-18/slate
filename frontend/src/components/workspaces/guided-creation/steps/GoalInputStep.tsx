/**
 * Goal Input Step
 *
 * First step where user enters their workspace goal and selects data sources.
 */

'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useGuidedCreationStore } from '@/lib/stores/guided-creation-store';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Info, Target, Database, FileText, Globe, Youtube, Plug } from 'lucide-react';
import { sourcesApi } from '@/lib/api/sources';
import type { Source } from '@/lib/types';

const SOURCE_TYPE_ICONS: Record<string, any> = {
  file: FileText,
  url: Globe,
  youtube: Youtube,
  hana_table: Database,
  api: Plug,
  text: FileText,
};

export function GoalInputStep() {
  const { goal, setGoal, selectedDataSources, setSelectedDataSources } = useGuidedCreationStore();
  const [searchQuery, setSearchQuery] = useState('');

  const characterCount = goal.length;
  const minCharacters = 20;
  const maxCharacters = 5000;
  const isValid = characterCount >= minCharacters && characterCount <= maxCharacters;

  // Fetch all available data sources
  const { data: allSources = [], isLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: () => sourcesApi.list(),
  });

  // Filter sources based on search query
  const filteredSources = allSources.filter((source) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      source.title?.toLowerCase().includes(query) ||
      source.full_text?.toLowerCase().includes(query) ||
      source.source_type.toLowerCase().includes(query)
    );
  });

  // Toggle source selection
  const toggleSource = (sourceId: string) => {
    if (selectedDataSources.includes(sourceId)) {
      setSelectedDataSources(selectedDataSources.filter((id) => id !== sourceId));
    } else {
      setSelectedDataSources([...selectedDataSources, sourceId]);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="p-3 bg-primary/10 rounded-lg">
          <Target className="h-6 w-6 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold mb-2">What do you want to achieve?</h2>
          <p className="text-muted-foreground">
            Describe your goal in detail. The more specific you are, the better we can help you set up
            your workspace with the right tools, data sources, and AI agents.
          </p>
        </div>
      </div>

      {/* Goal Input */}
      <div className="space-y-2">
        <Label htmlFor="goal">Your Goal</Label>
        <Textarea
          id="goal"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Example: I want to analyze customer feedback from our support tickets to identify common pain points and prioritize feature requests. I need to combine data from Zendesk, survey responses, and product usage analytics to generate monthly insights reports."
          rows={8}
          className="resize-none"
        />
        <div className="flex justify-between text-sm">
          <span className={characterCount < minCharacters ? 'text-muted-foreground' : 'text-green-600'}>
            {characterCount < minCharacters
              ? `${minCharacters - characterCount} more characters needed`
              : '✓ Goal is detailed enough'}
          </span>
          <span className={characterCount > maxCharacters ? 'text-destructive' : 'text-muted-foreground'}>
            {characterCount} / {maxCharacters}
          </span>
        </div>
      </div>

      {/* Data Source Selection */}
      <div className="space-y-4">
        <div>
          <Label htmlFor="sources">Select Data Sources (Optional)</Label>
          <p className="text-sm text-muted-foreground mt-1">
            Choose existing data sources to include in your workspace. You can also add more later.
          </p>
        </div>

        {/* Search */}
        <div className="relative">
          <Database className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search data sources..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* Selected Count */}
        {selectedDataSources.length > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <Badge variant="secondary">{selectedDataSources.length} selected</Badge>
          </div>
        )}

        {/* Source List */}
        <div className="max-h-96 overflow-y-auto space-y-2 border rounded-lg p-4">
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading data sources...</div>
          ) : filteredSources.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchQuery ? 'No data sources match your search.' : 'No data sources available. Create some first.'}
            </div>
          ) : (
            filteredSources.map((source) => {
              const Icon = SOURCE_TYPE_ICONS[source.source_type] || FileText;
              const isSelected = selectedDataSources.includes(source.id);

              return (
                <Card
                  key={source.id}
                  className={`cursor-pointer transition-all ${
                    isSelected ? 'border-primary bg-primary/5' : 'hover:border-primary/50'
                  }`}
                  onClick={() => toggleSource(source.id)}
                >
                  <CardHeader className="p-4">
                    <div className="flex items-start gap-3">
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => toggleSource(source.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4 text-muted-foreground" />
                          <CardTitle className="text-sm">{source.title}</CardTitle>
                          <Badge variant="outline" className="text-xs">
                            {source.source_type}
                          </Badge>
                        </div>
                        {source.full_text && (
                          <CardDescription className="text-xs mt-1 line-clamp-2">
                            {source.full_text.slice(0, 150)}
                          </CardDescription>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                </Card>
              );
            })
          )}
        </div>
      </div>

      {/* Tips */}
      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          <strong>Tips for a great goal:</strong>
          <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
            <li>Be specific about what you want to accomplish</li>
            <li>Mention any data sources or tools you plan to use</li>
            <li>Describe the expected outcome or deliverable</li>
            <li>Include any time constraints or deadlines</li>
          </ul>
        </AlertDescription>
      </Alert>

      {/* Examples */}
      <div className="space-y-3">
        <p className="text-sm font-medium">Need inspiration? Try these examples:</p>
        <div className="grid gap-2">
          {EXAMPLE_GOALS.map((example, index) => (
            <button
              key={index}
              onClick={() => setGoal(example)}
              className="text-left p-3 border rounded-lg hover:bg-accent transition-colors text-sm"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Example Goals
// ============================================================================

const EXAMPLE_GOALS = [
  'I want to track and analyze our competitors\' product launches, pricing changes, and marketing campaigns. I need to monitor their websites, social media, and press releases, then generate weekly competitive intelligence reports for our product team.',

  'I want to automate our monthly financial reporting by combining data from our HANA ERP system, Stripe payments, and expense tracking tools. The goal is to generate P&L statements, cash flow projections, and budget variance analysis automatically.',

  'I want to research emerging trends in AI and machine learning by analyzing academic papers, tech blogs, and industry reports. I need to identify relevant technologies for our product roadmap and summarize findings in a quarterly research digest.',

  'I want to monitor customer sentiment across all our communication channels (support tickets, social media, app reviews) and correlate it with product releases and marketing campaigns. The output should be a real-time sentiment dashboard and weekly insights.',
];
