/**
 * Layout Selector Component
 *
 * Dropdown panel for selecting graph layout algorithms (Force, Hierarchical,
 * Circular, Manual) with per-algorithm configuration options such as sliders
 * and direction selectors.
 */

'use client';

import React, { memo, useCallback, useState } from 'react';
import {
  Orbit,
  GitFork,
  Circle,
  Hand,
  Play,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import type {
  ForceLayoutOptions,
  HierarchicalLayoutOptions,
  CircularLayoutOptions,
} from '@/lib/graph-layouts';
import type { LayoutAlgorithm } from '@/lib/stores/source-graph-store';

// ============================================================================
// Types
// ============================================================================

export type LayoutOptions = ForceLayoutOptions | HierarchicalLayoutOptions | CircularLayoutOptions;

export interface LayoutSelectorProps {
  layout: LayoutAlgorithm;
  onLayoutChange: (layout: LayoutAlgorithm) => void;
  onApply: (algorithm: LayoutAlgorithm, options: LayoutOptions) => void;
  className?: string;
}

// ============================================================================
// Layout Descriptions
// ============================================================================

const LAYOUTS: {
  value: LayoutAlgorithm;
  label: string;
  description: string;
  icon: React.ElementType;
}[] = [
  {
    value: 'force',
    label: 'Force',
    description: 'Physics-based simulation that clusters connected nodes',
    icon: Orbit,
  },
  {
    value: 'hierarchical',
    label: 'Hierarchical',
    description: 'Tree-like layout showing parent-child relationships',
    icon: GitFork,
  },
  {
    value: 'circular',
    label: 'Circular',
    description: 'Nodes arranged in concentric circles by connectivity',
    icon: Circle,
  },
  {
    value: 'manual',
    label: 'Manual',
    description: 'Free-form positioning by dragging nodes',
    icon: Hand,
  },
];

// ============================================================================
// Default Options
// ============================================================================

const DEFAULT_FORCE: ForceLayoutOptions = {
  strength: 0.5,
  distance: 100,
  charge: -300,
  gravity: 0.1,
};

const DEFAULT_HIERARCHICAL: HierarchicalLayoutOptions = {
  direction: 'TB',
  nodeSpacing: 100,
  rankSpacing: 150,
};

const DEFAULT_CIRCULAR: CircularLayoutOptions = {
  radius: 300,
  ordering: 'connections',
};

// ============================================================================
// Force Options Panel
// ============================================================================

function ForceOptionsPanel({
  options,
  onChange,
}: {
  options: ForceLayoutOptions;
  onChange: (opts: ForceLayoutOptions) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Link Strength</Label>
          <span className="text-xs text-muted-foreground tabular-nums">{options.strength?.toFixed(2)}</span>
        </div>
        <Slider
          min={0}
          max={1}
          step={0.05}
          value={[options.strength ?? 0.5]}
          onValueChange={([v]) => onChange({ ...options, strength: v })}
        />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Link Distance</Label>
          <span className="text-xs text-muted-foreground tabular-nums">{options.distance}px</span>
        </div>
        <Slider
          min={30}
          max={400}
          step={10}
          value={[options.distance ?? 100]}
          onValueChange={([v]) => onChange({ ...options, distance: v })}
        />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Repulsion</Label>
          <span className="text-xs text-muted-foreground tabular-nums">{options.charge}</span>
        </div>
        <Slider
          min={-1000}
          max={-50}
          step={10}
          value={[options.charge ?? -300]}
          onValueChange={([v]) => onChange({ ...options, charge: v })}
        />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Gravity</Label>
          <span className="text-xs text-muted-foreground tabular-nums">{options.gravity?.toFixed(2)}</span>
        </div>
        <Slider
          min={0}
          max={1}
          step={0.05}
          value={[options.gravity ?? 0.1]}
          onValueChange={([v]) => onChange({ ...options, gravity: v })}
        />
      </div>
    </div>
  );
}

// ============================================================================
// Hierarchical Options Panel
// ============================================================================

function HierarchicalOptionsPanel({
  options,
  onChange,
}: {
  options: HierarchicalLayoutOptions;
  onChange: (opts: HierarchicalLayoutOptions) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Direction</Label>
        <RadioGroup
          value={options.direction ?? 'TB'}
          onValueChange={(v) => onChange({ ...options, direction: v as HierarchicalLayoutOptions['direction'] })}
          className="grid grid-cols-4 gap-1.5"
        >
          {(['TB', 'BT', 'LR', 'RL'] as const).map((dir) => (
            <label
              key={dir}
              className={cn(
                'flex items-center justify-center rounded-md border px-2 py-1.5 text-xs cursor-pointer transition-colors',
                options.direction === dir
                  ? 'border-primary bg-primary/10 text-primary font-medium'
                  : 'border-gray-200 dark:border-gray-800 hover:bg-muted text-foreground'
              )}
            >
              <RadioGroupItem value={dir} className="sr-only" />
              {dir}
            </label>
          ))}
        </RadioGroup>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Node Spacing</Label>
          <span className="text-xs text-muted-foreground tabular-nums">{options.nodeSpacing}px</span>
        </div>
        <Slider
          min={30}
          max={300}
          step={10}
          value={[options.nodeSpacing ?? 100]}
          onValueChange={([v]) => onChange({ ...options, nodeSpacing: v })}
        />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Rank Spacing</Label>
          <span className="text-xs text-muted-foreground tabular-nums">{options.rankSpacing}px</span>
        </div>
        <Slider
          min={50}
          max={400}
          step={10}
          value={[options.rankSpacing ?? 150]}
          onValueChange={([v]) => onChange({ ...options, rankSpacing: v })}
        />
      </div>
    </div>
  );
}

// ============================================================================
// Circular Options Panel
// ============================================================================

function CircularOptionsPanel({
  options,
  onChange,
}: {
  options: CircularLayoutOptions;
  onChange: (opts: CircularLayoutOptions) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label className="text-xs">Radius</Label>
          <span className="text-xs text-muted-foreground tabular-nums">{options.radius}px</span>
        </div>
        <Slider
          min={100}
          max={800}
          step={25}
          value={[options.radius ?? 300]}
          onValueChange={([v]) => onChange({ ...options, radius: v })}
        />
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">Node Ordering</Label>
        <Select
          value={options.ordering ?? 'connections'}
          onValueChange={(v) => onChange({ ...options, ordering: v as CircularLayoutOptions['ordering'] })}
        >
          <SelectTrigger className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="connections">By Connections</SelectItem>
            <SelectItem value="type">By Source Type</SelectItem>
            <SelectItem value="alphabetical">Alphabetical</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

// ============================================================================
// Main LayoutSelector Component
// ============================================================================

export const LayoutSelector = memo(function LayoutSelector({
  layout,
  onLayoutChange,
  onApply,
  className,
}: LayoutSelectorProps) {
  const [forceOpts, setForceOpts] = useState<ForceLayoutOptions>({ ...DEFAULT_FORCE });
  const [hierarchicalOpts, setHierarchicalOpts] = useState<HierarchicalLayoutOptions>({ ...DEFAULT_HIERARCHICAL });
  const [circularOpts, setCircularOpts] = useState<CircularLayoutOptions>({ ...DEFAULT_CIRCULAR });

  const activeLayout = LAYOUTS.find((l) => l.value === layout) ?? LAYOUTS[0];
  const ActiveIcon = activeLayout.icon;

  const handleApply = useCallback(() => {
    switch (layout) {
      case 'force':
        onApply('force', forceOpts);
        break;
      case 'hierarchical':
        onApply('hierarchical', hierarchicalOpts);
        break;
      case 'circular':
        onApply('circular', circularOpts);
        break;
      case 'manual':
        onApply('manual', {});
        break;
    }
  }, [layout, forceOpts, hierarchicalOpts, circularOpts, onApply]);

  const handleReset = useCallback(() => {
    setForceOpts({ ...DEFAULT_FORCE });
    setHierarchicalOpts({ ...DEFAULT_HIERARCHICAL });
    setCircularOpts({ ...DEFAULT_CIRCULAR });
  }, []);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn('h-8 gap-1.5 text-xs', className)}
        >
          <ActiveIcon className="h-3.5 w-3.5" />
          {activeLayout.label}
        </Button>
      </PopoverTrigger>

      <PopoverContent className="w-72 p-0" align="start">
        {/* Layout algorithm picker */}
        <div className="p-3 space-y-2">
          <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Layout Algorithm
          </Label>
          <div className="grid grid-cols-2 gap-1.5">
            {LAYOUTS.map((l) => {
              const Icon = l.icon;
              const isActive = layout === l.value;
              return (
                <button
                  key={l.value}
                  onClick={() => onLayoutChange(l.value)}
                  className={cn(
                    'flex items-center gap-2 px-2.5 py-2 rounded-md text-left transition-colors text-xs',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-muted text-foreground'
                  )}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  <span className="font-medium">{l.label}</span>
                </button>
              );
            })}
          </div>
          <p className="text-[10px] text-muted-foreground leading-relaxed">
            {activeLayout.description}
          </p>
        </div>

        {/* Per-algorithm options */}
        {layout !== 'manual' && (
          <>
            <Separator />
            <div className="p-3 space-y-1">
              <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Options
              </Label>
              <div className="pt-1">
                {layout === 'force' && (
                  <ForceOptionsPanel options={forceOpts} onChange={setForceOpts} />
                )}
                {layout === 'hierarchical' && (
                  <HierarchicalOptionsPanel options={hierarchicalOpts} onChange={setHierarchicalOpts} />
                )}
                {layout === 'circular' && (
                  <CircularOptionsPanel options={circularOpts} onChange={setCircularOpts} />
                )}
              </div>
            </div>
          </>
        )}

        {/* Action buttons */}
        <Separator />
        <div className="p-2 flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs gap-1"
            onClick={handleReset}
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </Button>
          <div className="flex-1" />
          <Button
            size="sm"
            className="h-7 text-xs gap-1"
            onClick={handleApply}
          >
            <Play className="h-3 w-3" />
            Apply
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
});
