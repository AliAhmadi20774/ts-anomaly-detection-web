import { apiRequest } from './client';
import type { Page } from './definitions';

export interface TestRun {
  id: string;
  test: string;
  test_name: string;
  device_serial_number: string;
  device_type: string;
  device_type_name: string;
  sample_rate_hz: number;
  executed_at: string;
  recorded_by: number;
  recorded_by_code: string;
  created_at: string;
  notes: string;
}

export type TestRunInput = Pick<TestRun, 'test' | 'device_serial_number' | 'executed_at' | 'notes'>;

export const testRuns = {
  list: (params: { page?: number; page_size?: number; search?: string; test?: string } = {}) =>
    apiRequest<Page<TestRun>>('/test-runs/', { params: { ...params } }),
  create: (data: TestRunInput) =>
    apiRequest<TestRun>('/test-runs/', { method: 'POST', data }),
  update: (id: string, data: TestRunInput) =>
    apiRequest<TestRun>(`/test-runs/${id}/`, { method: 'PATCH', data }),
  remove: (id: string) => apiRequest<void>(`/test-runs/${id}/`, { method: 'DELETE' }),
};
