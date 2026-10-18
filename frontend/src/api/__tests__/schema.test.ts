import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  HealthResponseSchema,
  StatsResponseSchema,
  AskResponseSchema,
  CompareResponseSchema,
  NeighborhoodResponseSchema,
  SyncResponseSchema,
  EvalResultsResponseSchema,
  ApiErrorResponseSchema,
} from '../schema';

const SAMPLES_DIR = path.resolve(__dirname, '../../../../docs/api_samples');

function loadSample(fileName: string) {
  const filePath = path.join(SAMPLES_DIR, fileName);
  const content = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(content);
}

describe('API Contract Zod Schemas against samples', () => {
  it('parses get_api_health.json', () => {
    const data = loadSample('get_api_health.json');
    const result = HealthResponseSchema.safeParse(data);
    expect(result.success).toBe(true);
  });

  it('parses get_api_stats.json', () => {
    const data = loadSample('get_api_stats.json');
    const result = StatsResponseSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.active_model).toBeDefined();
    }
  });

  it('parses post_api_ask_graph_on.json', () => {
    const data = loadSample('post_api_ask_graph_on.json');
    const result = AskResponseSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.status).toBe('VERIFIED');
      expect(Array.isArray(result.data.ranking)).toBe(true);
      expect(result.data.claims.length).toBeGreaterThan(0);
      expect(result.data.claims[0].verified).toBe(true);
    }
  });

  it('parses post_api_ask_graph_off.json', () => {
    const data = loadSample('post_api_ask_graph_off.json');
    const result = AskResponseSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.mode).toBe('graph_off');
    }
  });

  it('parses post_api_compare.json', () => {
    const data = loadSample('post_api_compare.json');
    const result = CompareResponseSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.comparison.on_status).toBeDefined();
      expect(result.data.comparison.off_status).toBeDefined();
    }
  });

  it('parses get_api_graph_neighborhood.json', () => {
    const data = loadSample('get_api_graph_neighborhood.json');
    const result = NeighborhoodResponseSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.nodes.length).toBeGreaterThan(0);
      expect(result.data.edges.length).toBeGreaterThan(0);
    }
  });

  it('parses post_api_sync.json', () => {
    const data = loadSample('post_api_sync.json');
    const result = SyncResponseSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.status).toBe('completed');
    }
  });

  it('parses get_api_eval_results.json', () => {
    const data = loadSample('get_api_eval_results.json');
    const result = EvalResultsResponseSchema.safeParse(data);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.split_name).toBe('development');
      expect(result.data.architectures.graph_on).toBeDefined();
    }
  });

  it('parses standardized errors', () => {
    const codes = [
      'MISSING_KEY',
      'PROVIDER_CREDITS',
      'PROVIDER_RATE_LIMIT',
      'BACKEND_UNAVAILABLE',
      'INVALID_REQUEST',
    ];
    for (const code of codes) {
      const errPayload = {
        error: {
          code,
          message: `Test error for ${code}`,
          retryable: code === 'PROVIDER_RATE_LIMIT',
        },
      };
      const result = ApiErrorResponseSchema.safeParse(errPayload);
      expect(result.success).toBe(true);
    }
  });
});
