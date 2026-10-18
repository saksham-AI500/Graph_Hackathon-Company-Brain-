import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '../context/ThemeContext';
import { ComparePage } from '../pages/ComparePage';
import type { CompareResponse, EvalResultsResponse } from '../api/schema';

function renderWithClient(ui: React.ReactElement, initialData?: { evalResults?: EvalResultsResponse | null }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  if (initialData?.evalResults !== undefined) {
    queryClient.setQueryData(['eval_results'], initialData.evalResults);
  }

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>{ui}</ThemeProvider>
    </QueryClientProvider>,
  );
}

const mockCompareResponse: CompareResponse = {
  question: 'Who should review changes to auth and payments?',
  as_of: '2026-09-30',
  graph_on: {
    status: 'VERIFIED',
    answer: 'Caleb Rivers [S1] is the primary code owner.',
    context: 'Synced data',
    ranking: [],
    reasoning: '',
    claims: [
      {
        id: 'C1',
        text: 'Caleb Rivers authored changes.',
        type: 'fact',
        source_ids: ['S1'],
        verified: true,
        verification_path: 'exact_lookup',
      },
    ],
    excluded: [],
    unresolved: [],
    sources: [
      {
        id: 'S1',
        entity: 'pkg/auth/handler.go',
        entity_type: 'File',
        url: 'https://github.com/org/repo/blob/main/pkg/auth/handler.go',
        date: '2026-09-15',
        quote: 'func AuthHandler()',
      },
    ],
    mode: 'graph_on',
    synced_at: '2026-09-30T23:59:59Z',
    model: 'liquid/lfm-2.5-2.6b:free',
    tool_calls: [],
  },
  graph_off: {
    status: 'ANSWERED_UNCERTAIN',
    answer: 'Someone in security or auth might be the reviewer.',
    context: '',
    ranking: [],
    reasoning: '',
    claims: [
      {
        id: 'C1',
        text: 'Security might review.',
        type: 'claim',
        source_ids: [],
        verified: false,
        verification_path: 'unverified',
      },
    ],
    excluded: [],
    unresolved: [],
    sources: [],
    mode: 'graph_off',
    synced_at: '2026-09-30T23:59:59Z',
    model: 'liquid/lfm-2.5-2.6b:free',
    tool_calls: [],
  },
  comparison: {
    on_status: 'VERIFIED',
    off_status: 'ANSWERED_UNCERTAIN',
    on_claims_count: 1,
    off_claims_count: 1,
    on_sources_count: 1,
    off_sources_count: 0,
    fabricated_citations_in_off: 2,
    verified: true,
    difference_counts: null, // Null correct-only counts for single question
  },
};

const mockEvalResults: EvalResultsResponse = {
  run_id: 'dev_v2_20261017_112444',
  timestamp: '2026-10-17T11:24:59.898963+00:00',
  split_name: 'development',
  code_revision: '1deb13b3d5775bb839b70d68058798711f30f0d0',
  architectures: {},
  individual_outcomes: [
    {
      question_id: 'Q1',
      repetition: 1,
      architecture: 'graph_on',
      correct: true,
      timestamp: '2026-10-17T11:24:44.284924+00:00',
    },
    {
      question_id: 'Q1',
      repetition: 1,
      architecture: 'graph_off',
      correct: false,
      timestamp: '2026-10-17T11:24:44.284924+00:00',
    },
    {
      question_id: 'Q2',
      repetition: 1,
      architecture: 'graph_on',
      correct: true,
      timestamp: '2026-10-17T11:24:50.000000+00:00',
    },
    {
      question_id: 'Q2',
      repetition: 1,
      architecture: 'graph_off',
      correct: true,
      timestamp: '2026-10-17T11:24:50.000000+00:00',
    },
  ],
};

describe('ComparePage View Unit Tests', () => {
  it('renders both columns: Graph Off and Graph On with subtitles, badges, and counters', () => {
    renderWithClient(<ComparePage initialSample={mockCompareResponse} />);

    // Column Headers & Subtitles
    expect(screen.getByText('Graph Off')).toBeInTheDocument();
    expect(screen.getByText('Model only, no tools')).toBeInTheDocument();

    expect(screen.getByText('Graph On')).toBeInTheDocument();
    expect(screen.getByText('Graph tools and verifier')).toBeInTheDocument();

    // Exact status badges (appear in column header and in single-question difference strip)
    expect(screen.getAllByText('ANSWERED_UNCERTAIN').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('VERIFIED').length).toBeGreaterThanOrEqual(1);

    // Answers
    expect(screen.getByText(/Someone in security or auth might be the reviewer/i)).toBeInTheDocument();
    expect(screen.getByText(/primary code owner/i)).toBeInTheDocument();

    // Fabricated citations in Graph Off
    expect(screen.getByText('Fabricated citations')).toBeInTheDocument();

    // Graph On source entity button
    expect(screen.getAllByText('[S1]').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('pkg/auth/handler.go')).toBeInTheDocument();
  });

  it('renders aggregate strip with results when eval results exist', () => {
    renderWithClient(<ComparePage initialSample={mockCompareResponse} />, {
      evalResults: mockEvalResults,
    });

    // 4 required aggregate counter cards
    expect(screen.getByText('Correct only with Graph On')).toBeInTheDocument();
    expect(screen.getByText('Correct only with Graph Off')).toBeInTheDocument();
    expect(screen.getByText('Both correct')).toBeInTheDocument();
    expect(screen.getByText('Both wrong')).toBeInTheDocument();

    // Tag and details
    expect(screen.getByText('Saved dev run, not validation')).toBeInTheDocument();
    expect(screen.getByText('development')).toBeInTheDocument();
  });

  it('renders "Not available" in aggregate strip when eval results are missing', () => {
    renderWithClient(<ComparePage initialSample={mockCompareResponse} />, {
      evalResults: null,
    });

    const notAvailables = screen.getAllByText('Not available');
    expect(notAvailables.length).toBeGreaterThan(0);
  });

  it('renders "Not available for a single question" in difference strip when difference_counts is null', () => {
    renderWithClient(<ComparePage initialSample={mockCompareResponse} />);

    expect(screen.getByText('Not available for a single question')).toBeInTheDocument();
    expect(screen.getByText('Question Status')).toBeInTheDocument();
  });
});
