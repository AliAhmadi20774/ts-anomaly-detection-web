import type { BatchTestRun } from '@/services/measurementBatches';
import type { SignalTraceData, TestRunDetail } from '@/services/testRuns';
import { formatTehranDateTime } from './dateTime';

export interface ReportTest {
  run: BatchTestRun;
  detail: TestRunDetail;
  signals: SignalTraceData[];
}

export interface TestReport {
  serialNumber: string;
  deviceType: string;
  deviceTypeId: string;
  deviceRunId: string;
  batchId: string;
  receivedAt: string;
  recordedBy: string;
  tests: ReportTest[];
}

export function testMetadata(report: TestReport, test: ReportTest): string[][] {
  return [
    ['Serial number', report.serialNumber], ['Device type', report.deviceType],
    ['Device type ID', report.deviceTypeId], ['Device run ID', report.deviceRunId],
    ['Test', test.run.test_name], ['Test ID', test.run.id], ['Test definition ID', test.run.test],
    ['Executed at (ISO)', test.run.executed_at],
    ['Executed at (Tehran)', formatTehranDateTime(test.run.executed_at)],
    ['Operator', test.detail.source_operator_name], ['Source file', test.detail.source_file_name],
    ['Sample rate (Hz, test definition)', String(test.run.sample_rate_hz)],
    ['Batch ID', report.batchId], ['Received at (ISO)', report.receivedAt],
    ['Recorded by', report.recordedBy],
  ];
}

export function downloadFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
