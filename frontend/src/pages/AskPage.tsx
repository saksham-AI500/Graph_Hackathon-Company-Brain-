import React, { useState } from 'react';
import {
  Send,
  CheckCircle,
  AlertTriangle,
  HelpCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Cpu,
  ShieldCheck,
  Terminal,
  ExternalLink,
  X,
  FileCode,
} from 'lucide-react';
import { useAsk, useStats, formatErrorMessage } from '../api/client';
import type { AskResponse, Source } from '../api/schema';
import { StaggeredText } from '../components/StaggeredText';
import { ScoreBar } from '../components/ScoreBar';
import { CountUp } from '../components/CountUp';

const STARTER_QUESTIONS = [
  'Who should review changes to auth and payments?',
  'Why did we choose the current retry policy?',
  'Who owns search indexing now?',
  'Who is on call next week for gateway?',
];

export function AskPage({ initialSample }: { initialSample?: AskResponse }) {
  const [question, setQuestion] = useState('Who should review changes to auth and payments?');
  const [mode, setMode] = useState<'graph_on' | 'graph_off'>('graph_on');
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const askMutation = useAsk();
  const { data: stats } = useStats();

  const [localResponse, setLocalResponse] = useState<AskResponse | null>(initialSample ?? null);

  const handleSubmit = (qToAsk?: string) => {
    const q = (qToAsk ?? question).trim();
    if (!q) return;
    askMutation.mutate(
      { question: q, mode },
      {
        onSuccess: (data) => {
          setLocalResponse(data);
          setActiveSource(null);
        },
      },
    );
  };

  const response = localResponse;
  const isRefusal = response?.status === 'REFUSED';

  // Helper for source click
  const handleSourceClick = (sourceId: string) => {
    if (!response || !response.sources) return;
    const found = response.sources.find((s) => s.id === sourceId);
    if (found) {
      setActiveSource(found);
    }
  };

  return (
    <div className="w-full max-w-[1440px] mx-auto px-4 md:px-8 py-6">
      <div className="grid grid-cols-12 gap-6 items-start">
        {/* Left Rail */}
        <aside className="col-span-12 lg:col-span-4 flex flex-col gap-5">
          {/* Reasoning Engine & Mode Toggle */}
          <div className="bg-surface-container-low rounded-xl p-4 border border-outline-variant/30 flex flex-col gap-3 shadow-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu size={16} className="text-primary" />
                <span className="font-mono text-xs uppercase tracking-wider text-on-surface-variant font-medium">
                  Reasoning Engine
                </span>
              </div>

              {/* Mode Toggle with ONLY Graph On and Graph Off */}
              <div className="inline-flex p-0.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
                <button
                  type="button"
                  id="toggle-graph-on"
                  onClick={() => setMode('graph_on')}
                  className={`px-3 py-1 rounded text-xs font-mono font-medium transition-all ${
                    mode === 'graph_on'
                      ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Graph On
                </button>
                <button
                  type="button"
                  id="toggle-graph-off"
                  onClick={() => setMode('graph_off')}
                  className={`px-3 py-1 rounded text-xs font-mono font-medium transition-all ${
                    mode === 'graph_off'
                      ? 'bg-primary-container text-on-primary-container font-semibold shadow-xs'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Graph Off
                </button>
              </div>
            </div>

            {/* Model String (from response or stats, never hardcoded) */}
            <div className="flex items-center justify-between gap-2 bg-surface-container-lowest px-3 py-2 rounded-lg border border-outline-variant/20">
              <span className="font-mono text-xs text-on-surface truncate">
                {response?.model || stats?.active_model || 'Loading model...'}
              </span>
              <span className="font-mono text-[9px] text-secondary uppercase tracking-widest px-1.5 py-0.5 rounded bg-surface-container-high font-semibold shrink-0">
                ACTIVE
              </span>
            </div>
          </div>

          {/* Suggested Inquiries / Starter questions */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between px-1">
              <span className="font-mono text-xs uppercase tracking-wider text-on-surface-variant font-semibold">
                Suggested Inquiries
              </span>
            </div>
            <div className="space-y-2">
              {STARTER_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setQuestion(q);
                    handleSubmit(q);
                  }}
                  className="w-full text-left p-3 rounded-xl bg-surface-container-low hover:bg-surface-container-high border border-outline-variant/20 hover:border-outline-variant/50 transition-colors flex items-start gap-2.5 shadow-xs group"
                >
                  <Terminal size={16} className="text-primary shrink-0 mt-0.5 group-hover:translate-x-0.5 transition-transform" />
                  <span className="text-xs md:text-sm font-medium text-on-surface group-hover:text-primary transition-colors leading-snug">
                    {q}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Graph Index Stats (from real /api/stats, not fake) */}
          {stats && (
            <div className="bg-surface-container-lowest rounded-xl p-4 border border-outline-variant/20 flex flex-col gap-2">
              <div className="flex items-center justify-between text-on-surface-variant">
                <span className="font-mono text-xs uppercase tracking-wider">Indexed Nodes</span>
                <span className="font-mono text-xs text-primary font-medium">
                  {stats.node_count.toLocaleString()} entities
                </span>
              </div>
              <div className="flex items-center justify-between text-on-surface-variant text-[11px] font-mono pt-1 border-t border-outline-variant/10">
                <span>{stats.edge_count.toLocaleString()} relations</span>
                <span className="text-secondary font-medium">Synced {stats.last_synced_at.slice(0, 10)}</span>
              </div>
            </div>
          )}
        </aside>

        {/* Center: Main Query and Answer Area */}
        <main className="col-span-12 lg:col-span-8 flex flex-col gap-6">
          {/* Query Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            className="relative bg-surface-container rounded-xl p-3 border border-outline-variant/30 shadow-sm"
          >
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  id="ask-input"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask question across repository index..."
                  className="w-full px-4 py-2.5 bg-surface-container-lowest text-on-surface text-sm rounded-lg border border-outline-variant/30 focus:outline-none focus:ring-1 focus:ring-primary-container transition-all"
                />
              </div>
              <button
                type="submit"
                id="ask-submit-btn"
                disabled={askMutation.isPending || !question.trim()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary hover:bg-primary-hover text-white text-sm font-medium disabled:opacity-50 transition-all cursor-pointer shrink-0"
              >
                {askMutation.isPending ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Thinking...</span>
                  </>
                ) : (
                  <>
                    <Send size={15} />
                    <span>Ask</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Error Message */}
          {askMutation.isError && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-start gap-3">
              <AlertTriangle size={18} className="shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">{askMutation.error.code}</p>
                <p className="text-xs mt-1 text-red-300">
                  {formatErrorMessage(askMutation.error.code, askMutation.error.message)}
                </p>
              </div>
            </div>
          )}

          {/* Answer Card */}
          {response && (
            <div className="bg-surface-container-low rounded-xl p-6 border border-outline-variant/30 flex flex-col gap-5 shadow-md">
              {/* 1. Status Badge & As-of Line */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-outline-variant/20">
                {/* Status Badge */}
                <div>
                  {response.status === 'VERIFIED' && (
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-mono text-xs font-bold uppercase tracking-wider">
                      <CheckCircle size={14} />
                      <span>VERIFIED</span>
                    </div>
                  )}
                  {response.status === 'PARTIALLY_VERIFIED' && (
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 font-mono text-xs font-bold uppercase tracking-wider">
                      <AlertTriangle size={14} />
                      <span>PARTIALLY VERIFIED</span>
                    </div>
                  )}
                  {response.status === 'ANSWERED_UNCERTAIN' && (
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/15 border border-orange-500/30 text-orange-400 font-mono text-xs font-bold uppercase tracking-wider">
                      <HelpCircle size={14} />
                      <span>ANSWERED UNCERTAIN</span>
                    </div>
                  )}
                  {response.status === 'REFUSED' && (
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-500/15 border border-red-500/30 text-red-400 font-mono text-xs font-bold uppercase tracking-wider">
                      <XCircle size={14} />
                      <span>REFUSED</span>
                    </div>
                  )}
                  {!['VERIFIED', 'PARTIALLY_VERIFIED', 'ANSWERED_UNCERTAIN', 'REFUSED'].includes(response.status) && (
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-500/15 border border-zinc-500/30 text-zinc-300 font-mono text-xs font-bold uppercase tracking-wider">
                      <span>{response.status}</span>
                    </div>
                  )}
                </div>

                {/* As-Of Line */}
                <div className="font-mono text-xs text-on-surface-variant">
                  {response.as_of ? `As of ${response.as_of}` : response.context || 'As of live data'}
                  {response.synced_at && <span className="ml-2 text-on-surface">• Synced: {response.synced_at.slice(0, 16)}</span>}
                </div>
              </div>

              {/* 2. Answer Text with [S#] Chips */}
              <div className="text-on-surface text-sm md:text-base leading-relaxed">
                <StaggeredText text={response.answer} onSourceClick={handleSourceClick} />
              </div>

              {/* 3. Ranked Reviewers (if any) */}
              {response.ranking && response.ranking.length > 0 && (
                <div className="flex flex-col gap-3 pt-2">
                  <span className="font-mono text-xs uppercase tracking-wider text-on-surface-variant font-semibold">
                    Ranked Reviewers
                  </span>
                  <div className="space-y-2.5">
                    {response.ranking.map((item) => (
                      <div
                        key={item.rank}
                        className="bg-surface-container rounded-lg p-3.5 border border-outline-variant/20 hover:border-outline-variant/50 transition-colors flex flex-col gap-2"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2.5">
                            <span className="w-5 h-5 rounded-full bg-surface-container-highest text-primary flex items-center justify-center font-mono text-xs font-bold">
                              {item.rank}
                            </span>
                            <span className="font-mono text-sm text-primary font-semibold">
                              @{item.login}
                            </span>
                            {item.tied && (
                              <span className="px-1.5 py-0.2 rounded bg-surface-container-highest text-[10px] font-mono text-on-surface-variant">
                                TIED
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 font-mono text-xs">
                            <span className="text-on-surface font-semibold">
                              {item.score <= 1 ? `${Math.round(item.score * 100)}%` : `${item.score}%`}
                            </span>
                            <span className="text-on-surface-variant uppercase text-[10px]">affinity</span>
                          </div>
                        </div>

                        {/* Score progress bar */}
                        <ScoreBar score={item.score} />

                        {/* Reasons and citing sources */}
                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs text-on-surface-variant">
                          <div className="flex-1">
                            {item.reasons.map((r, ri) => (
                              <p key={ri} className="text-on-surface-variant">
                                • {r}
                              </p>
                            ))}
                          </div>
                          {item.source_ids && item.source_ids.length > 0 && (
                            <div className="flex items-center gap-1">
                              {item.source_ids.map((sid) => (
                                <button
                                  key={sid}
                                  type="button"
                                  onClick={() => handleSourceClick(sid)}
                                  className="px-2 py-0.5 rounded bg-surface-container-highest hover:bg-primary-container hover:text-on-primary-container text-primary font-mono text-[11px] font-medium transition-colors"
                                >
                                  [{sid}]
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 4. Excluded Candidates (if any) */}
              {response.excluded && response.excluded.length > 0 && (
                <div className="p-3.5 rounded-xl bg-surface-container-lowest border border-outline-variant/30 flex flex-col gap-2">
                  <span className="font-mono text-xs uppercase tracking-wider text-on-surface-variant font-semibold">
                    Excluded Candidates
                  </span>
                  <div className="space-y-1.5">
                    {response.excluded.map((exc, i) => (
                      <div key={i} className="flex items-center justify-between text-xs text-on-surface-variant">
                        <span className="font-mono text-on-surface font-medium">@{exc.login}</span>
                        <div className="flex items-center gap-2">
                          <span>{exc.reason}</span>
                          {exc.end_date && <span className="opacity-60">(End date: {exc.end_date})</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 5. Unresolved Issues / Gaps (if any) */}
              {response.unresolved && response.unresolved.length > 0 && (
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/25 flex flex-col gap-2">
                  <span className="font-mono text-xs uppercase tracking-wider text-amber-400 font-semibold">
                    Unresolved Points
                  </span>
                  <ul className="list-disc list-inside space-y-1 text-xs text-amber-200">
                    {response.unresolved.map((gap, i) => (
                      <li key={i}>{gap}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 6. Verifier Counters (CountUp animated) */}
              {response.verifier && (
                <div className="pt-3 border-t border-outline-variant/20">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/20 flex flex-col">
                      <span className="text-[11px] font-mono text-on-surface-variant uppercase">Claims Passed</span>
                      <span className="font-mono text-lg font-bold text-primary mt-1">
                        <CountUp value={response.verifier.claims_passed} /> /{' '}
                        <CountUp value={response.verifier.claims_total} />
                      </span>
                    </div>
                    <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/20 flex flex-col">
                      <span className="text-[11px] font-mono text-on-surface-variant uppercase">Valid Sources</span>
                      <span className="font-mono text-lg font-bold text-secondary mt-1">
                        <CountUp value={response.verifier.sources_valid} /> /{' '}
                        <CountUp value={response.verifier.sources_total} />
                      </span>
                    </div>
                    <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/20 flex flex-col">
                      <span className="text-[11px] font-mono text-on-surface-variant uppercase">Sentences Passed</span>
                      <span className="font-mono text-lg font-bold text-on-surface mt-1">
                        <CountUp value={response.verifier.sentences_passed} /> /{' '}
                        <CountUp value={response.verifier.sentences_total} />
                      </span>
                    </div>
                    <div className="p-3 rounded-lg bg-surface-container-lowest border border-outline-variant/20 flex flex-col">
                      <span className="text-[11px] font-mono text-on-surface-variant uppercase">Post-Hoc Citations</span>
                      <span className="font-mono text-lg font-bold text-on-surface-variant mt-1">
                        <CountUp value={response.verifier.post_hoc_citations} />
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* 7. Collapsible Details (Claims, Tool Calls, Model) */}
              <div className="pt-2">
                <button
                  type="button"
                  id="toggle-details-btn"
                  onClick={() => setDetailsOpen(!detailsOpen)}
                  className="flex items-center justify-between w-full p-2.5 rounded-lg bg-surface-container hover:bg-surface-container-high border border-outline-variant/20 text-xs font-mono text-on-surface-variant hover:text-on-surface transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={14} className="text-primary" />
                    <span>Audit Details ({response.claims.length} claims, {response.tool_calls.length} tool calls)</span>
                  </div>
                  {detailsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>

                {detailsOpen && (
                  <div className="mt-3 p-4 rounded-xl bg-surface-container-lowest border border-outline-variant/20 space-y-4 text-xs font-mono">
                    <div>
                      <span className="text-on-surface-variant font-semibold uppercase tracking-wider block mb-2">
                        Active Model
                      </span>
                      <span className="p-1.5 px-2 rounded bg-surface-container-high text-on-surface">
                        {response.model}
                      </span>
                    </div>

                    {/* Claims */}
                    <div>
                      <span className="text-on-surface-variant font-semibold uppercase tracking-wider block mb-2">
                        Evaluated Claims ({response.claims.length})
                      </span>
                      <div className="space-y-2">
                        {response.claims.map((claim) => (
                          <div
                            key={claim.id}
                            className="p-2.5 rounded-lg bg-surface-container border border-outline-variant/15 flex flex-col gap-1"
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-primary font-bold">{claim.id}</span>
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                                  claim.verified ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                                }`}
                              >
                                {claim.verified ? 'VERIFIED' : 'UNVERIFIED'}
                              </span>
                            </div>
                            <p className="text-on-surface">{claim.text}</p>
                            <div className="flex items-center justify-between text-[11px] text-on-surface-variant pt-1">
                              <span>Path: {claim.verification_path}</span>
                              <span>Sources: {claim.source_ids.join(', ') || 'None'}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Tool Calls */}
                    {response.tool_calls.length > 0 && (
                      <div>
                        <span className="text-on-surface-variant font-semibold uppercase tracking-wider block mb-2">
                          Tool Call Traces ({response.tool_calls.length})
                        </span>
                        <div className="space-y-1.5">
                          {response.tool_calls.map((tc, idx) => (
                            <div
                              key={idx}
                              className="p-2 rounded bg-surface-container border border-outline-variant/15 flex items-center justify-between"
                            >
                              <div className="flex items-center gap-2">
                                <Terminal size={12} className="text-secondary" />
                                <span className="text-primary font-semibold">{tc.tool}</span>
                                <span className="text-on-surface-variant">({tc.result_count} records)</span>
                              </div>
                              <span className="text-on-surface-variant">{tc.ms} ms</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Refusal Variant: no sources rendered */}
              {!isRefusal && response.sources && response.sources.length > 0 && (
                <div className="pt-2 border-t border-outline-variant/20">
                  <span className="font-mono text-xs uppercase tracking-wider text-on-surface-variant font-semibold block mb-2">
                    Evidence Sources ({response.sources.length})
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {response.sources.map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => setActiveSource(s)}
                        className={`text-left p-2.5 rounded-lg border transition-all flex items-start gap-2 ${
                          activeSource?.id === s.id
                            ? 'bg-surface-container-high border-primary text-primary shadow-xs'
                            : 'bg-surface-container border-outline-variant/20 hover:border-outline-variant/50 text-on-surface'
                        }`}
                      >
                        <FileCode size={14} className="text-primary shrink-0 mt-0.5" />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-mono text-xs font-bold">[{s.id}]</span>
                            <span className="font-mono text-[10px] text-on-surface-variant uppercase">
                              {s.entity_type}
                            </span>
                          </div>
                          <p className="font-mono text-xs text-on-surface-variant truncate">{s.entity}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Source Detail Drawer/Modal */}
          {activeSource && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
              <div className="w-full max-w-lg rounded-2xl bg-surface-container border border-outline-variant/40 p-6 shadow-2xl text-on-surface flex flex-col gap-4">
                <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-primary">[{activeSource.id}]</span>
                    <span className="text-sm font-semibold">{activeSource.entity}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveSource(null)}
                    className="p-1 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
                  >
                    <X size={16} />
                  </button>
                </div>

                <div className="space-y-3 font-mono text-xs">
                  <div className="flex justify-between py-1 border-b border-outline-variant/10">
                    <span className="text-on-surface-variant">Entity Type</span>
                    <span className="font-semibold text-primary">{activeSource.entity_type}</span>
                  </div>
                  {activeSource.date && (
                    <div className="flex justify-between py-1 border-b border-outline-variant/10">
                      <span className="text-on-surface-variant">Date</span>
                      <span>{activeSource.date}</span>
                    </div>
                  )}
                  {activeSource.quote && (
                    <div className="py-1">
                      <span className="text-on-surface-variant block mb-1">Quote:</span>
                      <blockquote className="p-2.5 rounded bg-surface-container-lowest text-on-surface border-l-2 border-primary text-xs italic">
                        "{activeSource.quote}"
                      </blockquote>
                    </div>
                  )}
                  {activeSource.url && (
                    <div className="pt-2">
                      <a
                        href={activeSource.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1.5 text-primary hover:underline"
                      >
                        <span>Open in Repository</span>
                        <ExternalLink size={12} />
                      </a>
                    </div>
                  )}
                </div>

                <div className="flex justify-end pt-2 border-t border-outline-variant/20">
                  <button
                    type="button"
                    onClick={() => setActiveSource(null)}
                    className="px-4 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-xs font-medium"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
