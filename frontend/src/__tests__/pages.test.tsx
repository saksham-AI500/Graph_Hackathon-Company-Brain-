import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '../context/ThemeContext';
import { AskPage } from '../pages/AskPage';
import { ComparePage } from '../pages/ComparePage';
import { GraphPage } from '../pages/GraphPage';
import { EvaluationPage } from '../pages/EvaluationPage';
import type { AskResponse, CompareResponse, NeighborhoodResponse, EvalResultsResponse } from '../api/schema';

const SAMPLES_DIR = path.resolve(__dirname, '../../../docs/api_samples');

function loadSample<T>(fileName: string): T {
  const filePath = path.join(SAMPLES_DIR, fileName);
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>{ui}</ThemeProvider>
    </QueryClientProvider>,
  );
}

describe('Frontend Pages Rendering Tests', () => {
  it('AskPage renders refusal case without sources', () => {
    const refusalSample: AskResponse = {
      status: 'REFUSED',
      answer: 'Query cannot be answered because the requested financial metrics are outside authorized scope.',
      context: 'As of latest synchronized data',
      ranking: [],
      reasoning: 'Out of scope query refused.',
      claims: [],
      excluded: [],
      unresolved: ['Financial metrics access'],
      sources: [
        {
          id: 'S1',
          entity: 'internal/confidential.md',
          entity_type: 'Document',
          url: 'https://github.com/...',
          date: '',
          quote: '',
        },
      ],
      mode: 'graph_on',
      synced_at: '2026-10-18T10:00:00Z',
      model: 'anthropic/claude-3-5-sonnet',
      tool_calls: [],
    };

    renderWithProviders(<AskPage initialSample={refusalSample} />);

    // Must show REFUSED status
    expect(screen.getByText('REFUSED')).toBeInTheDocument();
    expect(screen.getByText(/financial metrics are outside authorized scope/i)).toBeInTheDocument();

    // Refusal variant has no sources
    expect(screen.queryByText(/Evidence Sources/i)).not.toBeInTheDocument();
  });

  it('AskPage renders excluded candidates case from contract sample', () => {
    const sampleWithExcluded: AskResponse = {
      status: 'VERIFIED',
      answer: 'Caleb Rivers is the recommended reviewer based on recent commits [S1].',
      context: 'As of 2026-10-18',
      ranking: [
        {
          rank: 1,
          login: 'caleb-rivers',
          score: 0.88,
          reasons: ['8 PRs merged in module api/gateway'],
          source_ids: ['S1'],
          tied: false,
        },
      ],
      reasoning: '',
      claims: [
        {
          id: 'C1',
          text: 'Caleb Rivers has 8 PRs merged.',
          type: 'fact',
          source_ids: ['S1'],
          verified: true,
          verification_path: 'exact_lookup',
        },
      ],
      excluded: [
        {
          login: 'jordan-hayes',
          reason: 'Departed staff member',
          end_date: '2024-08-01',
        },
      ],
      unresolved: [],
      sources: [
        {
          id: 'S1',
          entity: 'api/gateway/auth.py',
          entity_type: 'File',
          url: 'https://github.com/...',
          date: '',
          quote: '',
        },
      ],
      mode: 'graph_on',
      synced_at: '2026-10-18T10:00:00Z',
      model: 'anthropic/claude-3-5-sonnet',
      tool_calls: [],
    };

    renderWithProviders(<AskPage initialSample={sampleWithExcluded} />);

    expect(screen.getByText('VERIFIED')).toBeInTheDocument();
    expect(screen.getByText('Excluded Candidates')).toBeInTheDocument();
    expect(screen.getByText('@jordan-hayes')).toBeInTheDocument();
    expect(screen.getByText('Departed staff member')).toBeInTheDocument();
  });

  it('ComparePage renders dual columns and counters', () => {
    const compareSample = loadSample<CompareResponse>('post_api_compare.json');

    renderWithProviders(<ComparePage initialSample={compareSample} />);

    // Dual columns: Graph Off left, Graph On right
    expect(screen.getByText('Graph Off')).toBeInTheDocument();
    expect(screen.getByText('Graph On')).toBeInTheDocument();

    // Check difference and benchmark differential sections
    expect(screen.getByText(/Question Status/i)).toBeInTheDocument();
    expect(screen.getByText(/Benchmark Differential/i)).toBeInTheDocument();
  });

  it('GraphPage renders neighborhood canvas and controls', () => {
    const graphSample = loadSample<NeighborhoodResponse>('get_api_graph_neighborhood.json');

    renderWithProviders(<GraphPage initialSample={graphSample} />);

    expect(screen.getByPlaceholderText(/Query entity neighborhood/i)).toBeInTheDocument();
    expect(screen.getByText('Explore')).toBeInTheDocument();
  });

  it('EvaluationPage renders four stat cards, results table, and required note', () => {
    const evalSample = loadSample<EvalResultsResponse>('get_api_eval_results.json');

    renderWithProviders(<EvaluationPage initialSample={evalSample} />);

    // MUST show the exact required note:
    expect(screen.getByText('Dev set used during debugging. Not validation.')).toBeInTheDocument();

    // Four stat cards
    expect(screen.getByText('Graph On Accuracy')).toBeInTheDocument();
    expect(screen.getByText('Citation Support')).toBeInTheDocument();
    expect(screen.getByText('Unsupported Claims')).toBeInTheDocument();
    expect(screen.getByText('Mean Turn Latency')).toBeInTheDocument();

    // Table breakdown
    expect(screen.getByText(/Evaluation Question Breakdown/i)).toBeInTheDocument();
  });
});
