import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  HealthResponseSchema,
  StatsResponseSchema,
  AskResponseSchema,
  CompareResponseSchema,
  NeighborhoodResponseSchema,
  SyncResponseSchema,
  EvalResultsResponseSchema,
  ApiErrorResponseSchema,
  type HealthResponse,
  type StatsResponse,
  type AskResponse,
  type CompareResponse,
  type NeighborhoodResponse,
  type SyncResponse,
  type EvalResultsResponse,
} from './schema';

export const API_BASE_URL = import.meta.env.VITE_API_URL || (typeof window !== 'undefined' ? '' : 'http://localhost:8000');

export class ApiError extends Error {
  code: string;
  retryable: boolean;

  constructor(code: string, message: string, retryable = false) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.retryable = retryable;
  }
}

export function formatErrorMessage(code: string, fallbackMessage?: string): string {
  switch (code) {
    case 'MISSING_KEY':
      return 'The server has no model key configured.';
    case 'PROVIDER_CREDITS':
      return 'The model provider has no available credits.';
    case 'PROVIDER_RATE_LIMIT':
      return 'The model provider rate limit was reached. Try again shortly.';
    case 'BACKEND_UNAVAILABLE':
      return 'The backend is unavailable.';
    case 'INVALID_REQUEST':
      return 'The request could not be processed.';
    default:
      return fallbackMessage || 'The request could not be processed.';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  schema: { safeParse: (val: unknown) => { success: true; data: T } | { success: false; error: { errors: Array<{ path: (string | number)[]; message: string }> } } },
): Promise<T> {
  const cleanEndpoint = endpoint.startsWith('/api') && API_BASE_URL.endsWith('/api')
    ? endpoint.slice(4)
    : endpoint;
  const url = `${API_BASE_URL}${cleanEndpoint}`;
  let response: Response;

  try {
    response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new ApiError(
      'BACKEND_UNAVAILABLE',
      'The backend is unavailable.',
      true,
    );
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(
      'BACKEND_UNAVAILABLE',
      'The backend is unavailable.',
      false,
    );
  }

  if (!response.ok) {
    const errorParsed = ApiErrorResponseSchema.safeParse(data);
    if (errorParsed.success) {
      const err = errorParsed.data.error;
      throw new ApiError(err.code, formatErrorMessage(err.code, err.message), err.retryable);
    }
    const rawError = data as { error?: { code?: string; message?: string; retryable?: boolean } };
    const code = rawError?.error?.code || 'INVALID_REQUEST';
    const retryable = rawError?.error?.retryable ?? false;
    throw new ApiError(code, formatErrorMessage(code), retryable);
  }

  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    console.error(`Contract parse error on ${endpoint}:`, parsed.error);
    throw new ApiError(
      'INVALID_REQUEST',
      'The request could not be processed.',
      false,
    );
  }

  return parsed.data;
}

// ==========================================
// TanStack Query Hooks
// ==========================================

export function useHealth() {
  return useQuery<HealthResponse, ApiError>({
    queryKey: ['health'],
    queryFn: () => request('/api/health', { method: 'GET' }, HealthResponseSchema),
    refetchInterval: 15000,
    retry: 1,
  });
}

export function useStats() {
  return useQuery<StatsResponse, ApiError>({
    queryKey: ['stats'],
    queryFn: () => request('/api/stats', { method: 'GET' }, StatsResponseSchema),
    staleTime: 30000,
    retry: 1,
  });
}

export function useAsk() {
  return useMutation<
    AskResponse,
    ApiError,
    { question: string; mode?: 'graph_on' | 'graph_off'; as_of?: string | null }
  >({
    mutationFn: (body) =>
      request(
        '/api/ask',
        {
          method: 'POST',
          body: JSON.stringify({
            question: body.question,
            mode: body.mode || 'graph_on',
            as_of: body.as_of ?? null,
          }),
        },
        AskResponseSchema,
      ),
  });
}

export function useCompare() {
  return useMutation<
    CompareResponse,
    ApiError,
    { question: string; as_of?: string | null }
  >({
    mutationFn: (body) =>
      request(
        '/api/compare',
        {
          method: 'POST',
          body: JSON.stringify({
            question: body.question,
            as_of: body.as_of ?? null,
          }),
        },
        CompareResponseSchema,
      ),
  });
}

export function useNeighborhood(entity: string | null, as_of?: string | null) {
  return useQuery<NeighborhoodResponse, ApiError>({
    queryKey: ['neighborhood', entity, as_of],
    queryFn: () => {
      if (!entity) {
        throw new ApiError('INVALID_REQUEST', 'Entity parameter is required');
      }
      const params = new URLSearchParams({ entity });
      if (as_of) params.set('as_of', as_of);
      return request(
        `/api/graph/neighborhood?${params.toString()}`,
        { method: 'GET' },
        NeighborhoodResponseSchema,
      );
    },
    enabled: Boolean(entity),
    staleTime: 60000,
  });
}

export function useSync() {
  const queryClient = useQueryClient();
  return useMutation<SyncResponse, ApiError, void>({
    mutationFn: () => request('/api/sync', { method: 'POST', body: '{}' }, SyncResponseSchema),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      queryClient.invalidateQueries({ queryKey: ['neighborhood'] });
    },
  });
}

export function useEvalResults() {
  return useQuery<EvalResultsResponse, ApiError>({
    queryKey: ['eval_results'],
    queryFn: () => request('/api/eval/results', { method: 'GET' }, EvalResultsResponseSchema),
    staleTime: 60000,
    retry: 1,
  });
}
