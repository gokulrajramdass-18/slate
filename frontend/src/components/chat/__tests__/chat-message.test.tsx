import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessage } from "../chat-message";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

// Mock react-markdown since it has ESM issues in test environments
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));

vi.mock("remark-gfm", () => ({ default: () => {} }));
vi.mock("rehype-highlight", () => ({ default: () => {} }));
vi.mock("rehype-raw", () => ({ default: () => {} }));

// Mock GenerativeUIRenderer
vi.mock("@/components/chat/generative-ui/GenerativeUIRenderer", () => ({
  GenerativeUIRenderer: ({
    components,
    toolResults,
  }: {
    components?: unknown[];
    toolResults?: unknown[];
  }) => (
    <div data-testid="generative-ui">
      {components && <span>components:{components.length}</span>}
      {toolResults && <span>toolResults:{toolResults.length}</span>}
    </div>
  ),
}));

function makeMessage(overrides: Partial<ChatMessageType> = {}): ChatMessageType {
  return {
    id: "msg-1",
    session_id: "session-1",
    role: "assistant",
    content: "Hello, world!",
    created: new Date().toISOString(),
    ...overrides,
  };
}

describe("ChatMessage", () => {
  describe("user messages", () => {
    it("renders user message as plain text", () => {
      render(
        <ChatMessage message={makeMessage({ role: "user", content: "Hi there" })} />
      );
      expect(screen.getByText("Hi there")).toBeInTheDocument();
    });
  });

  describe("markdown mode (default)", () => {
    it("renders assistant message with markdown by default", () => {
      render(<ChatMessage message={makeMessage()} />);
      expect(screen.getByTestId("markdown")).toBeInTheDocument();
    });

    it("does not render generative UI in markdown mode", () => {
      render(<ChatMessage message={makeMessage()} />);
      expect(screen.queryByTestId("generative-ui")).not.toBeInTheDocument();
    });
  });

  describe("generative mode", () => {
    it("renders generative UI components when available", () => {
      const uiComponents = JSON.stringify([
        { component_type: "table", props: { title: "Test" } },
      ]);

      render(
        <ChatMessage
          message={makeMessage({
            render_mode: "generative",
            ui_components: uiComponents,
          })}
        />
      );

      expect(screen.getByTestId("generative-ui")).toBeInTheDocument();
      expect(screen.getByText("components:1")).toBeInTheDocument();
    });

    it("falls back to markdown when no generative content", () => {
      render(
        <ChatMessage
          message={makeMessage({ render_mode: "generative" })}
        />
      );

      expect(screen.getByTestId("markdown")).toBeInTheDocument();
    });
  });

  describe("hybrid mode", () => {
    it("renders both markdown and generative UI", () => {
      const toolResults = JSON.stringify([
        {
          tool_name: "query",
          tool_call_id: "c1",
          execution_time_ms: 50,
          result_type: "table",
          data: {},
        },
      ]);

      render(
        <ChatMessage
          message={makeMessage({
            render_mode: "hybrid",
            tool_results: toolResults,
          })}
        />
      );

      expect(screen.getByTestId("markdown")).toBeInTheDocument();
      expect(screen.getByTestId("generative-ui")).toBeInTheDocument();
    });
  });

  describe("sources", () => {
    it("renders source badges", () => {
      render(
        <ChatMessage
          message={makeMessage({
            sources: [
              {
                source_id: "s1",
                source_name: "Sales Data",
                chunks_included: 3,
                tokens: 500,
              },
            ],
          })}
        />
      );

      expect(screen.getByText(/Sales Data/)).toBeInTheDocument();
    });
  });

  describe("copy button", () => {
    it("shows copy button for assistant messages", () => {
      render(<ChatMessage message={makeMessage()} />);
      expect(screen.getByText("Copy")).toBeInTheDocument();
    });

    it("does not show copy button for user messages", () => {
      render(
        <ChatMessage message={makeMessage({ role: "user" })} />
      );
      expect(screen.queryByText("Copy")).not.toBeInTheDocument();
    });

    it("does not show copy button when streaming", () => {
      render(<ChatMessage message={makeMessage()} isStreaming />);
      expect(screen.queryByText("Copy")).not.toBeInTheDocument();
    });
  });

  describe("JSON parsing resilience", () => {
    it("handles invalid ui_components JSON", () => {
      render(
        <ChatMessage
          message={makeMessage({
            render_mode: "generative",
            ui_components: "not-valid-json",
          })}
        />
      );
      // Should fall back to markdown without crashing
      expect(screen.getByTestId("markdown")).toBeInTheDocument();
    });

    it("handles invalid tool_results JSON", () => {
      render(
        <ChatMessage
          message={makeMessage({
            render_mode: "hybrid",
            tool_results: "{broken",
          })}
        />
      );
      // Should still render markdown part
      expect(screen.getByTestId("markdown")).toBeInTheDocument();
    });
  });
});
