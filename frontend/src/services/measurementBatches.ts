import { apiRequest } from './client';
import type { Page } from './definitions';

export interface BatchTestRun {
  id: string;
  test: string;
  test_name: string;
  executed_at: string;
  sample_rate_hz: number;
}

export interface BatchDevice {
  id: string;
  device_type: string;
  device_type_name: string;
  serial_number: string;
  tests: BatchTestRun[];
}

export interface MeasurementBatch {
  id: string;
  created_at: string;
  recorded_by_code: string;
  devices: BatchDevice[];
}

export const measurementBatches = {
  list: (params: { page?: number; page_size?: number } = {}) =>
    apiRequest<Page<MeasurementBatch>>('/measurement-batches/', { params }),
  detail: (id: string) => apiRequest<MeasurementBatch>(`/measurement-batches/${id}/`),
};
