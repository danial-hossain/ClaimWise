import { getAuthHeaders, formatApiErrorDetail } from '@/lib/api';
import type { CoverageGapAnalysisResult, QAResponse } from '@/types/api';

export interface AnalysisConversation {
  analysis: CoverageGapAnalysisResult;
  messages: { sender: 'user' | 'assistant'; text: string; qaResponse?: QAResponse }[];
}
export async function workflowRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1/${path}`, {
    method, headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(formatApiErrorDetail(data.detail ?? data.error, 'Could not complete the request. Please retry.'));
  return data as T;
}
export function analysisLink(page: 'claims' | 'workspace' | 'coverage', id: string) {
  return `/${page}?analysis_id=${encodeURIComponent(id)}`;
}
