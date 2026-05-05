import { describe, it, expect, beforeEach } from "vitest";
import { ComponentRegistry } from "../component-registry";
import type { ToolResultData } from "@/lib/types";

function MockComponentA() {
  return null;
}
function MockComponentB() {
  return null;
}
function MockComponentC() {
  return null;
}

function makeToolResult(overrides: Partial<ToolResultData> = {}): ToolResultData {
  return {
    tool_name: "test_tool",
    tool_call_id: "call-1",
    execution_time_ms: 100,
    result_type: "table",
    data: null,
    ...overrides,
  };
}

describe("ComponentRegistry", () => {
  let registry: ComponentRegistry;

  beforeEach(() => {
    registry = new ComponentRegistry();
  });

  it("returns null when no components are registered", () => {
    const result = registry.getComponent(makeToolResult());
    expect(result).toBeNull();
  });

  it("registers and retrieves a component", () => {
    registry.register({
      name: "table",
      component: MockComponentA,
      matcher: (r) => r.result_type === "table",
      priority: 100,
    });

    const result = registry.getComponent(makeToolResult({ result_type: "table" }));
    expect(result).toBe(MockComponentA);
  });

  it("returns null when no matcher matches", () => {
    registry.register({
      name: "table",
      component: MockComponentA,
      matcher: (r) => r.result_type === "table",
      priority: 100,
    });

    const result = registry.getComponent(makeToolResult({ result_type: "json" }));
    expect(result).toBeNull();
  });

  it("returns higher priority component when multiple match", () => {
    registry.register({
      name: "low",
      component: MockComponentA,
      matcher: (r) => r.result_type === "table",
      priority: 10,
    });
    registry.register({
      name: "high",
      component: MockComponentB,
      matcher: (r) => r.result_type === "table",
      priority: 100,
    });

    const result = registry.getComponent(makeToolResult({ result_type: "table" }));
    expect(result).toBe(MockComponentB);
  });

  it("overwrites registration with same name", () => {
    registry.register({
      name: "table",
      component: MockComponentA,
      matcher: (r) => r.result_type === "table",
      priority: 100,
    });
    registry.register({
      name: "table",
      component: MockComponentB,
      matcher: (r) => r.result_type === "table",
      priority: 100,
    });

    const result = registry.getComponent(makeToolResult({ result_type: "table" }));
    expect(result).toBe(MockComponentB);
    expect(registry.getRegisteredNames()).toEqual(["table"]);
  });

  it("matchComponent convenience method works", () => {
    registry.register({
      name: "hana",
      component: MockComponentA,
      matcher: (r) => r.tool_name.includes("query_hana") && r.result_type === "table",
      priority: 100,
    });

    expect(registry.matchComponent("query_hana_db", "table")).toBe(MockComponentA);
    expect(registry.matchComponent("other_tool", "table")).toBeNull();
  });

  it("getRegisteredNames returns all names", () => {
    registry.register({
      name: "a",
      component: MockComponentA,
      matcher: () => true,
      priority: 50,
    });
    registry.register({
      name: "b",
      component: MockComponentB,
      matcher: () => true,
      priority: 100,
    });
    registry.register({
      name: "c",
      component: MockComponentC,
      matcher: () => true,
      priority: 10,
    });

    // Sorted by priority descending
    expect(registry.getRegisteredNames()).toEqual(["b", "a", "c"]);
  });

  it("swallows matcher errors and skips to next", () => {
    registry.register({
      name: "broken",
      component: MockComponentA,
      matcher: () => {
        throw new Error("boom");
      },
      priority: 200,
    });
    registry.register({
      name: "good",
      component: MockComponentB,
      matcher: () => true,
      priority: 100,
    });

    const result = registry.getComponent(makeToolResult());
    expect(result).toBe(MockComponentB);
  });
});
