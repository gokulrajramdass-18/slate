import type { ComponentType } from "react";
import type { ToolResultData } from "@/lib/types";

/**
 * Registration entry for a generative UI component.
 */
export interface ComponentRegistration {
  /** Unique name for this registration */
  name: string;
  /** The React component to render */
  component: ComponentType<any>;
  /** Function that tests whether this component should handle a given tool result */
  matcher: (result: ToolResultData) => boolean;
  /** Higher priority registrations are tested first (default 0) */
  priority: number;
}

/**
 * Registry that maps tool results to the appropriate React component.
 *
 * Components self-register at module load time. The renderer queries the
 * registry to find the best component for each tool result.
 */
export class ComponentRegistry {
  private registrations: ComponentRegistration[] = [];

  /**
   * Register a component. Duplicate names overwrite the previous entry.
   */
  register(reg: ComponentRegistration): void {
    // Remove existing registration with same name
    this.registrations = this.registrations.filter((r) => r.name !== reg.name);
    this.registrations.push(reg);
    // Keep sorted by priority descending for fast matching
    this.registrations.sort((a, b) => b.priority - a.priority);
  }

  /**
   * Find the best component for a given tool result.
   * Returns null if no registration matches.
   */
  getComponent(toolResult: ToolResultData): ComponentType<any> | null {
    for (const reg of this.registrations) {
      try {
        if (reg.matcher(toolResult)) {
          return reg.component;
        }
      } catch {
        // Swallow matcher errors - skip this registration
      }
    }
    return null;
  }

  /**
   * Convenience method: match by tool name and result type directly.
   */
  matchComponent(
    toolName: string,
    resultType: string
  ): ComponentType<any> | null {
    return this.getComponent({
      tool_name: toolName,
      tool_call_id: "",
      execution_time_ms: 0,
      result_type: resultType as ToolResultData["result_type"],
      data: null,
    });
  }

  /**
   * Get all registered component names (useful for debugging).
   */
  getRegisteredNames(): string[] {
    return this.registrations.map((r) => r.name);
  }
}

/** Singleton registry instance shared across the application */
export const componentRegistry = new ComponentRegistry();
