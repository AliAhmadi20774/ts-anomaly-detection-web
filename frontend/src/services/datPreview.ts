import { apiRequest } from './client';

export interface DatSignal {
  name: string;
  sample_count: number;
  non_finite_count: number;
  sample: (number | null)[];
}

export interface DatTest {
  name: string;
  operator_name: string | null;
  date_raw: string | null;
  sample_rate_hz: number | null;
  test_definition_id: string | null;
  signals: DatSignal[];
  flat_result_table: {
    columns: string[];
    column_count: number;
    row_count: number;
    sample_rows: string[][];
    valid_shape: boolean;
  } | null;
}

export interface DatDevice {
  device_series: string;
  serial_number: string;
  tests: DatTest[];
}

export interface DatFilePreview {
  index: number;
  name: string;
  size: number;
  status: 'ready' | 'warning' | 'error';
  format?: 'current' | 'legacy';
  devices?: DatDevice[];
  warnings?: string[];
  error?: string;
}

export interface DatPreview {
  previewed_by_code: string;
  summary: { files: number; readable: number; errors: number; devices: number; tests: number; signals: number };
  files: DatFilePreview[];
}

export interface DatImportResult {
  batch: {
    id: string;
    created_at: string;
    devices: {
      id: string;
      device_type: string;
      serial_number: string;
      tests: { id: string; name: string; executed_at: string }[];
    }[];
  } | null;
  summary: { files: number; imported: number; skipped: number; errors: number; test_runs: number };
  files: { name: string; status: 'imported' | 'skipped' | 'error'; test_runs: number; errors?: string[]; run_ids?: string[] }[];
}

export async function previewDatFiles(files: File[], deviceType: string, signal?: AbortSignal) {
  await apiRequest('/auth/csrf/');
  const data = new FormData();
  for (const file of files) data.append('files', file);
  data.append('file_format', 'auto');
  data.append('device_type', deviceType);
  return apiRequest<DatPreview>('/dat/preview/', { method: 'POST', data, signal });
}

export async function importDatFiles(files: File[], deviceType: string, signal?: AbortSignal) {
  await apiRequest('/auth/csrf/');
  const data = new FormData();
  for (const file of files) data.append('files', file);
  data.append('file_format', 'current');
  data.append('device_type', deviceType);
  return apiRequest<DatImportResult>('/dat/import/', { method: 'POST', data, signal });
}
