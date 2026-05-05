import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AgentStepsViewer } from '../agent-steps-viewer';
import type { AgentStep } from '@/lib/types';

describe('AgentStepsViewer', () => {
  it('renders nothing when steps array is empty', () => {
    const { container } = render(<AgentStepsViewer steps={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when steps is undefined', () => {
    const { container } = render(<AgentStepsViewer steps={undefined as any} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders steps correctly - always expanded', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Analyzing query',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
      {
        step_type: 'tool_call',
        content: 'Querying database',
        status: 'running',
        timestamp: new Date().toISOString(),
        metadata: { tool_name: 'query_hana' },
      },
    ];

    render(<AgentStepsViewer steps={steps} />);

    expect(screen.getByText(/Agent Execution Steps \(2\)/)).toBeInTheDocument();
    expect(screen.getByText(/Analyzing query/)).toBeInTheDocument();
    expect(screen.getByText(/Querying database/)).toBeInTheDocument();
  });

  it('shows live badge when streaming', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Processing...',
        status: 'running',
        timestamp: new Date().toISOString(),
      },
    ];

    render(<AgentStepsViewer steps={steps} isStreaming={true} />);
    expect(screen.getByText(/Live/)).toBeInTheDocument();
  });

  it('does not show live badge when not streaming', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Processing...',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
    ];

    render(<AgentStepsViewer steps={steps} isStreaming={false} />);
    expect(screen.queryByText(/Live/)).not.toBeInTheDocument();
  });

  it('displays duration when provided', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'tool_call',
        content: 'Executed query',
        status: 'completed',
        timestamp: new Date().toISOString(),
        metadata: { duration_ms: 1250, tool_name: 'query_hana' },
      },
    ];

    render(<AgentStepsViewer steps={steps} />);
    expect(screen.getByText(/1250ms/)).toBeInTheDocument();
  });

  it('displays error message when present', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'tool_call',
        content: 'Failed to execute',
        status: 'error',
        timestamp: new Date().toISOString(),
        metadata: { error_message: 'Connection timeout' },
      },
    ];

    render(<AgentStepsViewer steps={steps} />);
    // Check that error section exists - use getAllByText since text appears in both error div and details
    const errorTexts = screen.getAllByText(/Connection timeout/);
    expect(errorTexts.length).toBeGreaterThan(0);
    // Check Error: label exists
    expect(screen.getByText(/Error:/)).toBeInTheDocument();
  });

  it('renders correct step labels for different step types', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Analyzing',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
      {
        step_type: 'tool_call',
        content: 'Calling tool',
        status: 'completed',
        timestamp: new Date().toISOString(),
        metadata: { tool_name: 'custom_tool' },
      },
      {
        step_type: 'tool_result',
        content: 'Got result',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
      {
        step_type: 'response',
        content: 'Generating',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
    ];

    render(<AgentStepsViewer steps={steps} />);

    // Check step labels (they appear as font-semibold spans)
    expect(screen.getAllByText('Analyzing')[0]).toBeInTheDocument();
    expect(screen.getAllByText('custom_tool')[0]).toBeInTheDocument();
    expect(screen.getAllByText('Tool Result')[0]).toBeInTheDocument();
    expect(screen.getAllByText('Generating Response')[0]).toBeInTheDocument();
  });

  it('renders status badges for all statuses', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Step 1',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
      {
        step_type: 'thinking',
        content: 'Step 2',
        status: 'running',
        timestamp: new Date().toISOString(),
      },
      {
        step_type: 'thinking',
        content: 'Step 3',
        status: 'error',
        timestamp: new Date().toISOString(),
      },
      {
        step_type: 'thinking',
        content: 'Step 4',
        status: 'pending',
        timestamp: new Date().toISOString(),
      },
    ];

    render(<AgentStepsViewer steps={steps} />);

    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText('error')).toBeInTheDocument();
    expect(screen.getByText('pending')).toBeInTheDocument();
  });

  it('renders tool name from metadata when step type is not tool_call', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'tool_result',
        content: 'Result received',
        status: 'completed',
        timestamp: new Date().toISOString(),
        metadata: { tool_name: 'query_hana_table' },
      },
    ];

    render(<AgentStepsViewer steps={steps} />);
    // Tool name appears in the dedicated "Tool:" section
    const toolSection = screen.getAllByText(/query_hana_table/)[0].closest('.text-xs.text-gray-600');
    expect(toolSection).toBeInTheDocument();
    expect(screen.getByText(/Tool:/)).toBeInTheDocument();
  });

  it('handles multiple steps with mixed statuses', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Analyzing query and available tools',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
      {
        step_type: 'tool_call',
        content: 'Executing: query_hana_table',
        status: 'completed',
        timestamp: new Date().toISOString(),
        metadata: { tool_name: 'query_hana_table', duration_ms: 850 },
      },
      {
        step_type: 'tool_result',
        content: 'Retrieved 42 rows',
        status: 'completed',
        timestamp: new Date().toISOString(),
        metadata: { tool_name: 'query_hana_table', duration_ms: 850 },
      },
      {
        step_type: 'response',
        content: 'Generating response',
        status: 'running',
        timestamp: new Date().toISOString(),
      },
    ];

    render(<AgentStepsViewer steps={steps} />);

    expect(screen.getByText(/Agent Execution Steps \(4\)/)).toBeInTheDocument();
    expect(screen.getByText(/Analyzing query and available tools/)).toBeInTheDocument();
    expect(screen.getByText(/Executing: query_hana_table/)).toBeInTheDocument();
    expect(screen.getByText(/Retrieved 42 rows/)).toBeInTheDocument();
    expect(screen.getByText(/Generating response/)).toBeInTheDocument();
    // Duration badge appears twice (tool_call and tool_result)
    expect(screen.getAllByText(/850ms/)).toHaveLength(2);
  });

  it('always shows steps expanded (no accordion)', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Test step',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
    ];

    const { container } = render(<AgentStepsViewer steps={steps} />);

    // Should NOT have accordion structure anymore
    const accordion = container.querySelector('[data-radix-accordion]');
    expect(accordion).toBeNull();

    // Content should be immediately visible
    expect(screen.getByText('Test step')).toBeInTheDocument();
  });

  it('shows step number badges', () => {
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Step one',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
      {
        step_type: 'thinking',
        content: 'Step two',
        status: 'completed',
        timestamp: new Date().toISOString(),
      },
    ];

    const { container } = render(<AgentStepsViewer steps={steps} />);

    // Should show step numbers 1 and 2
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('displays timestamps when available', () => {
    const timestamp = new Date('2024-03-25T10:30:00Z');
    const steps: AgentStep[] = [
      {
        step_type: 'thinking',
        content: 'Test step',
        status: 'completed',
        timestamp: timestamp.toISOString(),
      },
    ];

    render(<AgentStepsViewer steps={steps} />);

    // Should show formatted time (exact format depends on locale)
    expect(screen.getByText(/Time:/)).toBeInTheDocument();
  });
});
