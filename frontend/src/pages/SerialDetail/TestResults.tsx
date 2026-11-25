import { Alert, Empty, Grid, Spin, Table, Typography } from 'antd';
import { type ReactNode, useEffect, useState } from 'react';
import type { TestRunDetail } from '@/services/testRuns';

export default function TestResults({ runId, testName, canView, getDetail, actions }: {
  runId: string;
  testName: string;
  canView: boolean;
  getDetail: (id: string) => Promise<TestRunDetail>;
  actions: ReactNode;
}) {
  const screens = Grid.useBreakpoint();
  const [detail, setDetail] = useState<TestRunDetail>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    setDetail(undefined);
    setError(undefined);
    setLoading(true);
    if (!canView) {
      setLoading(false);
      return () => controller.abort();
    }
    getDetail(runId).then((result) => {
      if (!controller.signal.aborted) setDetail(result);
    }).catch((failure) => {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Could not load test results.');
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [runId, canView, getDetail]);

  const table = detail?.flat_result_data;
  const validShape = table && Number.isInteger(table.column_count) && table.column_count >= 0
    && table.columns.length === table.column_count
    && (table.column_count === 0 ? table.flattened_rows.length === 0 : table.flattened_rows.length % table.column_count === 0);
  const rows = table && validShape && table.column_count > 0
    ? Array.from({ length: table.flattened_rows.length / table.column_count }, (_, index) =>
      table.flattened_rows.slice(index * table.column_count, (index + 1) * table.column_count))
    : [];

  return (
    <section className="batch-detail-panel" aria-label={`Results for ${testName}`}>
      <div className="batch-detail-panel-header serial-results-header">
        <h2>Results for {testName}</h2>
        {actions}
      </div>
      <div className="batch-detail-results-body">
        {!canView ? <Typography.Text type="secondary">Test result access is unavailable for your account.</Typography.Text> : <>
          {loading && <div className="batch-detail-results-loading"><Spin aria-label="Loading test results" /></div>}
          {error && <Alert type="error" showIcon title={error} />}
          {!loading && !error && detail && <>
            {detail.source_operator_name && <div className="batch-detail-result-source">
              {detail.source_operator_name && <span>Operator: <strong>{detail.source_operator_name}</strong></span>}
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
