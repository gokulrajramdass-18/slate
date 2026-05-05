import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PublishDialog } from "../PublishDialog";

describe("PublishDialog", () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onPublish: vi.fn().mockResolvedValue(undefined),
    hasUnpublishedChanges: true,
  };

  it("renders dialog title and description when open", () => {
    render(<PublishDialog {...defaultProps} />);
    expect(screen.getByText("Publish Microsite")).toBeInTheDocument();
    expect(
      screen.getByText(/create a new version and make your microsite publicly/)
    ).toBeInTheDocument();
  });

  it("does not render content when closed", () => {
    render(<PublishDialog {...defaultProps} open={false} />);
    expect(screen.queryByText("Publish Microsite")).not.toBeInTheDocument();
  });

  it("shows warning when no unpublished changes", () => {
    render(<PublishDialog {...defaultProps} hasUnpublishedChanges={false} />);
    expect(
      screen.getByText(/No changes since last publish/)
    ).toBeInTheDocument();
  });

  it("does not show warning when there are unpublished changes", () => {
    render(<PublishDialog {...defaultProps} hasUnpublishedChanges={true} />);
    expect(
      screen.queryByText(/No changes since last publish/)
    ).not.toBeInTheDocument();
  });

  it("calls onPublish with version message when submitted", async () => {
    const user = userEvent.setup();
    const onPublish = vi.fn().mockResolvedValue(undefined);
    render(<PublishDialog {...defaultProps} onPublish={onPublish} />);

    const textarea = screen.getByPlaceholderText(
      "Describe what changed in this version..."
    );
    await user.type(textarea, "Updated hero section");
    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(onPublish).toHaveBeenCalledWith("Updated hero section");
    });
  });

  it("calls onPublish with undefined when no message provided", async () => {
    const user = userEvent.setup();
    const onPublish = vi.fn().mockResolvedValue(undefined);
    render(<PublishDialog {...defaultProps} onPublish={onPublish} />);

    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(onPublish).toHaveBeenCalledWith(undefined);
    });
  });

  it("shows loading state while publishing", async () => {
    const user = userEvent.setup();
    let resolvePublish: () => void;
    const onPublish = vi.fn(
      () => new Promise<void>((resolve) => { resolvePublish = resolve; })
    );

    render(<PublishDialog {...defaultProps} onPublish={onPublish} />);

    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(screen.getByText("Publishing...")).toBeInTheDocument();
    });

    resolvePublish!();

    await waitFor(() => {
      expect(screen.queryByText("Publishing...")).not.toBeInTheDocument();
    });
  });

  it("calls onOpenChange(false) when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(<PublishDialog {...defaultProps} onOpenChange={onOpenChange} />);

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("closes dialog after successful publish", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onPublish = vi.fn().mockResolvedValue(undefined);
    render(
      <PublishDialog
        {...defaultProps}
        onOpenChange={onOpenChange}
        onPublish={onPublish}
      />
    );

    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it("does not close dialog on publish failure", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onPublish = vi.fn().mockRejectedValue(new Error("Server error"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <PublishDialog
        {...defaultProps}
        onOpenChange={onOpenChange}
        onPublish={onPublish}
      />
    );

    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });

    // onOpenChange should not have been called with false (except for Cancel)
    expect(
      onOpenChange.mock.calls.filter((c) => c[0] === false)
    ).toHaveLength(0);

    consoleSpy.mockRestore();
  });
});
