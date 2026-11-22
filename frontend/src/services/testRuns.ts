import { apiRequest } from './client';

export interface FlatResultData {
  columns: string[];
  column_count: number;
  flattened_rows: string[];
}

export interface TestRunDetail {
  id: string;
  flat_result_data: FlatResultData | null;
  source_file_name: string;
  source_operator_name: string;
}

export interface SignalTraceSummary {
  id: string;
  name: string;
  sample_count: number;
}

export interface SignalTraceData {
  id: string;
  name: string;
  samples: number[];
}

export const testRuns = {
  detail: (id: string, signal?: AbortSignal) => apiRequest<TestRunDetail>(`/test-runs/${id}/`, { signal }),
  signals: (id: string) => apiRequest<SignalTraceSummary[]>(`/test-runs/${id}/signals/`),
  signalSamples: (runId: string, signalId: string) =>
    apiRequest<SignalTraceData>(`/test-runs/${runId}/signals/${signalId}/`),
};
