import { useState } from 'react';
import {
  Play,
  CheckCircle,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Terminal,
  FileCode,
  ShieldAlert,
} from 'lucide-react';
import { useCompare, formatErrorMessage } from '../api/client';
import type { CompareResponse } from '../api/schema';
import { StaggeredText } from '../components/StaggeredText';
import { CountUp } from '../components/CountUp';

export function ComparePage({ initialSample }: { initialSample?: CompareResponse }) {
  const [question, setQuestion] = useState('Who should review changes to auth and payments?');
  const [localResponse, setLocalResponse] = useState<CompareResponse | null>(initialSample ?? null);

  const compareMutation = useCompare();

  const handleRun = (qToRun?: string) => {
    const q = (qToRun ?? question).trim();
    if (!q) return;
    compareMutation.mutate(
      { question: q },
      {
        onSuccess: (data) => {
          setLocalResponse(data);
        },
      },
    );
  };

  const response = localResponse;

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'VERIFIED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-mono text-[11px] font-bold uppercase tracking-wider">
            <CheckCircle size={13} />
            <span>VERIFIED</span>
          </span>
        );
      case 'PARTIALLY_VERIFIED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 font-mono text-[11px] font-bold uppercase tracking-wider">
            <AlertTriangle size={13} />
            <span>PARTIALLY VERIFIED</span>
          </span>
        );
      case 'ANSWERED_UNCERTAIN':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-orange-500/15 border border-orange-500/30 text-orange-400 font-mono text-[11px] font-bold uppercase tracking-wider">
            <HelpCircle size={13} />
            <span>ANSWERED UNCERTAIN</span>
          </span>
        );
      case 'REFUSED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-500/15 border border-red-500/30 text-red-400 font-mono text-[11px] font-bold uppercase tracking-wider">
            <XCircle size={13} />
            <span>REFUSED</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-500/15 border border-zinc-500/30 text-zinc-300 font-mono text-[11px] font-bold uppercase tracking-wider">
            <span>{status}</span>
          </span>
        );
    }
  };

  const diffCounts = response?.comparison.difference_counts;

  return (
    <div className="w-full max-w-[1440px] mx-auto px-4 md:px-8 py-6 flex flex-col gap-6">
      {/* Query Bar */}
      <section className="w-full">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleRun();
          }}
          className="relative bg-surface-container rounded-xl p-3 border border-outline-variant/30 shadow-md"
        >
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="relative flex-1 flex items-center">
              <Terminal size={18} className="absolute left-3 text-outline pointer-events-none" />
              <input
                type="text"
                id="compare-input"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask question across repository index..."
                className="w-full pl-10 pr-4 py-2.5 bg-surface-container-lowest text-on-surface text-sm rounded-lg border border-outline-variant/30 focus:outline-none focus:ring-1 focus:ring-primary-container font-mono transition-all"
              />
            </div>
            <button
              type="submit"
              id="compare-run-btn"
              disabled={compareMutation.isPending || !question.trim()}
              className="flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-primary hover:bg-primary-hover text-white text-sm font-semibold shadow-sm active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50"
            >
              {compareMutation.isPending ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Evaluating...</span>
                </>
              ) : (
                <>
                  <Play size={15} fill="currentColor" />
                  <span>Run</span>
                </>
              )}
            </button>
          </div>
        </form>
      </section>

      {/* Error state */}
      {compareMutation.isError && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-start gap-3">
          <AlertTriangle size={18} className="shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">{compareMutation.error.code}</p>
            <p className="text-xs mt-1 text-red-300">
              {formatErrorMessage(compareMutation.error.code, compareMutation.error.message)}
            </p>
          </div>
        </div>
      )}

      {/* Side-by-Side Evaluation Columns */}
      {response && (
        <section className="w-full grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* LEFT COLUMN: Graph Off */}
          <article className="flex flex-col rounded-xl bg-surface-container-low p-5 md:p-6 border border-outline-variant/30 shadow-sm relative overflow-hidden">
            {/* Header strip */}
            <div className="flex items-center justify-between pb-4 border-b border-outline-variant/20">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded bg-surface-container-high text-on-surface-variant font-mono text-xs uppercase tracking-wider font-semibold">
                  Graph Off
                </span>
                <span className="text-xs text-on-surface-variant font-mono">Zero Tools / Standard LLM</span>
              </div>
              {renderStatusBadge(response.comparison.off_status)}
            </div>

            {/* Answer body */}
            <div className="py-4 text-on-surface text-sm leading-relaxed">
              <StaggeredText text={response.graph_off.answer} />
            </div>

            {/* Metrics summary */}
            <div className="pt-4 border-t border-outline-variant/20 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-on-surface-variant">
              <div>
                <span>Claims: </span>
                <span className="text-on-surface font-semibold">{response.comparison.off_claims_count}</span>
              </div>
              <div>
                <span>Sources Cited: </span>
                <span className="text-on-surface font-semibold">{response.comparison.off_sources_count}</span>
              </div>
              <div>
                <span>Model: </span>
                <span className="text-on-surface font-semibold">{response.graph_off.model}</span>
              </div>
            </div>

            {/* Fabricated citations banner if any in Graph Off */}
            {response.comparison.fabricated_citations_in_off > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/25 flex items-center gap-2.5 text-xs text-amber-300">
                <ShieldAlert size={16} className="text-amber-400 shrink-0" />
                <span>
                  {response.comparison.fabricated_citations_in_off} fabricated citation(s) detected in Graph Off response.
                </span>
              </div>
            )}
          </article>

          {/* RIGHT COLUMN: Graph On */}
          <article className="flex flex-col rounded-xl bg-surface-container-low p-5 md:p-6 border border-primary/30 shadow-md relative overflow-hidden">
            {/* Header strip */}
            <div className="flex items-center justify-between pb-4 border-b border-outline-variant/20">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded bg-primary-container text-on-primary-container font-mono text-xs uppercase tracking-wider font-bold">
                  Graph On
                </span>
                <span className="text-xs text-on-surface-variant font-mono">Knowledge Graph Grounded</span>
              </div>
              {renderStatusBadge(response.comparison.on_status)}
            </div>

            {/* Answer body */}
            <div className="py-4 text-on-surface text-sm leading-relaxed">
              <StaggeredText text={response.graph_on.answer} />
            </div>

            {/* Ranked reviewers (if any) */}
            {response.graph_on.ranking && response.graph_on.ranking.length > 0 && (
              <div className="my-2 p-3 rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col gap-2">
                <span className="text-[11px] font-mono uppercase text-on-surface-variant font-semibold">
                  Ranked Candidates
                </span>
                <div className="space-y-1.5 text-xs font-mono">
                  {response.graph_on.ranking.map((r) => (
                    <div key={r.rank} className="flex items-center justify-between">
                      <span className="text-primary font-semibold">
                        #{r.rank} @{r.login}
                      </span>
                      <span className="text-on-surface-variant">
                        {r.score <= 1 ? `${Math.round(r.score * 100)}%` : `${r.score}%`}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Sources list */}
            {response.graph_on.sources && response.graph_on.sources.length > 0 && (
              <div className="pt-3 border-t border-outline-variant/20 flex flex-col gap-2">
                <span className="text-[11px] font-mono uppercase text-on-surface-variant font-semibold">
                  Verified Sources ({response.graph_on.sources.length})
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {response.graph_on.sources.map((s) => (
                    <span
                      key={s.id}
                      className="px-2 py-0.5 rounded bg-surface-container-high border border-outline-variant/30 text-primary font-mono text-[11px] flex items-center gap-1"
                    >
                      <FileCode size={11} />
                      <span>[{s.id}] {s.entity}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Metrics summary */}
            <div className="pt-4 border-t border-outline-variant/20 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-on-surface-variant mt-auto">
              <div>
                <span>Claims: </span>
                <span className="text-primary font-semibold">{response.comparison.on_claims_count}</span>
              </div>
              <div>
                <span>Sources Cited: </span>
                <span className="text-secondary font-semibold">{response.comparison.on_sources_count}</span>
              </div>
              <div>
                <span>Model: </span>
                <span className="text-on-surface font-semibold">{response.graph_on.model}</span>
              </div>
            </div>
          </article>
        </section>
      )}

      {/* Bottom Strip with Counters */}
      {response && (
        <section className="w-full pt-2">
          <div className="mb-3">
            <span className="font-mono text-xs uppercase tracking-wider text-on-surface-variant font-semibold">
              Comparative Analysis Counters
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* 1. Claims Difference */}
            <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/20 shadow-xs flex flex-col justify-between">
              <span className="text-xs text-on-surface-variant font-medium">Claims Difference (On - Off)</span>
              <div className="mt-3">
                {diffCounts?.claims_diff !== null && diffCounts?.claims_diff !== undefined ? (
                  <span className="font-mono text-2xl font-bold text-primary">
                    <CountUp value={diffCounts.claims_diff} prefix={diffCounts.claims_diff > 0 ? '+' : ''} />
                  </span>
                ) : (
                  <span className="font-mono text-sm text-on-surface-variant italic">not available</span>
                )}
              </div>
            </div>

            {/* 2. Sources Difference */}
            <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/20 shadow-xs flex flex-col justify-between">
              <span className="text-xs text-on-surface-variant font-medium">Sources Difference (On - Off)</span>
              <div className="mt-3">
                {diffCounts?.sources_diff !== null && diffCounts?.sources_diff !== undefined ? (
                  <span className="font-mono text-2xl font-bold text-secondary">
                    <CountUp value={diffCounts.sources_diff} prefix={diffCounts.sources_diff > 0 ? '+' : ''} />
                  </span>
                ) : (
                  <span className="font-mono text-sm text-on-surface-variant italic">not available</span>
                )}
              </div>
            </div>

            {/* 3. Facts Passed Difference */}
            <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/20 shadow-xs flex flex-col justify-between">
              <span className="text-xs text-on-surface-variant font-medium">Verified Facts Delta</span>
              <div className="mt-3">
                {diffCounts?.facts_passed_diff !== null && diffCounts?.facts_passed_diff !== undefined ? (
                  <span className="font-mono text-2xl font-bold text-emerald-400">
                    <CountUp value={diffCounts.facts_passed_diff} prefix={diffCounts.facts_passed_diff > 0 ? '+' : ''} />
                  </span>
                ) : (
                  <span className="font-mono text-sm text-on-surface-variant italic">not available</span>
                )}
              </div>
            </div>

            {/* 4. Violations Delta */}
            <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/20 shadow-xs flex flex-col justify-between">
              <span className="text-xs text-on-surface-variant font-medium">Rubric Violations Delta</span>
              <div className="mt-3">
                {diffCounts?.violations_diff !== null && diffCounts?.violations_diff !== undefined ? (
                  <span className="font-mono text-2xl font-bold text-amber-400">
                    <CountUp value={diffCounts.violations_diff} prefix={diffCounts.violations_diff > 0 ? '+' : ''} />
                  </span>
                ) : (
                  <span className="font-mono text-sm text-on-surface-variant italic">not available</span>
                )}
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
