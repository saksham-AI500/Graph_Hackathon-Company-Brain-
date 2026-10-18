import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence, MotionConfig } from 'motion/react';
import {
  Terminal,
  Play,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  FileCode,
  X,
  ExternalLink,
  RefreshCw,
  TrendingUp,
  Minus,
  CheckCheck,
  AlertCircle,
} from 'lucide-react';
import { useCompare, useStats, useHealth, useEvalResults, formatErrorMessage } from '../api/client';
import type { CompareResponse, Source, EvalOutcome } from '../api/schema';
import { CountUp } from '../components/CountUp';

export function ComparePage({ initialSample }: { initialSample?: CompareResponse }) {
  const [question, setQuestion] = useState('Who should review changes to auth and payments?');
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [localResponse, setLocalResponse] = useState<CompareResponse | null>(initialSample ?? null);
  const [showFailureModal, setShowFailureModal] = useState(false);

  const { data: stats } = useStats();
  const { data: health, isError: isHealthError } = useHealth();
  const { data: evalResults, isError: isEvalError } = useEvalResults();
  const compareMutation = useCompare();

  // Handle Escape key to close drawer and modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setActiveSource(null);
        setShowFailureModal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleRun = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const q = question.trim();
    if (!q || compareMutation.isPending) return;

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
  const isOffline = isHealthError || (health && health.status !== 'healthy');

  // Format relative time helper
  const formatTime = (isoString?: string | null) => {
    if (!isoString) return null;
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return null;
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return null;
    }
  };

  // Status Badge Helper
  const renderStatusBadge = (status: string) => {
    const s = (status || '').toUpperCase();
    if (s === 'VERIFIED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-secondary font-label-code text-label-code tracking-wide uppercase font-semibold">
          <CheckCircle2 size={13} className="text-secondary" />
          <span>VERIFIED</span>
        </span>
      );
    }
    if (s === 'REFUSED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-tertiary-fixed-dim font-label-code text-label-code tracking-wide uppercase font-semibold">
          <ShieldAlert size={13} className="text-tertiary-fixed-dim" />
          <span>REFUSED</span>
        </span>
      );
    }
    if (s === 'ANSWERED_UNCERTAIN' || s === 'PARTIALLY_VERIFIED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-tertiary-fixed-dim font-label-code text-label-code tracking-wide uppercase font-semibold">
          <AlertTriangle size={13} className="text-tertiary-fixed-dim" />
          <span>{s}</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-high border border-outline-variant/30 text-on-surface-variant font-label-code text-label-code tracking-wide uppercase font-semibold">
        <span>{s || 'UNKNOWN'}</span>
      </span>
    );
  };

  // Parse Answer text to replace [S#] with clickable buttons for Graph On
  const renderAnswerText = (text: string, sources: Source[]) => {
    if (!text) return null;
    const parts = text.split(/(\[S\d+\])/g);
    return parts.map((part, idx) => {
      const match = part.match(/^\[S(\d+)\]$/);
      if (match) {
        const id = `S${match[1]}`;
        const source = sources.find((s) => s.id === id);
        return (
          <button
            key={idx}
            type="button"
            onClick={() => source && setActiveSource(source)}
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-surface-container-high text-primary hover:bg-surface-bright font-label-code text-label-code align-baseline transition-colors cursor-pointer border border-outline-variant/30"
            title={source ? (source.title || source.entity) : id}
          >
            {part}
          </button>
        );
      }
      return <span key={idx}>{part}</span>;
    });
  };

  // Compute 4 Aggregate Counters from /api/eval/results
  const aggregateMetrics = useMemo(() => {
    if (!evalResults) return null;
    const outcomes: EvalOutcome[] = evalResults.individual_outcomes || evalResults.results || [];
    if (outcomes.length === 0) return null;

    const pairs = new Map<string, { on_correct?: boolean; off_correct?: boolean }>();
    const timestamps: string[] = [];
    const fabricatedFailures: Array<{ qid: string; quote: string }> = [];

    outcomes.forEach((o) => {
      if (o.timestamp) timestamps.push(o.timestamp);
      const qid = o.question_id || o.id || 'unknown';
      const rep = o.repetition ?? 1;
      const key = `${qid}-rep${rep}`;
      const existing = pairs.get(key) || {};

      const isCorrect = Boolean(
        o.correct === true ||
        (o.score && typeof o.score === 'object' && (o.score as Record<string, unknown>).correct === true)
      );

      const arch = o.architecture || o.mode;
      if (arch === 'graph_on') {
        existing.on_correct = isCorrect;
      } else if (arch === 'graph_off') {
        existing.off_correct = isCorrect;
        // Check for fabricated citations
        const citations = o.citations || [];
        const scoreObj = o.score && typeof o.score === 'object' ? (o.score as Record<string, unknown>) : null;
        const unsupportedCount = Number(scoreObj?.unsupported_claim_count || 0);
        if (citations.length > 0 && unsupportedCount > 0) {
          fabricatedFailures.push({
            qid,
            quote: citations.join(', '),
          });
        }
      }
      pairs.set(key, existing);
    });

    let onOnly = 0;
    let offOnly = 0;
    let bothCorrect = 0;
    let bothWrong = 0;

    pairs.forEach((pair) => {
      const on = Boolean(pair.on_correct);
      const off = Boolean(pair.off_correct);
      if (on && !off) onOnly++;
      else if (!on && off) offOnly++;
      else if (on && off) bothCorrect++;
      else bothWrong++;
    });

    const minDate = timestamps.length > 0 ? formatTime(timestamps.sort()[0]) : null;
    const maxDate = timestamps.length > 0 ? formatTime(timestamps.sort()[timestamps.length - 1]) : null;
    const dateRange = minDate && maxDate ? (minDate === maxDate ? minDate : `${minDate} - ${maxDate}`) : null;

    return {
      completedCount: outcomes.length,
      pairsCount: pairs.size,
      splitName: evalResults.split_name || 'development',
      dateRange,
      onOnly,
      offOnly,
      bothCorrect,
      bothWrong,
      fabricatedFailures,
    };
  }, [evalResults]);

  // Index label derived strictly from stats.last_synced_at
  const indexLabel = stats?.last_synced_at
    ? `Index: ${formatTime(stats.last_synced_at)}`
    : 'Index: Not available';

  return (
    <MotionConfig reducedMotion="user">
      <div className="w-full flex-1 bg-surface max-w-[1440px] mx-auto px-margin-desktop min-h-screen text-on-surface">
        <div className="flex flex-col w-full pb-space-xl">
          {/* Query Bar Section */}
          <section className="w-full pt-space-lg pb-space-xl">
            <div className="relative bg-surface-container rounded-xl p-space-md shadow-md border border-outline-variant/20">
              <form onSubmit={handleRun} className="flex flex-col md:flex-row items-stretch md:items-center gap-space-md">
                {/* Input Group */}
                <div className="relative flex-1 flex items-center">
                  <Terminal size={18} className="absolute left-3 text-outline pointer-events-none" />
                  <input
                    id="query-input"
                    type="text"
                    value={question}
                    disabled={isOffline || compareMutation.isPending}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Ask question across repository index..."
                    className="w-full pl-10 pr-4 py-2.5 bg-surface-container-lowest text-on-surface font-code-md text-code-md rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-container transition-all border border-outline-variant/30 disabled:opacity-50"
                  />
                </div>

                {/* Index label & Run trigger */}
                <div className="flex items-center gap-space-sm justify-between md:justify-end">
                  <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container-low text-on-surface-variant font-label-code text-label-code border border-outline-variant/20">
                    <span className="material-symbols-outlined text-[16px] text-primary">account_tree</span>
                    <span>{indexLabel}</span>
                  </div>
                  <button
                    id="run-compare-btn"
                    type="submit"
                    disabled={isOffline || compareMutation.isPending || !question.trim()}
                    className="flex items-center gap-space-xs px-space-lg py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container font-title-md text-title-md font-medium shadow-sm active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50"
                  >
                    {compareMutation.isPending ? (
                      <>
                        <RefreshCw size={16} className="animate-spin" />
                        <span>Evaluating...</span>
                      </>
                    ) : (
                      <>
                        <Play size={16} fill="currentColor" />
                        <span>Run</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </section>

          {/* Backend Offline Banner */}
          {isOffline && (
            <div className="mb-space-lg p-space-lg rounded-xl bg-red-500/10 border border-red-500/30 text-error flex items-start gap-3 shadow-sm">
              <AlertCircle size={20} className="shrink-0 mt-0.5 text-error" />
              <div>
                <p className="font-semibold text-sm">Backend Offline</p>
                <p className="text-xs text-on-surface-variant mt-1">
                  The backend service is currently unreachable. Start the backend server to run evaluations.
                </p>
              </div>
            </div>
          )}

          {/* Error Banner with Retry */}
          {compareMutation.isError && (
            <div className="mb-space-lg p-space-md rounded-xl bg-amber-500/10 border border-amber-500/30 text-tertiary-fixed-dim flex items-center justify-between gap-space-md shadow-sm">
              <div className="flex items-center gap-space-sm">
                <AlertTriangle size={18} className="shrink-0 text-tertiary-fixed-dim" />
                <span className="text-sm">
                  {formatErrorMessage(compareMutation.error.code, compareMutation.error.message)}
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleRun()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-bright text-on-surface text-xs font-medium border border-outline-variant/40 transition-colors cursor-pointer"
              >
                <RefreshCw size={13} />
                <span>Retry</span>
              </button>
            </div>
          )}

          {/* Loading Skeleton */}
          {compareMutation.isPending && (
            <div className="w-full grid grid-cols-1 lg:grid-cols-2 gap-space-xl items-start mb-space-xl">
              <div className="h-64 rounded-xl bg-surface-container p-space-lg animate-pulse border border-outline-variant/20 flex flex-col gap-4">
                <div className="h-6 bg-surface-container-high rounded w-1/3"></div>
                <div className="h-4 bg-surface-container-high rounded w-full"></div>
                <div className="h-4 bg-surface-container-high rounded w-4/5"></div>
                <div className="h-10 bg-surface-container-lowest rounded mt-auto"></div>
              </div>
              <div className="h-64 rounded-xl bg-surface-container p-space-lg animate-pulse border border-outline-variant/20 flex flex-col gap-4">
                <div className="h-6 bg-surface-container-high rounded w-1/3"></div>
                <div className="h-4 bg-surface-container-high rounded w-full"></div>
                <div className="h-4 bg-surface-container-high rounded w-4/5"></div>
                <div className="h-10 bg-surface-container-lowest rounded mt-auto"></div>
              </div>
            </div>
          )}

          {/* Side-by-Side Comparison Columns */}
          {response && !compareMutation.isPending && (
            <motion.section
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
              className="w-full grid grid-cols-1 lg:grid-cols-2 gap-space-xl items-start mb-space-xl"
            >
              {/* LEFT COLUMN: Graph Off */}
              <article className="flex flex-col rounded-xl bg-surface-container p-space-lg shadow-sm border border-outline-variant/20 relative overflow-hidden h-full">
                {/* Header strip */}
                <div className="flex items-center justify-between pb-space-md border-b border-outline-variant/10">
                  <div className="flex items-center gap-space-sm">
                    <span className="px-2.5 py-1 rounded bg-surface-container-high text-on-surface-variant font-label-code text-label-code uppercase tracking-wider font-semibold">
                      Graph Off
                    </span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Model only, no tools</span>
                  </div>
                  {renderStatusBadge(response.graph_off.status)}
                </div>

                {/* Synthesized Text Response */}
                <div className="mt-space-sm p-space-md rounded-lg bg-surface-container-lowest text-on-surface font-body-md text-body-md leading-relaxed min-h-[80px]">
                  {response.graph_off.answer}
                </div>

                {/* Counters Row */}
                <div className="grid grid-cols-2 gap-space-md py-space-md my-space-xs">
                  <div className="flex flex-col p-space-sm rounded-lg bg-surface-container-low border border-outline-variant/10">
                    <span className="font-label-code text-label-code text-on-surface-variant uppercase tracking-wider">
                      Claims
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="font-headline-sm text-headline-sm text-on-surface font-semibold">
                        <CountUp value={response.graph_off.claims ? response.graph_off.claims.length : 0} />
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col p-space-sm rounded-lg bg-surface-container-low border border-outline-variant/10">
                    <span className="font-label-code text-label-code text-on-surface-variant uppercase tracking-wider">
                      Sources
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="font-headline-sm text-headline-sm text-tertiary-container font-semibold">
                        <CountUp value={response.graph_off.sources ? response.graph_off.sources.length : 0} />
                      </span>
                    </div>
                  </div>
                </div>

                {/* Fabricated Citations in Graph Off */}
                <div className="mt-auto p-space-md rounded-lg bg-surface-container-low border border-outline-variant/15 flex items-start gap-space-sm">
                  <ShieldAlert size={18} className="text-tertiary-fixed-dim mt-0.5 shrink-0" />
                  <div className="flex flex-col">
                    <span className="font-label-code text-label-code text-on-surface-variant uppercase tracking-wider">
                      Fabricated citations
                    </span>
                    <span className="font-code-md text-code-md font-semibold text-tertiary-fixed-dim mt-0.5">
                      {response.comparison.fabricated_citations_in_off}
                    </span>
                  </div>
                </div>
              </article>

              {/* RIGHT COLUMN: Graph On */}
              <article className="flex flex-col rounded-xl bg-surface-container p-space-lg shadow-md border border-outline-variant/20 relative overflow-hidden h-full">
                {/* Top edge glow highlight */}
                <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-primary to-transparent opacity-80"></div>

                {/* Header strip */}
                <div className="flex items-center justify-between pb-space-md border-b border-outline-variant/10">
                  <div className="flex items-center gap-space-sm">
                    <span className="px-2.5 py-1 rounded bg-primary-container/20 text-primary-container font-label-code text-label-code uppercase tracking-wider font-semibold">
                      Graph On
                    </span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Graph tools and verifier</span>
                  </div>
                  {renderStatusBadge(response.graph_on.status)}
                </div>

                {/* Synthesized Text Response with Citation Chips */}
                <div className="mt-space-sm p-space-md rounded-lg bg-surface-container-lowest text-on-surface font-body-md text-body-md leading-relaxed min-h-[80px]">
                  {renderAnswerText(response.graph_on.answer, response.graph_on.sources || [])}
                </div>

                {/* Counters Row */}
                <div className="grid grid-cols-2 gap-space-md py-space-md my-space-xs">
                  <div className="flex flex-col p-space-sm rounded-lg bg-surface-container-low border border-outline-variant/10">
                    <span className="font-label-code text-label-code text-on-surface-variant uppercase tracking-wider">
                      Claims
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="font-headline-sm text-headline-sm text-on-surface font-semibold">
                        <CountUp value={response.graph_on.claims ? response.graph_on.claims.length : 0} />
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col p-space-sm rounded-lg bg-surface-container-low border border-outline-variant/10">
                    <span className="font-label-code text-label-code text-on-surface-variant uppercase tracking-wider">
                      Sources
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="font-headline-sm text-headline-sm text-secondary font-semibold">
                        <CountUp value={response.graph_on.sources ? response.graph_on.sources.length : 0} />
                      </span>
                    </div>
                  </div>
                </div>

                {/* Verified Sources list linked to drawer */}
                <div className="mt-auto p-space-md rounded-lg bg-surface-container-low border border-outline-variant/15 flex flex-col gap-space-xs">
                  <span className="font-label-code text-label-code text-on-surface-variant uppercase tracking-wider">
                    Source Entities
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {response.graph_on.sources && response.graph_on.sources.length > 0 ? (
                      response.graph_on.sources.map((s) => (
                        <button
                          key={s.id}
                          type="button"
                          onClick={() => setActiveSource(s)}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container-high hover:bg-surface-bright text-on-surface font-code-md text-code-md hover:text-primary transition-colors cursor-pointer border border-outline-variant/20"
                        >
                          <FileCode size={11} className="text-primary" />
                          <span className="text-primary font-semibold">[{s.id}]</span>
                          <span className="truncate max-w-[150px]">{s.entity}</span>
                        </button>
                      ))
                    ) : (
                      <span className="text-on-surface-variant font-body-sm text-xs italic">No sources returned</span>
                    )}
                  </div>
                </div>
              </article>
            </motion.section>
          )}

          {/* Difference Strip: Single Question */}
          {response && (
            <section className="w-full mb-space-xl p-space-md rounded-xl bg-surface-container border border-outline-variant/20 shadow-xs">
              <div className="flex flex-wrap items-center justify-between gap-space-md">
                <div className="flex items-center gap-space-md">
                  <span className="font-label-code text-label-code uppercase tracking-wider text-on-surface-variant font-semibold">
                    Question Status
                  </span>
                  <div className="flex items-center gap-space-sm font-label-code text-label-code">
                    <span className="text-on-surface-variant">Graph On:</span>
                    <span className="font-semibold text-secondary">{response.comparison.on_status}</span>
                    <span className="text-outline-variant">•</span>
                    <span className="text-on-surface-variant">Graph Off:</span>
                    <span className="font-semibold text-tertiary-fixed-dim">{response.comparison.off_status}</span>
                  </div>
                </div>
                <div className="font-body-sm text-body-sm text-on-surface-variant italic">
                  Not available for a single question
                </div>
              </div>
            </section>
          )}

          {/* Section Header for Aggregate Differences */}
          <div className="flex items-center justify-between pb-space-sm mb-space-sm">
            <div className="flex items-center gap-space-sm">
              <span className="font-headline-sm text-headline-sm font-semibold text-on-surface">
                Benchmark Differential
              </span>
              <span className="px-2 py-0.5 rounded bg-surface-container-high font-label-code text-label-code text-primary font-medium border border-outline-variant/30">
                Saved dev run, not validation
              </span>
            </div>
            {aggregateMetrics ? (
              <div className="flex items-center gap-space-sm font-label-code text-label-code text-on-surface-variant">
                <span>Split: <strong className="text-on-surface">{aggregateMetrics.splitName}</strong></span>
                <span className="opacity-40">•</span>
                <span>Evaluations: <strong className="text-on-surface">{aggregateMetrics.completedCount}</strong></span>
                {aggregateMetrics.dateRange && (
                  <>
                    <span className="opacity-40">•</span>
                    <span>Date: <strong className="text-on-surface">{aggregateMetrics.dateRange}</strong></span>
                  </>
                )}
              </div>
            ) : (
              <span className="font-label-code text-label-code text-on-surface-variant italic">
                {isEvalError ? 'Not available' : 'Loading benchmark run...'}
              </span>
            )}
          </div>

          {/* Aggregate Strip: Four Prominent Counter Cards */}
          <section className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-md mb-space-lg">
            {/* 1. Correct only with Graph On */}
            <div className="flex flex-col justify-between p-space-lg rounded-xl bg-surface-container shadow-sm border border-outline-variant/20 transition-all hover:bg-surface-container-high">
              <div className="flex items-center justify-between">
                <span className="font-body-sm text-body-sm text-on-surface-variant font-medium">
                  Correct only with Graph On
                </span>
                <div className="w-7 h-7 rounded-full bg-secondary/10 flex items-center justify-center text-secondary">
                  <TrendingUp size={16} />
                </div>
              </div>
              <div className="mt-space-lg flex items-baseline gap-2">
                {aggregateMetrics ? (
                  <span className="font-display-lg text-display-lg text-secondary font-semibold tracking-tight">
                    <CountUp value={aggregateMetrics.onOnly} />
                  </span>
                ) : (
                  <span className="font-body-sm text-body-sm text-on-surface-variant italic">Not available</span>
                )}
              </div>
              <div className="w-full bg-surface-container-lowest h-1.5 rounded-full mt-space-sm overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{
                    width: aggregateMetrics && aggregateMetrics.pairsCount > 0
                      ? `${(aggregateMetrics.onOnly / aggregateMetrics.pairsCount) * 100}%`
                      : '0%',
                  }}
                  transition={{ duration: 0.5 }}
                  className="bg-secondary h-full rounded-full"
                />
              </div>
            </div>

            {/* 2. Correct only with Graph Off */}
            <div className="flex flex-col justify-between p-space-lg rounded-xl bg-surface-container shadow-sm border border-outline-variant/20 transition-all hover:bg-surface-container-high">
              <div className="flex items-center justify-between">
                <span className="font-body-sm text-body-sm text-on-surface-variant font-medium">
                  Correct only with Graph Off
                </span>
                <div className="w-7 h-7 rounded-full bg-surface-container-high flex items-center justify-center text-outline">
                  <Minus size={16} />
                </div>
              </div>
              <div className="mt-space-lg flex items-baseline gap-2">
                {aggregateMetrics ? (
                  <span className="font-display-lg text-display-lg text-on-surface-variant font-semibold tracking-tight">
                    <CountUp value={aggregateMetrics.offOnly} />
                  </span>
                ) : (
                  <span className="font-body-sm text-body-sm text-on-surface-variant italic">Not available</span>
                )}
              </div>
              <div className="w-full bg-surface-container-lowest h-1.5 rounded-full mt-space-sm overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{
                    width: aggregateMetrics && aggregateMetrics.pairsCount > 0
                      ? `${(aggregateMetrics.offOnly / aggregateMetrics.pairsCount) * 100}%`
                      : '0%',
                  }}
                  transition={{ duration: 0.5 }}
                  className="bg-outline h-full rounded-full"
                />
              </div>
            </div>

            {/* 3. Both correct */}
            <div className="flex flex-col justify-between p-space-lg rounded-xl bg-surface-container shadow-sm border border-outline-variant/20 transition-all hover:bg-surface-container-high">
              <div className="flex items-center justify-between">
                <span className="font-body-sm text-body-sm text-on-surface-variant font-medium">
                  Both correct
                </span>
                <div className="w-7 h-7 rounded-full bg-primary-container/10 flex items-center justify-center text-primary-container">
                  <CheckCheck size={16} />
                </div>
              </div>
              <div className="mt-space-lg flex items-baseline gap-2">
                {aggregateMetrics ? (
                  <span className="font-display-lg text-display-lg text-primary-container font-semibold tracking-tight">
                    <CountUp value={aggregateMetrics.bothCorrect} />
                  </span>
                ) : (
                  <span className="font-body-sm text-body-sm text-on-surface-variant italic">Not available</span>
                )}
              </div>
              <div className="w-full bg-surface-container-lowest h-1.5 rounded-full mt-space-sm overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{
                    width: aggregateMetrics && aggregateMetrics.pairsCount > 0
                      ? `${(aggregateMetrics.bothCorrect / aggregateMetrics.pairsCount) * 100}%`
                      : '0%',
                  }}
                  transition={{ duration: 0.5 }}
                  className="bg-primary-container h-full rounded-full"
                />
              </div>
            </div>

            {/* 4. Both wrong */}
            <div className="flex flex-col justify-between p-space-lg rounded-xl bg-surface-container shadow-sm border border-outline-variant/20 transition-all hover:bg-surface-container-high">
              <div className="flex items-center justify-between">
                <span className="font-body-sm text-body-sm text-on-surface-variant font-medium">
                  Both wrong
                </span>
                <div className="w-7 h-7 rounded-full bg-red-500/10 flex items-center justify-center text-error">
                  <X size={16} />
                </div>
              </div>
              <div className="mt-space-lg flex items-baseline gap-2">
                {aggregateMetrics ? (
                  <span className="font-display-lg text-display-lg text-error font-semibold tracking-tight">
                    <CountUp value={aggregateMetrics.bothWrong} />
                  </span>
                ) : (
                  <span className="font-body-sm text-body-sm text-on-surface-variant italic">Not available</span>
                )}
              </div>
              <div className="w-full bg-surface-container-lowest h-1.5 rounded-full mt-space-sm overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{
                    width: aggregateMetrics && aggregateMetrics.pairsCount > 0
                      ? `${(aggregateMetrics.bothWrong / aggregateMetrics.pairsCount) * 100}%`
                      : '0%',
                  }}
                  transition={{ duration: 0.5 }}
                  className="bg-error h-full rounded-full"
                />
              </div>
            </div>
          </section>

          {/* Aggregate Counters Summary & Difference Note */}
          {aggregateMetrics && (
            <div className="w-full mb-space-lg p-3.5 rounded-xl bg-surface-container-low border border-outline-variant/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs font-mono">
              <div className="flex items-center gap-4 text-on-surface">
                <span>
                  <strong className="text-secondary">Counters Total:</strong> {aggregateMetrics.onOnly + aggregateMetrics.offOnly + aggregateMetrics.bothCorrect + aggregateMetrics.bothWrong} paired questions
                </span>
                <span className="text-outline-variant">•</span>
                <span>
                  <strong className="text-primary">Evaluation Count:</strong> {aggregateMetrics.completedCount} total runs
                </span>
              </div>
              {aggregateMetrics.completedCount !== (aggregateMetrics.onOnly + aggregateMetrics.offOnly + aggregateMetrics.bothCorrect + aggregateMetrics.bothWrong) && (
                <div className="px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/25 text-amber-300 text-[11px] leading-tight">
                  Difference: {aggregateMetrics.completedCount - (aggregateMetrics.onOnly + aggregateMetrics.offOnly + aggregateMetrics.bothCorrect + aggregateMetrics.bothWrong)} evaluations (includes 36 plain_retrieval runs in file)
                </div>
              )}
            </div>
          )}

          {/* Fabricated Citations Banner */}
          <section className="w-full mb-space-lg">
            <div className="p-space-lg rounded-xl bg-surface-container flex flex-col md:flex-row items-start md:items-center justify-between gap-space-lg shadow-sm border border-outline-variant/20">
              <div className="flex items-center gap-space-md">
                <div className="w-12 h-12 rounded-xl bg-amber-500/15 flex items-center justify-center shrink-0 text-tertiary-fixed-dim border border-amber-500/30">
                  <ShieldAlert size={28} />
                </div>
                <div className="flex flex-col">
                  <div className="flex items-center gap-space-sm">
                    <span className="font-title-md text-title-md font-semibold text-on-surface">
                      Fabricated Citations for Graph Off
                    </span>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
                    {aggregateMetrics
                      ? `Evaluated across ${aggregateMetrics.completedCount} benchmark runs.`
                      : 'Evaluation run data.'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-space-lg shrink-0 self-end md:self-center">
                <div className="flex flex-col items-end">
                  <span className="font-display-lg text-display-lg font-bold text-tertiary-container tracking-tight">
                    {aggregateMetrics ? aggregateMetrics.fabricatedFailures.length : '—'}
                  </span>
                  <span className="font-label-code text-label-code text-on-surface-variant uppercase">
                    Incidents detected
                  </span>
                </div>
                {/* Only show Inspect Failures button if failures exist in eval results */}
                {aggregateMetrics && aggregateMetrics.fabricatedFailures.length > 0 && (
                  <button
                    id="inspect-hallucinations-btn"
                    type="button"
                    onClick={() => setShowFailureModal(true)}
                    className="px-space-md py-2 rounded-lg bg-surface-container-high hover:bg-surface-bright text-on-surface font-body-sm text-body-sm font-medium transition-colors border border-outline-variant/30 cursor-pointer"
                  >
                    Inspect Failures
                  </button>
                )}
              </div>
            </div>
          </section>

          {/* Failure Inspection Modal */}
          {showFailureModal && aggregateMetrics && aggregateMetrics.fabricatedFailures.length > 0 && (
            <div
              id="failure-modal"
              className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4"
              onClick={() => setShowFailureModal(false)}
            >
              <div
                className="w-full max-w-2xl bg-surface-container p-space-xl rounded-xl shadow-xl flex flex-col gap-space-md border border-outline-variant/30"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={20} className="text-tertiary-fixed-dim" />
                    <span className="font-title-md text-title-md font-semibold text-on-surface">
                      {aggregateMetrics.fabricatedFailures.length} Fabricated Citation Incidents
                    </span>
                  </div>
                  <button
                    id="close-modal-btn"
                    type="button"
                    onClick={() => setShowFailureModal(false)}
                    className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-surface-container-high text-on-surface-variant cursor-pointer"
                  >
                    <X size={18} />
                  </button>
                </div>
                <div className="flex flex-col gap-space-sm font-code-md text-code-md text-on-surface-variant max-h-60 overflow-y-auto">
                  {aggregateMetrics.fabricatedFailures.map((f, i) => (
                    <div key={i} className="p-space-sm rounded bg-surface-container-lowest border border-outline-variant/20">
                      <span className="text-error font-semibold">[{f.qid}]</span> {f.quote}
                    </div>
                  ))}
                </div>
                <div className="flex justify-end pt-space-xs">
                  <button
                    type="button"
                    onClick={() => setShowFailureModal(false)}
                    className="px-space-md py-1.5 rounded-lg bg-surface-container-high text-on-surface font-body-sm text-body-sm hover:bg-surface-bright cursor-pointer"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Right Source Drawer */}
          <AnimatePresence>
            {activeSource && (
              <div className="fixed inset-0 z-50 flex justify-end">
                {/* Backdrop */}
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => setActiveSource(null)}
                  className="fixed inset-0 bg-background/60 backdrop-blur-xs"
                />

                {/* Drawer Container */}
                <motion.aside
                  id="source-drawer"
                  initial={{ x: '100%' }}
                  animate={{ x: 0 }}
                  exit={{ x: '100%' }}
                  transition={{ duration: 0.2 }}
                  className="relative w-full max-w-md h-full bg-surface-container-low border-l border-outline-variant/30 shadow-2xl p-space-lg flex flex-col gap-space-md z-10 overflow-y-auto"
                >
                  <div className="flex items-center justify-between pb-space-sm border-b border-outline-variant/20">
                    <div className="flex items-center gap-space-sm">
                      <span className="px-2 py-0.5 rounded bg-primary-container text-on-primary-container font-label-code text-label-code font-bold">
                        [{activeSource.id}]
                      </span>
                      <h3 className="font-title-md text-title-md font-semibold text-on-surface truncate max-w-[220px]">
                        {activeSource.title || activeSource.entity}
                      </h3>
                    </div>
                    <button
                      type="button"
                      aria-label="Close drawer"
                      onClick={() => setActiveSource(null)}
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors cursor-pointer"
                    >
                      <X size={18} />
                    </button>
                  </div>

                  {/* Metadata fields: show only if present */}
                  <div className="flex flex-col gap-1.5 text-xs font-mono text-on-surface-variant">
                    {activeSource.entity && (
                      <div className="flex items-center justify-between">
                        <span className="text-outline uppercase text-[10px]">Entity</span>
                        <span className="text-on-surface">{activeSource.entity}</span>
                      </div>
                    )}
                    {activeSource.date && (
                      <div className="flex items-center justify-between">
                        <span className="text-outline uppercase text-[10px]">Date</span>
                        <span className="text-on-surface">{activeSource.date}</span>
                      </div>
                    )}
                  </div>

                  {/* Excerpt in mono block */}
                  <div className="flex flex-col gap-1.5">
                    <span className="font-label-code text-label-code uppercase text-on-surface-variant font-semibold">
                      Excerpt
                    </span>
                    <div className="p-space-md rounded-lg bg-surface-container-lowest font-code-md text-code-md text-on-surface leading-relaxed border border-outline-variant/20 whitespace-pre-wrap">
                      {activeSource.quote ? activeSource.quote : 'No excerpt returned'}
                    </div>
                  </div>

                  {/* Open on GitHub: only when url is present */}
                  {activeSource.url && (
                    <div className="mt-auto pt-space-md">
                      <a
                        href={activeSource.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-surface-container-high hover:bg-surface-bright text-primary font-title-md text-sm font-semibold transition-colors border border-outline-variant/30 cursor-pointer"
                      >
                        <ExternalLink size={16} />
                        <span>Open on GitHub</span>
                      </a>
                    </div>
                  )}
                </motion.aside>
              </div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </MotionConfig>
  );
}
