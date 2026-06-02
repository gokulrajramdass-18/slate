/**
 * MemoryConfigSection
 *
 * Reusable config UI for an agent's 4-layer agentic memory:
 *   Short-Term, Episodic, Semantic, Procedural.
 *
 * Each layer is a row with:
 *   - a Switch to enable/disable it
 *   - parameter inputs that appear inline when the switch is on
 *
 * The component is fully controlled — `value` and `onChange` move the entire
 * MemoryConfig object, mirroring the rest of the agent form's pattern.
 *
 * When `agentId` is set (i.e. we're editing an existing agent rather than
 * creating one), an "Open Memory Inspector" link surfaces, taking the user
 * to the per-layer browser at /agents/standalone/:id/memory.
 */

import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Brain, Clock, Database, Zap, ExternalLink } from "lucide-react";
import { useRouter } from "@/lib/routing/navigation";

export interface MemoryConfig {
  short_term_enabled: boolean;
  episodic_enabled: boolean;
  episodic_retention_days: number;
  episodic_max_entries: number;
  semantic_enabled: boolean;
  semantic_max_facts: number;
  procedural_enabled: boolean;
  procedural_min_attempts: number;
  procedural_min_success_rate: number;
}

interface Props {
  value: MemoryConfig;
  onChange: (next: MemoryConfig) => void;
  /** When set, an "Open Inspector" link appears (edit-mode only). */
  agentId?: string | null;
}

export function MemoryConfigSection({ value, onChange, agentId }: Props) {
  const router = useRouter();
  const set = (patch: Partial<MemoryConfig>) => onChange({ ...value, ...patch });

  return (
    <div className="space-y-3 max-h-[280px] overflow-y-auto pr-1">
      {/* Short-Term */}
      <LayerRow
        icon={<Zap className="w-4 h-4 text-amber-500" />}
        title="Short-Term"
        subtitle="Active variables & current prompt — lives only for one execution."
        enabled={value.short_term_enabled}
        onToggle={(on) => set({ short_term_enabled: on })}
      />

      <Separator />

      {/* Episodic */}
      <LayerRow
        icon={<Clock className="w-4 h-4 text-blue-500" />}
        title="Episodic"
        subtitle="Past interactions — “user prefers 2 decimals, said last Tuesday.”"
        enabled={value.episodic_enabled}
        onToggle={(on) => set({ episodic_enabled: on })}
      >
        <div className="grid grid-cols-2 gap-3 pt-2">
          <NumberField
            label="Retention (days)"
            value={value.episodic_retention_days}
            min={1}
            max={3650}
            onChange={(v) => set({ episodic_retention_days: v })}
          />
          <NumberField
            label="Max entries"
            value={value.episodic_max_entries}
            min={10}
            max={10000}
            onChange={(v) => set({ episodic_max_entries: v })}
          />
        </div>
      </LayerRow>

      <Separator />

      {/* Semantic */}
      <LayerRow
        icon={<Database className="w-4 h-4 text-purple-500" />}
        title="Semantic"
        subtitle="Durable facts the agent has chosen to remember (with embeddings)."
        enabled={value.semantic_enabled}
        onToggle={(on) => set({ semantic_enabled: on })}
      >
        <div className="grid grid-cols-2 gap-3 pt-2">
          <NumberField
            label="Max facts"
            value={value.semantic_max_facts}
            min={10}
            max={10000}
            onChange={(v) => set({ semantic_max_facts: v })}
          />
        </div>
      </LayerRow>

      <Separator />

      {/* Procedural */}
      <LayerRow
        icon={<Brain className="w-4 h-4 text-emerald-500" />}
        title="Procedural"
        subtitle="Tool-success patterns — auto-learned from execution history."
        enabled={value.procedural_enabled}
        onToggle={(on) => set({ procedural_enabled: on })}
        badge={!value.procedural_enabled ? "Recommended off until history accrues" : undefined}
      >
        <div className="grid grid-cols-2 gap-3 pt-2">
          <NumberField
            label="Min attempts"
            value={value.procedural_min_attempts}
            min={1}
            max={100}
            onChange={(v) => set({ procedural_min_attempts: v })}
          />
          <div className="space-y-1.5">
            <Label className="text-xs">Min success rate ({Math.round(value.procedural_min_success_rate * 100)}%)</Label>
            <Slider
              min={0}
              max={1}
              step={0.05}
              value={[value.procedural_min_success_rate]}
              onValueChange={([v]) => set({ procedural_min_success_rate: v })}
            />
          </div>
        </div>
      </LayerRow>

      {agentId && (
        <>
          <Separator />
          <button
            type="button"
            className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 hover:underline"
            onClick={() => router.push(`/agents/standalone/${agentId}/memory`)}
          >
            <ExternalLink className="w-3 h-3" />
            Open Memory Inspector for this agent
          </button>
        </>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

interface LayerRowProps {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  enabled: boolean;
  onToggle: (on: boolean) => void;
  badge?: string;
  children?: React.ReactNode;
}

function LayerRow({ icon, title, subtitle, enabled, onToggle, badge, children }: LayerRowProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 min-w-0">
          <div className="mt-0.5">{icon}</div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{title}</span>
              {badge && (
                <Badge variant="outline" className="text-[10px] h-4 px-1.5 font-normal">
                  {badge}
                </Badge>
              )}
            </div>
            <div className="text-xs text-muted-foreground leading-snug">{subtitle}</div>
          </div>
        </div>
        <Switch checked={enabled} onCheckedChange={onToggle} />
      </div>
      {enabled && children}
    </div>
  );
}

interface NumberFieldProps {
  label: string;
  value: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
}

function NumberField({ label, value, min, max, onChange }: NumberFieldProps) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      <Input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (!Number.isNaN(n)) onChange(n);
        }}
        className="h-8 text-xs"
      />
    </div>
  );
}
