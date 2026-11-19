import { apiRequest } from './client';

export type DatFormat = 'auto' | 'current' | 'legacy';

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
  status: 'ready' | 'warning' | 'duplicate' | 'error';
  format?: 'current' | 'legacy';
  devices?: DatDevice[];
  warnings?: string[];
  error?: string;
  duplicate_of?: string;
}

export interface DatPreview {
  previewed_by_code: string;
  summary: { files: number; readable: number; errors: number; duplicates: number; devices: number; tests: number; signals: number };
  files: DatFilePreview[];
}

export async function previewDatFiles(files: File[], fileFormat: DatFormat, signal?: AbortSignal) {
  await apiRequest('/auth/csrf/');
  const data = new FormData();
  for (const file of files) data.append('files', file);
  data.append('file_format', fileFormat);
  return apiRequest<DatPreview>('/dat/preview/', { method: 'POST', data, signal });
}
