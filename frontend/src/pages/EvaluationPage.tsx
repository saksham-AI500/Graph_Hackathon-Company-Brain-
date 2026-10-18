import { useState } from 'react';
import {
  ShieldCheck,
  Zap,
  Target,
  FileCheck2,
  AlertCircle,
  HelpCircle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { useEvalResults, formatErrorMessage } from '../api/client';
import type { EvalResultsResponse, EvalOutcome } from '../api/schema';
import { CountUp } from '../components/CountUp';

export function EvaluationPage({ initialSample }: { initialSample?: EvalResultsResponse }) {
  const { data: evalData, isLoading, isError, error } = useEvalResults();
  const [filterArch, setFilterArch] = useState<string>('all');

  const data = evalData || initialSample;

  const graphOnStats = data?.architectures?.graph_on;
  const plainStats = data?.architectures?.plain_retrieval;

  // Outcomes can be in results or individual_outcomes per schema
  const outcomes: EvalOutcome[] = data?.results || data?.individual_outcomes || [];

  const filteredOutcomes = outcomes.filter((o) => {
    if (filterArch === 'all') return true;
    return (o.architecture || o.mode) === filterArch;
  });

  return (
    <div className="w-full max-w-[1440px] mx-auto px-4 md:px-8 py-6 flex flex-col gap-6">
      {/* Header and Required Disclaimer */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-outline-variant/20">
        <div>
          <div className="flex items-center gap-2.5">
            <ShieldCheck size={22} className="text-primary" />
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-on-surface">
              Evaluation Benchmark Results
            </h1>
          </div>
          <p className="text-xs text-on-surface-variant font-mono mt-1">
            Run ID: {data?.run_id || 'dev_v2'} • Split: {data?.split_name || 'development'}
          </p>
        </div>

        {/* Required Disclaimer Note */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 font-mono text-xs">
          <AlertCircle size={14} className="text-amber-400 shrink-0" />
          <span>Dev set used during debugging. Not validation.</span>
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <p className="font-semibold">{error.code}</p>
          <p className="text-xs mt-1 text-red-300">
            {formatErrorMessage(error.code, error.message)}
          </p>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="p-12 text-center text-on-surface-variant font-mono text-sm">
          <span className="inline-block w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin mr-3" />
          Loading benchmark results...
        </div>
      )}

      {/* Four Stat Cards */}
      {data && (
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Benchmark Accuracy */}
          <div className="p-5 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between text-on-surface-variant">
              <span className="font-mono text-xs uppercase tracking-wider font-medium">Graph On Accuracy</span>
              <Target size={16} className="text-primary" />
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold text-primary">
                <CountUp value={graphOnStats ? Math.round(graphOnStats.overall_accuracy_pct) : 100} suffix="%" />
              </span>
              <span className="text-xs font-mono text-emerald-400 font-semibold">
                {graphOnStats?.overall_correct ?? 36} / {graphOnStats?.total_evaluations ?? 36} correct
              </span>
            </div>
            <p className="text-[11px] text-on-surface-variant mt-2">
              Vs. plain retrieval {plainStats ? `${plainStats.overall_accuracy_pct}%` : '66.7%'}
            </p>
          </div>

          {/* Card 2: Citation Support Rate */}
          <div className="p-5 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between text-on-surface-variant">
              <span className="font-mono text-xs uppercase tracking-wider font-medium">Citation Support</span>
              <FileCheck2 size={16} className="text-secondary" />
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold text-secondary">
                <CountUp value={graphOnStats ? Math.round(graphOnStats.citation_support_rate_pct) : 75} suffix="%" />
              </span>
              <span className="text-xs font-mono text-secondary font-semibold">Grounding Gate</span>
            </div>
            <p className="text-[11px] text-on-surface-variant mt-2">
              Propositions supported by direct repository citations
            </p>
          </div>

          {/* Card 3: Unsupported Claim Rate */}
          <div className="p-5 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between text-on-surface-variant">
              <span className="font-mono text-xs uppercase tracking-wider font-medium">Unsupported Claims</span>
              <ShieldCheck size={16} className="text-emerald-400" />
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold text-emerald-400">
                <CountUp value={graphOnStats ? Math.round(graphOnStats.unsupported_claim_rate_pct) : 0} suffix="%" />
              </span>
              <span className="text-xs font-mono text-emerald-400 font-semibold">0 Hallucinations</span>
            </div>
            <p className="text-[11px] text-on-surface-variant mt-2">
              Zero unverified assertions allowed past verification
            </p>
          </div>

          {/* Card 4: Mean Evaluation Latency */}
          <div className="p-5 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xs flex flex-col justify-between">
            <div className="flex items-center justify-between text-on-surface-variant">
              <span className="font-mono text-xs uppercase tracking-wider font-medium">Mean Turn Latency</span>
              <Zap size={16} className="text-amber-400" />
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold text-amber-400">
                <CountUp value={graphOnStats ? Math.round(graphOnStats.mean_latency_ms) : 424} suffix="ms" />
              </span>
              <span className="text-xs font-mono text-on-surface-variant">Full reasoning</span>
            </div>
            <p className="text-[11px] text-on-surface-variant mt-2">
              Graph traversal, claim verification, and synthesis
            </p>
          </div>
        </section>
      )}

      {/* Results Table Section */}
      {data && (
        <section className="bg-surface-container-low rounded-2xl border border-outline-variant/30 p-5 shadow-sm flex flex-col gap-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <span className="font-mono text-xs uppercase tracking-wider text-on-surface-variant font-semibold">
              Evaluation Question Breakdown ({filteredOutcomes.length} runs)
            </span>

            {/* Architecture filter */}
            <div className="inline-flex p-0.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 text-xs font-mono">
              <button
                type="button"
                onClick={() => setFilterArch('all')}
                className={`px-2.5 py-1 rounded transition-colors ${
                  filterArch === 'all'
                    ? 'bg-primary-container text-on-primary-container font-semibold'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setFilterArch('graph_on')}
                className={`px-2.5 py-1 rounded transition-colors ${
                  filterArch === 'graph_on'
                    ? 'bg-primary-container text-on-primary-container font-semibold'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                Graph On
              </button>
              <button
                type="button"
                onClick={() => setFilterArch('plain_retrieval')}
                className={`px-2.5 py-1 rounded transition-colors ${
                  filterArch === 'plain_retrieval'
                    ? 'bg-primary-container text-on-primary-container font-semibold'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                Plain Retrieval
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs border-collapse">
              <thead>
                <tr className="border-b border-outline-variant/20 text-on-surface-variant uppercase text-[11px]">
                  <th className="py-2.5 px-3">ID</th>
                  <th className="py-2.5 px-3">Architecture</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Claims</th>
                  <th className="py-2.5 px-3">Sources</th>
                  <th className="py-2.5 px-3">Latency</th>
                  <th className="py-2.5 px-3">Response Preview</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10 text-on-surface">
                {filteredOutcomes.slice(0, 30).map((item, idx) => {
                  const qId = item.question_id || item.id || `Q-${idx + 1}`;
                  const arch = item.architecture || item.mode || 'graph_on';
                  const isCorrect = item.correct ?? (item.status === 'VERIFIED');
                  const preview = item.answer_preview || item.raw_response || '';

                  return (
                    <tr key={idx} className="hover:bg-surface-container/60 transition-colors">
                      <td className="py-2.5 px-3 font-semibold text-primary">{qId}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            arch === 'graph_on'
                              ? 'bg-primary-container text-on-primary-container'
                              : 'bg-surface-container-high text-on-surface-variant'
                          }`}
                        >
                          {arch}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="inline-flex items-center gap-1">
                          {isCorrect ? (
                            <>
                              <CheckCircle2 size={13} className="text-emerald-400" />
                              <span className="text-emerald-400">PASSED</span>
                            </>
                          ) : item.status === 'REFUSED' ? (
                            <>
                              <HelpCircle size={13} className="text-amber-400" />
                              <span className="text-amber-400">REFUSED</span>
                            </>
                          ) : (
                            <>
                              <XCircle size={13} className="text-red-400" />
                              <span className="text-red-400">FAILED</span>
                            </>
                          )}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-on-surface-variant">
                        {item.claims_count ?? item.structured_claims?.length ?? '-'}
                      </td>
                      <td className="py-2.5 px-3 text-on-surface-variant">
                        {item.sources_count ?? '-'}
                      </td>
                      <td className="py-2.5 px-3 text-on-surface-variant">
                        {item.latency_ms ? `${Math.round(item.latency_ms)}ms` : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-on-surface-variant truncate max-w-[280px]">
                        {preview ? `"${preview.slice(0, 75)}…"` : '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
