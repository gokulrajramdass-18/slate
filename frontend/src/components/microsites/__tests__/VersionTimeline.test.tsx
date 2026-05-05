import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VersionTimeline } from "../VersionTimeline";
import type { MicrositeVersion } from "@/lib/types";

// Mock the API client
vi.mock("@/lib/api/microsites", () => ({
  micrositesApi: {
    listVersions: vi.fn(),
  },
}));

import { micrositesApi } from "@/lib/api/microsites";

const mockVersions: MicrositeVersion[] = [
  {
    id: "v1",
    microsite_id: "ms-1",
    version_number: 1,
    full_html: "<html>v1</html>",
    created_by: "alice",
    published_at: "2026-03-20T10:00:00Z",
    created: "2026-03-20T10:00:00Z",
  },
  {
    id: "v2",
    microsite_id: "ms-1",
    version_number: 2,
    full_html: "<html>v2</html>",
    created_by: "bob",
    published_at: "2026-03-22T14:00:00Z",
    created: "2026-03-22T14:00:00Z",
  },
];

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("VersionTimeline", () => {
  const defaultProps = {
    micrositeId: "ms-1",
    activeVersionId: "v2",
    onPreview: vi.fn(),
    onRestore: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    vi.mocked(micrositesApi.listVersions).mockReturnValue(
      new Promise(() => {}) // never resolves
    );

    render(<VersionTimeline {...defaultProps} />, { wrapper: createWrapper() });

    expect(screen.getByText("Loading versions...")).toBeInTheDocument();
  });

  it("shows empty state when no versions exist", async () => {
    vi.mocked(micrositesApi.listVersions).mockResolvedValue([]);

    render(<VersionTimeline {...defaultProps} />, { wrapper: createWrapper() });

    expect(
      await screen.findByText(/No published versions yet/)
    ).toBeInTheDocument();
  });

  it("displays version list with version numbers", async () => {
    vi.mocked(micrositesApi.listVersions).mockResolvedValue(mockVersions);

    render(<VersionTimeline {...defaultProps} />, { wrapper: createWrapper() });

    expect(await screen.findByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText("Version 2")).toBeInTheDocument();
  });

  it("displays the Version History title", async () => {
    vi.mocked(micrositesApi.listVersions).mockResolvedValue(mockVersions);

    render(<VersionTimeline {...defaultProps} />, { wrapper: createWrapper() });

    expect(await screen.findByText("Version History")).toBeInTheDocument();
  });

  it("shows 'Active' badge on the active version", async () => {
    vi.mocked(micrositesApi.listVersions).mockResolvedValue(mockVersions);

    render(<VersionTimeline {...defaultProps} activeVersionId="v2" />, {
      wrapper: createWrapper(),
    });

    expect(await screen.findByText("Active")).toBeInTheDocument();
  });

  it("shows creator names", async () => {
    vi.mocked(micrositesApi.listVersions).mockResolvedValue(mockVersions);

    render(<VersionTimeline {...defaultProps} />, { wrapper: createWrapper() });

    expect(await screen.findByText("Published by alice")).toBeInTheDocument();
    expect(screen.getByText("Published by bob")).toBeInTheDocument();
  });

  it("calls onPreview when Preview button is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(micrositesApi.listVersions).mockResolvedValue(mockVersions);
    const onPreview = vi.fn();

    render(<VersionTimeline {...defaultProps} onPreview={onPreview} />, {
      wrapper: createWrapper(),
    });

    const previewButtons = await screen.findAllByText("Preview");
    await user.click(previewButtons[0]);

    expect(onPreview).toHaveBeenCalledWith(mockVersions[0]);
  });

  it("calls onRestore when Restore button is clicked on non-active version", async () => {
    const user = userEvent.setup();
    vi.mocked(micrositesApi.listVersions).mockResolvedValue(mockVersions);
    const onRestore = vi.fn();

    render(
      <VersionTimeline
        {...defaultProps}
        activeVersionId="v2"
        onRestore={onRestore}
      />,
      { wrapper: createWrapper() }
    );

    const restoreButton = await screen.findByText("Restore");
    await user.click(restoreButton);

    expect(onRestore).toHaveBeenCalledWith(mockVersions[0]);
  });

  it("does not show Restore button for the active version", async () => {
    vi.mocked(micrositesApi.listVersions).mockResolvedValue(mockVersions);

    render(<VersionTimeline {...defaultProps} activeVersionId="v2" />, {
      wrapper: createWrapper(),
    });

    await screen.findByText("Version 1");

    // Only one Restore button (for v1, not v2)
    const restoreButtons = screen.getAllByText("Restore");
    expect(restoreButtons).toHaveLength(1);
  });

  it("renders Preview button for every version", async () => {
    vi.mocked(micrositesApi.listVersions).mockResolvedValue(mockVersions);

    render(<VersionTimeline {...defaultProps} />, { wrapper: createWrapper() });

    const previewButtons = await screen.findAllByText("Preview");
    expect(previewButtons).toHaveLength(2);
  });
});
