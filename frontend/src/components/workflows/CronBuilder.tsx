/**
 * Cron Builder Component
 *
 * Visual cron expression builder with presets and next run preview.
 */

'use client';

import React from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Clock, Calendar } from 'lucide-react';
import { format, addMinutes, addHours, addDays, addWeeks, addMonths } from 'date-fns';

// ============================================================================
// Cron Builder Component
// ============================================================================

interface CronBuilderProps {
  value: string;
  onChange: (value: string) => void;
}

export function CronBuilder({ value, onChange }: CronBuilderProps) {
  const [mode, setMode] = React.useState<'simple' | 'advanced'>('simple');

  // Parse cron expression
  const parts = value.split(' ');
  const [minute = '*', hour = '*', dayOfMonth = '*', month = '*', dayOfWeek = '*'] = parts;

  // Calculate next run times
  const getNextRuns = (cronExpr: string): Date[] => {
    // Simple approximation for common patterns
    const now = new Date();
    const runs: Date[] = [];

    try {
      if (cronExpr === '0 9 * * *') {
        // Daily at 9 AM
        let next = new Date(now);
        next.setHours(9, 0, 0, 0);
        if (next <= now) next = addDays(next, 1);
        for (let i = 0; i < 5; i++) {
          runs.push(new Date(next));
          next = addDays(next, 1);
        }
      } else if (cronExpr === '0 */6 * * *') {
        // Every 6 hours
        let next = new Date(now);
        next.setMinutes(0, 0, 0);
        const nextHour = Math.ceil(next.getHours() / 6) * 6;
        next.setHours(nextHour);
        if (next <= now) next = addHours(next, 6);
        for (let i = 0; i < 5; i++) {
          runs.push(new Date(next));
          next = addHours(next, 6);
        }
      } else if (cronExpr === '*/15 * * * *') {
        // Every 15 minutes
        let next = new Date(now);
        const nextMinute = Math.ceil(next.getMinutes() / 15) * 15;
        next.setMinutes(nextMinute, 0, 0);
        if (next <= now) next = addMinutes(next, 15);
        for (let i = 0; i < 5; i++) {
          runs.push(new Date(next));
          next = addMinutes(next, 15);
        }
      } else if (cronExpr === '0 0 * * 1') {
        // Every Monday at midnight
        let next = new Date(now);
        next.setHours(0, 0, 0, 0);
        while (next.getDay() !== 1 || next <= now) {
          next = addDays(next, 1);
        }
        for (let i = 0; i < 5; i++) {
          runs.push(new Date(next));
          next = addWeeks(next, 1);
        }
      } else if (cronExpr === '0 0 1 * *') {
        // First day of month at midnight
        let next = new Date(now);
        next.setDate(1);
        next.setHours(0, 0, 0, 0);
        if (next <= now) next = addMonths(next, 1);
        for (let i = 0; i < 5; i++) {
          runs.push(new Date(next));
          next = addMonths(next, 1);
        }
      } else {
        // Generic fallback - show current time + intervals
        for (let i = 1; i <= 5; i++) {
          runs.push(addHours(now, i));
        }
      }
    } catch (e) {
      // Fallback on error
      for (let i = 1; i <= 5; i++) {
        runs.push(addHours(now, i));
      }
    }

    return runs;
  };

  const nextRuns = getNextRuns(value);

  // Presets
  const presets = [
    { label: 'Every 15 minutes', value: '*/15 * * * *' },
    { label: 'Every hour', value: '0 * * * *' },
    { label: 'Every 6 hours', value: '0 */6 * * *' },
    { label: 'Daily at 9 AM', value: '0 9 * * *' },
    { label: 'Daily at midnight', value: '0 0 * * *' },
    { label: 'Every Monday at 9 AM', value: '0 9 * * 1' },
    { label: 'First day of month', value: '0 0 1 * *' },
    { label: 'Every weekday at 9 AM', value: '0 9 * * 1-5' },
  ];

  const updateCronPart = (index: number, newValue: string) => {
    const newParts = [...parts];
    while (newParts.length < 5) newParts.push('*');
    newParts[index] = newValue;
    onChange(newParts.join(' '));
  };

  return (
    <div className="space-y-4">
      <Tabs value={mode} onValueChange={(v) => setMode(v as any)}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="simple">
            <Clock className="h-4 w-4 mr-2" />
            Simple
          </TabsTrigger>
          <TabsTrigger value="advanced">
            <Calendar className="h-4 w-4 mr-2" />
            Advanced
          </TabsTrigger>
        </TabsList>

        <TabsContent value="simple" className="space-y-4">
          <div className="space-y-2">
            <Label>Presets</Label>
            <div className="grid grid-cols-2 gap-2">
              {presets.map((preset) => (
                <Button
                  key={preset.value}
                  type="button"
                  variant={value === preset.value ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => onChange(preset.value)}
                  className="justify-start"
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Custom Expression</Label>
            <Input
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder="0 9 * * *"
              className="font-mono"
            />
          </div>
        </TabsContent>

        <TabsContent value="advanced" className="space-y-4">
          <div className="grid grid-cols-5 gap-3">
            <div className="space-y-2">
              <Label className="text-xs">Minute</Label>
              <Select value={minute} onValueChange={(v) => updateCronPart(0, v)}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="*">Every</SelectItem>
                  <SelectItem value="0">:00</SelectItem>
                  <SelectItem value="15">:15</SelectItem>
                  <SelectItem value="30">:30</SelectItem>
                  <SelectItem value="45">:45</SelectItem>
                  <SelectItem value="*/5">Every 5</SelectItem>
                  <SelectItem value="*/10">Every 10</SelectItem>
                  <SelectItem value="*/15">Every 15</SelectItem>
                  <SelectItem value="*/30">Every 30</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs">Hour</Label>
              <Select value={hour} onValueChange={(v) => updateCronPart(1, v)}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="*">Every</SelectItem>
                  <SelectItem value="0">12 AM</SelectItem>
                  <SelectItem value="6">6 AM</SelectItem>
                  <SelectItem value="9">9 AM</SelectItem>
                  <SelectItem value="12">12 PM</SelectItem>
                  <SelectItem value="18">6 PM</SelectItem>
                  <SelectItem value="*/6">Every 6</SelectItem>
                  <SelectItem value="*/12">Every 12</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs">Day</Label>
              <Select value={dayOfMonth} onValueChange={(v) => updateCronPart(2, v)}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="*">Every</SelectItem>
                  <SelectItem value="1">1st</SelectItem>
                  <SelectItem value="15">15th</SelectItem>
                  <SelectItem value="*/7">Every 7</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs">Month</Label>
              <Select value={month} onValueChange={(v) => updateCronPart(3, v)}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="*">Every</SelectItem>
                  <SelectItem value="1">Jan</SelectItem>
                  <SelectItem value="4">Apr</SelectItem>
                  <SelectItem value="7">Jul</SelectItem>
                  <SelectItem value="10">Oct</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs">Day of Week</Label>
              <Select value={dayOfWeek} onValueChange={(v) => updateCronPart(4, v)}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="*">Every</SelectItem>
                  <SelectItem value="1">Mon</SelectItem>
                  <SelectItem value="5">Fri</SelectItem>
                  <SelectItem value="1-5">Weekdays</SelectItem>
                  <SelectItem value="0,6">Weekends</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Expression</Label>
            <Input
              value={value}
              onChange={(e) => onChange(e.target.value)}
              className="font-mono"
            />
            <div className="text-xs text-muted-foreground">
              Format: minute hour day-of-month month day-of-week
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Next Run Preview */}
      <div className="bg-muted/50 p-4 rounded-lg space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Clock className="h-4 w-4" />
          Next 5 Runs
        </div>
        <div className="space-y-1">
          {nextRuns.map((run, index) => (
            <div key={index} className="text-sm text-muted-foreground">
              {index + 1}. {format(run, 'PPpp')}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
