import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../StatusBadge";

describe("StatusBadge", () => {
  it("renders 'Draft' with secondary variant for draft status", () => {
    const { container } = render(<StatusBadge status="draft" />);
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-secondary");
  });

  it("renders 'Published' with default variant for published status", () => {
    const { container } = render(<StatusBadge status="published" />);
    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-primary");
  });

  it("renders 'Blocked' with destructive variant for blocked status", () => {
    const { container } = render(<StatusBadge status="blocked" />);
    expect(screen.getByText("Blocked")).toBeInTheDocument();
    expect(container.firstChild).toHaveClass("bg-destructive");
  });

  it("applies custom className", () => {
    const { container } = render(
      <StatusBadge status="draft" className="ml-4" />
    );
    expect(container.firstChild).toHaveClass("ml-4");
  });
});
