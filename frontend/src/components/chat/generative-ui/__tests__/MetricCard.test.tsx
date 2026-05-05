import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "../MetricCard";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Total Revenue" value={125000} />);

    expect(screen.getByText("Total Revenue")).toBeInTheDocument();
    expect(screen.getByText("125,000")).toBeInTheDocument();
  });

  it("renders string value", () => {
    render(<MetricCard label="Status" value="Healthy" />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("renders unit", () => {
    render(<MetricCard label="Response Time" value={42} unit="ms" />);
    expect(screen.getByText("ms")).toBeInTheDocument();
  });

  it("renders positive change with up arrow", () => {
    render(<MetricCard label="Growth" value={100} change={12.5} />);
    expect(screen.getByText("+12.5%")).toBeInTheDocument();
  });

  it("renders negative change", () => {
    render(<MetricCard label="Errors" value={5} change={-8.3} />);
    expect(screen.getByText("-8.3%")).toBeInTheDocument();
  });

  it("renders zero change as neutral", () => {
    render(<MetricCard label="Stable" value={100} change={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("renders change label", () => {
    render(
      <MetricCard
        label="Sales"
        value={500}
        change={15}
        change_label="vs last week"
      />
    );
    expect(screen.getByText("vs last week")).toBeInTheDocument();
  });

  it("renders icon placeholder from first letter", () => {
    render(<MetricCard label="Revenue" value={100} />);
    expect(screen.getByText("R")).toBeInTheDocument();
  });

  it("does not render change section when change is undefined", () => {
    const { container } = render(<MetricCard label="Test" value={100} />);
    // No percentage sign should be present
    expect(container.textContent).not.toContain("%");
  });
});
