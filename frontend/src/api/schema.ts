import { z } from 'zod';

// ==========================================
// Standardized Error Schema
// ==========================================
export const ApiErrorPayloadSchema = z.object({
  code: z.enum([
    'MISSING_KEY',
    'PROVIDER_CREDITS',
    'PROVIDER_RATE_LIMIT',
    'BACKEND_UNAVAILABLE',
    'INVALID_REQUEST',
  ]).or(z.string()),
  message: z.string(),
  retryable: z.boolean().default(false),
});

export const ApiErrorResponseSchema = z.object({
  error: ApiErrorPayloadSchema,
});

export type ApiErrorPayload = z.infer<typeof ApiErrorPayloadSchema>;
export type ApiErrorResponse = z.infer<typeof ApiErrorResponseSchema>;

// ==========================================
// Health & Stats Schemas
// ==========================================
export const HealthResponseSchema = z.object({
  status: z.string(),
  service: z.string(),
  timestamp: z.string(),
  database: z.enum(['connected', 'disconnected']).or(z.string()),
  model: z.string(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const StatsResponseSchema = z.object({
  node_count: z.number(),
  edge_count: z.number(),
  nodes_by_label: z.record(z.string(), z.number()),
  edges_by_type: z.record(z.string(), z.number()),
  last_synced_at: z.string(),
  active_model: z.string(),
});
export type StatsResponse = z.infer<typeof StatsResponseSchema>;

// ==========================================
// Ask Endpoint Sub-Schemas
// ==========================================
export const RankingItemSchema = z.object({
  rank: z.number(),
  login: z.string(),
  score: z.number(),
  reasons: z.array(z.string()),
  source_ids: z.array(z.string()),
  tied: z.boolean(),
});
export type RankingItem = z.infer<typeof RankingItemSchema>;

export const ClaimSchema = z.object({
  id: z.string(),
  text: z.string(),
  type: z.string(),
  source_ids: z.array(z.string()),
  verified: z.boolean(),
  verification_path: z.string(),
});
export type Claim = z.infer<typeof ClaimSchema>;

export const ExcludedItemSchema = z.object({
  login: z.string(),
  reason: z.string(),
  end_date: z.string().nullable().optional(),
});
export type ExcludedItem = z.infer<typeof ExcludedItemSchema>;

export const SourceSchema = z.object({
  id: z.string(),
  entity: z.string(),
  entity_type: z.string(),
  url: z.string(),
  date: z.string(),
  quote: z.string(),
  title: z.string().optional(),
});
export type Source = z.infer<typeof SourceSchema>;

export const ToolCallSchema = z.object({
  tool: z.string(),
  args: z.record(z.string(), z.unknown()),
  result_count: z.number(),
  ms: z.number(),
});
export type ToolCall = z.infer<typeof ToolCallSchema>;

export const SentenceLogSchema = z.object({
  sentence: z.string(),
  claim_ids: z.array(z.string()),
  cited_sources: z.array(z.string()),
  verification_path: z.string(),
  score: z.number(),
  passed: z.boolean(),
  reason: z.string().nullable().optional(),
});
export type SentenceLog = z.infer<typeof SentenceLogSchema>;

export const VerifierSchema = z.object({
  claims_total: z.number(),
  claims_passed: z.number(),
  claims_fully_supported: z.number(),
  sources_valid: z.number(),
  sources_total: z.number(),
  sentences_total: z.number(),
  sentences_passed: z.number(),
  post_hoc_citations: z.number(),
  fabricated_citations: z.number().optional(),
  sentence_logs: z.array(SentenceLogSchema).default([]),
});
export type Verifier = z.infer<typeof VerifierSchema>;

export const AskResponseSchema = z.object({
  status: z.enum(['VERIFIED', 'PARTIALLY_VERIFIED', 'ANSWERED_UNCERTAIN', 'REFUSED']).or(z.string()),
  answer: z.string(),
  context: z.string(),
  ranking: z.array(RankingItemSchema).default([]),
  reasoning: z.string().default(''),
  claims: z.array(ClaimSchema).default([]),
  excluded: z.array(ExcludedItemSchema).default([]),
  unresolved: z.array(z.string()).default([]),
  sources: z.array(SourceSchema).default([]),
  mode: z.enum(['graph_on', 'graph_off']).or(z.string()),
  as_of: z.string().nullable().optional(),
  synced_at: z.string().default(''),
  model: z.string(),
  tool_calls: z.array(ToolCallSchema).default([]),
  verifier: VerifierSchema.optional(),
  what_changed: z.record(z.string(), z.unknown()).nullable().optional(),
});
export type AskResponse = z.infer<typeof AskResponseSchema>;

// ==========================================
// Compare Endpoint Schemas
// ==========================================
export const DifferenceCountsSchema = z.object({
  claims_diff: z.number().nullable().optional(),
  sources_diff: z.number().nullable().optional(),
  facts_passed_diff: z.number().nullable().optional(),
  violations_diff: z.number().nullable().optional(),
});
export type DifferenceCounts = z.infer<typeof DifferenceCountsSchema>;

export const ComparisonSchema = z.object({
  on_status: z.string(),
  off_status: z.string(),
  on_claims_count: z.number(),
  off_claims_count: z.number(),
  on_sources_count: z.number(),
  off_sources_count: z.number(),
  fabricated_citations_in_off: z.number(),
  verified: z.boolean(),
  difference_counts: DifferenceCountsSchema.nullable().optional(),
});
export type Comparison = z.infer<typeof ComparisonSchema>;

export const CompareResponseSchema = z.object({
  question: z.string(),
  as_of: z.string().nullable().optional(),
  graph_on: AskResponseSchema,
  graph_off: AskResponseSchema,
  comparison: ComparisonSchema,
});
export type CompareResponse = z.infer<typeof CompareResponseSchema>;

// ==========================================
// Graph Neighborhood Schemas
// ==========================================
export const GraphNodeSchema = z.object({
  id: z.string(),
  labels: z.union([z.array(z.string()), z.string()]).optional(),
  label: z.string().optional(),
  properties: z.record(z.string(), z.unknown()).default({}),
});
export type GraphNode = z.infer<typeof GraphNodeSchema>;

export const GraphEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  type: z.string(),
  properties: z.record(z.string(), z.unknown()).optional(),
});
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;

export const NeighborhoodResponseSchema = z.object({
  entity: z.string(),
  as_of: z.string().nullable().optional(),
  node_count: z.number(),
  edge_count: z.number(),
  nodes: z.array(GraphNodeSchema).default([]),
  edges: z.array(GraphEdgeSchema).default([]),
});
export type NeighborhoodResponse = z.infer<typeof NeighborhoodResponseSchema>;

// ==========================================
// Sync Endpoint Schemas
// ==========================================
export const SyncChangeSchema = z.object({
  id: z.string(),
  entity: z.string(),
  type: z.string(),
  action: z.string(),
  timestamp: z.string(),
  summary: z.string(),
  author: z.string(),
});
export type SyncChange = z.infer<typeof SyncChangeSchema>;

export const SyncResponseSchema = z.object({
  run_id: z.string(),
  repo: z.string(),
  status: z.string(),
  events_processed: z.number().optional(),
  mutations_applied: z.number().optional(),
  failures: z.number().optional(),
  dry_run: z.boolean().optional(),
  synced_at: z.string().optional(),
  changes: z.array(SyncChangeSchema).default([]),
});
export type SyncResponse = z.infer<typeof SyncResponseSchema>;

// ==========================================
// Eval Results Schemas
// ==========================================
export const ArchitectureStatsSchema = z.object({
  architecture: z.string().optional(),
  total_evaluations: z.number().default(0),
  overall_accuracy_pct: z.number().default(0),
  citation_support_rate_pct: z.number().default(0),
  unsupported_claim_rate_pct: z.number().default(0),
  mean_latency_ms: z.number().default(0),
  median_latency_ms: z.number().optional(),
  overall_correct: z.number().optional(),
  answerable_count: z.number().optional(),
});
export type ArchitectureStats = z.infer<typeof ArchitectureStatsSchema>;

export const EvalOutcomeSchema = z.object({
  run_id: z.string().optional(),
  timestamp: z.string().optional(),
  question_id: z.string().optional(),
  id: z.string().optional(),
  question: z.string().optional(),
  architecture: z.string().optional(),
  mode: z.string().optional(),
  status: z.string().optional(),
  repetition: z.number().optional(),
  raw_response: z.string().optional(),
  answer_preview: z.string().optional(),
  structured_claims: z.array(z.string()).optional(),
  claims_count: z.number().optional(),
  sources_count: z.number().optional(),
  correct: z.boolean().optional(),
  supported: z.boolean().optional(),
  latency_ms: z.number().nullable().optional(),
  score: z.record(z.string(), z.unknown()).optional(),
  citations: z.array(z.string()).optional(),
  execution_type: z.string().optional(),
  model_identifier: z.string().optional(),
  error: z.unknown().optional(),
});
export type EvalOutcome = z.infer<typeof EvalOutcomeSchema>;

export const EvalResultsResponseSchema = z.object({
  run_id: z.string().default(''),
  timestamp: z.string().default(''),
  split_name: z.string().default('development'),
  code_revision: z.string().optional(),
  architectures: z.record(z.string(), ArchitectureStatsSchema).default({}),
  results: z.array(EvalOutcomeSchema).optional(),
  individual_outcomes: z.array(EvalOutcomeSchema).optional(),
});
export type EvalResultsResponse = z.infer<typeof EvalResultsResponseSchema>;
