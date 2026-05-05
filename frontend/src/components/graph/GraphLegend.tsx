'use client';

/**
 * GraphLegend
 *
 * Dialog overlay showing Node Types, Edge Types, and Keyboard Shortcuts
 * for the source graph visualization.
 */

import React from 'react';
import {
  FileText,
  Globe,
  Video,
  Database,
  Plug,
  Keyboard,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface GraphLegendProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// ============================================================================
// Node Type Definitions
// ============================================================================

const NODE_TYPES: {
  type: string;
  label: string;
  color: string;
  icon: React.ElementType;
  description: string;
}[] = [
  {
    type: 'file',
    label: 'File',
    color: '#3B82F6',
    icon: FileText,
    description: 'Uploaded documents (PDF, Word, etc.)',
  },
  {
    type: 'url',
    label: 'URL',
    color: '#10B981',
    icon: Globe,
    description: 'Web pages and online articles',
  },
  {
    type: 'text',
    label: 'Text',
    color: '#6B7280',
    icon: FileText,
    description: 'Raw text content and notes',
  },
  {
    type: 'youtube',
    label: 'YouTube',
    color: '#EF4444',
    icon: Video,
    description: 'YouTube video transcripts',
  },
  {
    type: 'hana_table',
    label: 'HANA Table',
    color: '#8B5CF6',
    icon: Database,
    description: 'SAP HANA database tables',
  },
  {
    type: 'api',
    label: 'API',
    color: '#F59E0B',
    icon: Plug,
    description: 'Authenticated REST API endpoints',
  },
];

// ============================================================================
// Edge Type Definitions
// ============================================================================

const EDGE_TYPES: {
  type: string;
  label: string;
  color: string;
  dashArray?: string;
  animated?: boolean;
  description: string;
}[] = [
  {
    type: 'semantic',
    label: 'Semantic Similarity',
    color: '#A855F7',
    description: 'Connected by embedding similarity (1-4px by strength)',
  },
  {
    type: 'notebook',
    label: 'Shared Notebook',
    color: '#3B82F6',
    description: 'Belong to the same notebook',
  },
  {
    type: 'topic',
    label: 'Common Topic',
    color: '#10B981',
    dashArray: '6 4',
    description: 'Share one or more topics',
  },
  {
    type: 'note_link',
    label: 'Note Link',
    color: '#F59E0B',
    animated: true,
    description: 'Linked via a shared note',
  },
  {
    type: 'hana_schema',
    label: 'HANA Schema',
    color: '#EC4899',
    dashArray: '10 4',
    description: 'Related through HANA schema',
  },
  {
    type: 'api_relation',
    label: 'API Relation',
    color: '#14B8A6',
    dashArray: '4 3',
    description: 'Related through API endpoints',
  },
];

// ============================================================================
// Keyboard Shortcuts
// ============================================================================

const SHORTCUTS: { keys: string[]; description: string }[] = [
  { keys: ['Click'], description: 'Select a node' },
  { keys: ['Double Click'], description: 'Open source details' },
  { keys: ['Esc'], description: 'Deselect / close panel' },
  { keys: ['Scroll'], description: 'Zoom in / out' },
  { keys: ['Drag'], description: 'Pan the canvas' },
  { keys: ['Shift', 'Drag'], description: 'Box selection' },
  { keys: ['Ctrl', 'A'], description: 'Select all nodes' },
  { keys: ['Ctrl', '0'], description: 'Fit graph to view' },
  { keys: ['Delete'], description: 'Remove selected' },
];

// ============================================================================
// Component
// ============================================================================

export const GraphLegend = React.memo(function GraphLegend({ open, onOpenChange }: GraphLegendProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Graph Legend</DialogTitle>
          <DialogDescription>
            Visual guide for the source relationship graph.
          </DialogDescription>
        </DialogHeader>

        {/* Node Types */}
        <div>
          <h3 className="text-sm font-semibold mb-3">Node Types</h3>
          <div className="grid grid-cols-1 gap-2">
            {NODE_TYPES.map((nt) => {
              const Icon = nt.icon;
              return (
                <div
                  key={nt.type}
                  className="flex items-center gap-3 rounded-md border border-gray-200 dark:border-gray-800 px-3 py-2"
                >
                  <div
                    className="p-1.5 rounded-md text-white shadow-sm shrink-0"
                    style={{ backgroundColor: nt.color }}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{nt.label}</div>
                    <div className="text-xs text-muted-foreground">{nt.description}</div>
                  </div>
                  <div
                    className="w-4 h-4 rounded-full shrink-0 border-2 border-white dark:border-gray-900 shadow-sm"
                    style={{ backgroundColor: nt.color }}
                  />
                </div>
              );
            })}
          </div>
        </div>

        <Separator />

        {/* Edge Types */}
        <div>
          <h3 className="text-sm font-semibold mb-3">Edge Types</h3>
          <div className="grid grid-cols-1 gap-2">
            {EDGE_TYPES.map((et) => (
              <div
                key={et.type}
                className="flex items-center gap-3 rounded-md border border-gray-200 dark:border-gray-800 px-3 py-2"
              >
                {/* Line sample */}
                <svg width="40" height="16" className="shrink-0">
                  <line
                    x1="2"
                    y1="8"
                    x2="38"
                    y2="8"
                    stroke={et.color}
                    strokeWidth="2.5"
                    strokeDasharray={et.dashArray}
                    strokeLinecap="round"
                  />
                  {et.animated && (
                    <>
                      <circle cx="12" cy="8" r="2" fill={et.color} opacity="0.6">
                        <animate
                          attributeName="cx"
                          from="4"
                          to="36"
                          dur="1.5s"
                          repeatCount="indefinite"
                        />
                        <animate
                          attributeName="opacity"
                          values="0.6;1;0.6"
                          dur="1.5s"
                          repeatCount="indefinite"
                        />
                      </circle>
                    </>
                  )}
                </svg>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{et.label}</div>
                  <div className="text-xs text-muted-foreground">{et.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <Separator />

        {/* Keyboard Shortcuts */}
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
            <Keyboard className="h-4 w-4" />
            Keyboard Shortcuts
          </h3>
          <div className="rounded-md border border-gray-200 dark:border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-800/50">
                  <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                    Key
                  </th>
                  <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {SHORTCUTS.map((shortcut, i) => (
                  <tr
                    key={i}
                    className={cn(
                      'border-t border-gray-100 dark:border-gray-800',
                      i % 2 === 0 ? 'bg-white dark:bg-gray-900' : 'bg-gray-50/50 dark:bg-gray-800/20'
                    )}
                  >
                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-1">
                        {shortcut.keys.map((key, j) => (
                          <React.Fragment key={j}>
                            {j > 0 && (
                              <span className="text-[10px] text-muted-foreground">+</span>
                            )}
                            <kbd className="inline-flex items-center justify-center px-1.5 py-0.5 rounded border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 text-[11px] font-mono font-medium text-foreground min-w-[24px] text-center">
                              {key}
                            </kbd>
                          </React.Fragment>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-1.5 text-muted-foreground text-xs">
                      {shortcut.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
});
