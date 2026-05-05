import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { APIResponseViewer } from "../APIResponseViewer";

describe("APIResponseViewer", () => {
  it("renders with title", () => {
    render(<APIResponseViewer title="Users API" data={{ name: "test" }} />);
    expect(screen.getByText("Users API")).toBeInTheDocument();
  });

  it("renders default title when none provided", () => {
    render(<APIResponseViewer data={{ key: "value" }} />);
    expect(screen.getByText("API Response")).toBeInTheDocument();
  });

  it("displays status code badge", () => {
    render(<APIResponseViewer data={{}} status_code={200} />);
    expect(screen.getByText("200")).toBeInTheDocument();
  });

  it("displays execution time", () => {
    render(<APIResponseViewer data={{}} execution_time_ms={150} />);
    expect(screen.getByText("150ms")).toBeInTheDocument();
  });

  it("displays endpoint and method", () => {
    render(
      <APIResponseViewer
        data={{}}
        endpoint="/api/users"
        method="GET"
      />
    );
    expect(screen.getByText("/api/users")).toBeInTheDocument();
    expect(screen.getByText("GET")).toBeInTheDocument();
  });

  it("renders JSON string values", () => {
    render(<APIResponseViewer data={{ name: "Alice" }} defaultExpandDepth={2} />);
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
  });

  it("renders JSON number values", () => {
    render(<APIResponseViewer data={{ count: 42 }} defaultExpandDepth={2} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders null values", () => {
    render(<APIResponseViewer data={{ value: null }} defaultExpandDepth={2} />);
    expect(screen.getByText("null")).toBeInTheDocument();
  });

  it("renders boolean values", () => {
    render(<APIResponseViewer data={{ active: true }} defaultExpandDepth={2} />);
    expect(screen.getByText("true")).toBeInTheDocument();
  });

  it("has a copy button", () => {
    render(<APIResponseViewer data={{ key: "value" }} />);
    expect(screen.getByText("Copy")).toBeInTheDocument();
  });

  it("renders empty object", () => {
    render(<APIResponseViewer data={{}} defaultExpandDepth={2} />);
    expect(screen.getByText("{}")).toBeInTheDocument();
  });

  it("renders empty array", () => {
    render(<APIResponseViewer data={[]} defaultExpandDepth={2} />);
    expect(screen.getByText("[]")).toBeInTheDocument();
  });
});
