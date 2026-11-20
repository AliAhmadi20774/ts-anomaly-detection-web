import { apiRequest } from './client';

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
  signals: (id: string) => apiRequest<SignalTraceSummary[]>(`/test-runs/${id}/signals/`),
  signalSamples: (runId: string, signalId: string) =>
    apiRequest<SignalTraceData>(`/test-runs/${runId}/signals/${signalId}/`),
};
