import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TimeSeriesChart } from "../TimeSeriesChart";

const sampleData = [
  { timestamp: "2024-01-01", value: 100 },
  { timestamp: "2024-02-01", value: 150 },
  { timestamp: "2024-03-01", value: 120 },
  { timestamp: "2024-04-01", value: 200 },
  { timestamp: "2024-05-01", value: 180 },
];

describe("TimeSeriesChart", () => {
  it("renders with title", () => {
    render(<TimeSeriesChart title="Monthly Revenue" data={sampleData} />);
    expect(screen.getByText("Monthly Revenue")).toBeInTheDocument();
  });

  it("renders description", () => {
    render(
      <TimeSeriesChart
        title="Chart"
        description="Revenue over time"
        data={sampleData}
      />
    );
    expect(screen.getByText("Revenue over time")).toBeInTheDocument();
  });

  it("displays data point count badge", () => {
    render(<TimeSeriesChart data={sampleData} />);
    expect(screen.getByText("5 points")).toBeInTheDocument();
  });

  it("renders SVG element", () => {
    const { container } = render(<TimeSeriesChart data={sampleData} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
  });

  it("renders SVG path for line", () => {
    const { container } = render(<TimeSeriesChart data={sampleData} />);
    // Should have a line path (stroke, no fill) and possibly area path
    const paths = container.querySelectorAll("path");
    expect(paths.length).toBeGreaterThanOrEqual(1);
  });

  it("renders circles for data points when showDots is true", () => {
    const { container } = render(
      <TimeSeriesChart data={sampleData} showDots={true} />
    );
    // Each data point has a hit area circle + visible dot
    const circles = container.querySelectorAll("circle");
    expect(circles.length).toBeGreaterThanOrEqual(sampleData.length);
  });

  it("shows empty state when no data", () => {
    render(<TimeSeriesChart data={[]} />);
    expect(
      screen.getByText("No data available for chart.")
    ).toBeInTheDocument();
  });

  it("handles single data point without error", () => {
    const { container } = render(
      <TimeSeriesChart data={[{ timestamp: "2024-01-01", value: 42 }]} />
    );
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
  });

  it("renders axis labels when provided", () => {
    render(
      <TimeSeriesChart
        data={sampleData}
        x_label="Month"
        y_label="USD"
      />
    );
    expect(screen.getByText("Month")).toBeInTheDocument();
    expect(screen.getByText("USD")).toBeInTheDocument();
  });
});
