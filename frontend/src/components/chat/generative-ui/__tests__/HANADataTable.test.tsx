import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HANADataTable } from "../HANADataTable";

const sampleColumns = [
  { key: "id", label: "ID", type: "number" as const },
  { key: "name", label: "Name", type: "string" as const },
  { key: "revenue", label: "Revenue", type: "number" as const },
];

const sampleRows = [
  { id: 1, name: "Alpha Corp", revenue: 50000 },
  { id: 2, name: "Beta Inc", revenue: 30000 },
  { id: 3, name: "Gamma LLC", revenue: 70000 },
];

describe("HANADataTable", () => {
  it("renders with title and description", () => {
    render(
      <HANADataTable
        title="Sales Data"
        description="Q4 results"
        columns={sampleColumns}
        rows={sampleRows}
      />
    );

    expect(screen.getByText("Sales Data")).toBeInTheDocument();
    expect(screen.getByText("Q4 results")).toBeInTheDocument();
  });

  it("renders column headers", () => {
    render(<HANADataTable columns={sampleColumns} rows={sampleRows} />);

    expect(screen.getByText("ID")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
  });

  it("renders row data", () => {
    render(<HANADataTable columns={sampleColumns} rows={sampleRows} />);

    expect(screen.getByText("Alpha Corp")).toBeInTheDocument();
    expect(screen.getByText("Beta Inc")).toBeInTheDocument();
    expect(screen.getByText("Gamma LLC")).toBeInTheDocument();
  });

  it("displays metadata badges", () => {
    render(
      <HANADataTable
        columns={sampleColumns}
        rows={sampleRows}
        execution_time_ms={42}
        total_count={150}
      />
    );

    expect(screen.getByText("42ms")).toBeInTheDocument();
    expect(screen.getByText("150 rows")).toBeInTheDocument();
  });

  it("sorts rows when column header is clicked", async () => {
    const user = userEvent.setup();
    render(<HANADataTable columns={sampleColumns} rows={sampleRows} />);

    const nameHeader = screen.getByText("Name");
    await user.click(nameHeader);

    // After ascending sort, Alpha should be first
    const cells = screen.getAllByRole("cell");
    const nameIndex = 1; // second column
    const names = cells
      .filter((_, i) => i % sampleColumns.length === nameIndex)
      .map((c) => c.textContent);
    expect(names).toEqual(["Alpha Corp", "Beta Inc", "Gamma LLC"]);
  });

  it("filters rows when search is used", async () => {
    const user = userEvent.setup();
    render(<HANADataTable columns={sampleColumns} rows={sampleRows} />);

    const searchInput = screen.getByPlaceholderText("Filter results...");
    await user.type(searchInput, "Beta");

    expect(screen.getByText("Beta Inc")).toBeInTheDocument();
    expect(screen.queryByText("Alpha Corp")).not.toBeInTheDocument();
    expect(screen.queryByText("Gamma LLC")).not.toBeInTheDocument();
  });

  it("shows empty state when no data", () => {
    render(<HANADataTable columns={sampleColumns} rows={[]} />);

    expect(screen.getByText("No data available.")).toBeInTheDocument();
  });

  it("shows SQL query when SQL button clicked", async () => {
    const user = userEvent.setup();
    render(
      <HANADataTable
        columns={sampleColumns}
        rows={sampleRows}
        query="SELECT * FROM sales"
      />
    );

    const sqlBtn = screen.getByText("SQL");
    await user.click(sqlBtn);

    expect(screen.getByText("SELECT * FROM sales")).toBeInTheDocument();
  });

  it("truncates rows beyond maxDisplayRows", () => {
    const manyRows = Array.from({ length: 10 }, (_, i) => ({
      id: i,
      name: `Row ${i}`,
      revenue: i * 1000,
    }));

    render(
      <HANADataTable
        columns={sampleColumns}
        rows={manyRows}
        maxDisplayRows={3}
      />
    );

    expect(screen.getByText("Row 0")).toBeInTheDocument();
    expect(screen.getByText("Row 2")).toBeInTheDocument();
    expect(screen.queryByText("Row 3")).not.toBeInTheDocument();
    expect(screen.getByText(/limited to 3/)).toBeInTheDocument();
  });
});
