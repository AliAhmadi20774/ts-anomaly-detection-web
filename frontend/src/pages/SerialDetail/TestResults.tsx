import { DownloadOutlined } from '@ant-design/icons';
import { Alert, Button, Empty, Grid, Spin, Table, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { type TestRunDetail, testRuns } from '@/services/testRuns';
import { resultExcel } from '@/utils/resultExcel';

export default function TestResults({ runId, testName, canView }: {
  runId: string;
  testName: string;
  canView: boolean;
}) {
  const screens = Grid.useBreakpoint();
  const [detail, setDetail] = useState<TestRunDetail>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    setDetail(undefined);
    setError(undefined);
    setLoading(true);
    if (!canView) {
      setLoading(false);
      return () => controller.abort();
    }
    testRuns.detail(runId, controller.signal).then((result) => {
      if (!controller.signal.aborted) setDetail(result);
    }).catch((failure) => {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Could not load test results.');
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [runId, canView]);

  const table = detail?.flat_result_data;
  const validShape = table && Number.isInteger(table.column_count) && table.column_count >= 0
    && table.columns.length === table.column_count
    && (table.column_count === 0 ? table.flattened_rows.length === 0 : table.flattened_rows.length % table.column_count === 0);
  const rows = table && validShape && table.column_count > 0
    ? Array.from({ length: table.flattened_rows.length / table.column_count }, (_, index) =>
      table.flattened_rows.slice(index * table.column_count, (index + 1) * table.column_count))
    : [];

  const exportExcel = async () => {
    if (!table || !validShape || !rows.length) return;
    setExporting(true);
    setExportError(undefined);
    try {
      const blob = await resultExcel(table);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${testName.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')}_${runId.slice(0, 8)}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) {
      setExportError(failure instanceof Error ? failure.message : 'Could not export test results.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <section className="batch-detail-panel" aria-label={`Results for ${testName}`}>
      <div className="batch-detail-panel-header">
        <div><span className="batch-detail-eyebrow">SELECTED TEST</span><h2>Results for {testName}</h2></div>
        <Button type="primary" icon={<DownloadOutlined aria-hidden="true" />} onClick={exportExcel} loading={exporting}
          disabled={!canView || loading || !validShape || rows.length === 0}>Export Excel</Button>
      </div>
      <div className="batch-detail-results-body">
        {!canView ? <Typography.Text type="secondary">Test result access is unavailable for your account.</Typography.Text> : <>
          {loading && <div className="batch-detail-results-loading"><Spin aria-label="Loading test results" /></div>}
          {error && <Alert type="error" showIcon title={error} />}
          {exportError && <Alert type="error" showIcon title={exportError} />}
          {!loading && !error && detail && <>
            {(detail.source_operator_name || detail.source_file_name) && <div className="batch-detail-result-source">
              {detail.source_operator_name && <span>Operator: <strong>{detail.source_operator_name}</strong></span>}
              {detail.source_file_name && <span>Source: <strong>{detail.source_file_name}</strong></span>}
            </div>}
            {table && !validShape ? <Alert type="warning" showIcon title="The stored result table has incomplete rows or columns." />
              : !table || rows.length === 0 ? <Empty description="No result table stored for this test" />
              : <Table<string[]> className="batch-detail-results-table" size="small" tableLayout="fixed"
                rowKey={(_, index) => String(index)} dataSource={rows}
                scroll={screens.lg ? undefined : { x: 1100 }}
                pagination={false}
                columns={table.columns.map((name, index) => ({
                  title: name, key: String(index), width: table.column_count > 6 ? (index === 0 ? '13%' : index === 1 ? '9%' : undefined) : undefined,
                  render: (_, row) => row[index],
                }))} />}
          </>}
        </>}
      </div>
    </section>
  );
}
