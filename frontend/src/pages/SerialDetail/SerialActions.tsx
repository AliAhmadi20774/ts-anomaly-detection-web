import { DownOutlined, FileExcelOutlined, FilePdfOutlined, LineChartOutlined } from '@ant-design/icons';
import { Alert, Button, Dropdown, Modal, Space, Spin, Tooltip } from 'antd';
import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { BatchTestRun } from '@/services/measurementBatches';
import { completeExcel } from '@/utils/resultExcel';
import { downloadFile, type TestReport } from '@/utils/testReport';
import { showPdfReport } from '@/utils/testPdf';
import './SignalGraphs.css';
const SignalGraphs = lazy(() => import('./SignalGraphs'));

export default function SerialActions({ testName, testId, tests, disabled, loadReport }: {
  testName: string;
  testId: string;
  tests: BatchTestRun[];
  disabled: boolean;
  loadReport: (all: boolean, includeSignals?: boolean, testId?: string) => Promise<TestReport>;
}) {
  const [busy, setBusy] = useState<'excel' | 'pdf'>();
  const [error, setError] = useState<string>();
  const [graphOpen, setGraphOpen] = useState(false);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string>();
  const [graphReport, setGraphReport] = useState<TestReport>();
  const [graphTestId, setGraphTestId] = useState(testId);
  const graphRequest = useRef(0);
  useEffect(() => () => { graphRequest.current += 1; }, []);

  const plot = async (id = testId) => {
    const request = ++graphRequest.current;
    setGraphTestId(id);
    setGraphOpen(true);
    setGraphLoading(true);
    setGraphError(undefined);
    try {
      const report = await loadReport(false, true, id);
      if (request === graphRequest.current) setGraphReport(report);
    } catch (failure) {
      if (request === graphRequest.current) setGraphError(failure instanceof Error ? failure.message : 'Could not load signals.');
    } finally { if (request === graphRequest.current) setGraphLoading(false); }
  };
  const graphTestName = tests.find((test) => test.id === graphTestId)?.test_name ?? testName;
  const testSelector = tests.length > 1 ? <Dropdown trigger={['click']} getPopupContainer={(trigger) => trigger.parentElement!}
    menu={{ selectedKeys: [graphTestId], items: tests.map((test) => ({ key: test.id, label: test.test_name })),
      onClick: ({ key }) => { if (key !== graphTestId) void plot(key); } }}>
    <button type="button" className="signal-test-selector" aria-label="Change test">
      <span className="signal-test-name">{graphTestName}</span><DownOutlined aria-hidden="true" />
    </button>
  </Dropdown> : <span className="signal-test-name">{graphTestName}</span>;

  const exportReport = async (kind: 'excel' | 'pdf', all = false) => {
    // Open synchronously from the click so popup blockers allow PDF previews.
    const preview = kind === 'pdf' ? window.open('', '_blank') : null;
    setError(undefined);
    if (kind === 'pdf' && !preview) {
      setError('Allow popups for this site to open the PDF report.');
      return;
    }
    if (preview) {
      preview.opener = null;
      preview.document.title = 'Preparing test report';
      preview.document.body.textContent = 'Preparing your report…';
    }
    setBusy(kind);
    try {
      const report = await loadReport(all, kind === 'excel');
      if (kind === 'excel') {
        const blob = await completeExcel(report);
        const scope = all ? 'all_tests' : report.tests[0].run.test_name;
        downloadFile(blob, `${report.serialNumber}_${scope}.xlsx`);
      } else if (preview && !preview.closed) await showPdfReport(preview, report);
    } catch (failure) {
      preview?.close();
      setError(failure instanceof Error ? failure.message : 'Could not prepare the report.');
    } finally { setBusy(undefined); }
  };

  const unavailable = disabled || Boolean(busy);
  return <div className="serial-actions" aria-label="Test actions">
    <Space wrap size={8}>
      <Button icon={<LineChartOutlined aria-hidden="true" />} onClick={() => plot()} disabled={unavailable}>Plot signals</Button>
      <Space.Compact>
        <Tooltip title="Open a print-ready report and choose Save as PDF">
          <Button icon={<FilePdfOutlined aria-hidden="true" />} onClick={() => exportReport('pdf')}
            loading={busy === 'pdf'} disabled={unavailable}>PDF report</Button>
        </Tooltip>
        <Dropdown trigger={['click']} menu={{ items: [{ key: 'all', label: 'PDF: all tests in this serial' }], onClick: () => exportReport('pdf', true) }} disabled={unavailable}>
          <Button aria-label="PDF report options" disabled={unavailable} icon={<DownOutlined aria-hidden="true" />} />
        </Dropdown>
      </Space.Compact>
      <Dropdown trigger={['click']} disabled={unavailable} menu={{
        items: [{ key: 'selected', label: 'This test only' }, { key: 'all', label: 'All tests' }],
        onClick: ({ key }) => exportReport('excel', key === 'all'),
      }}>
        <Button type="primary" icon={<FileExcelOutlined aria-hidden="true" />}
          loading={busy === 'excel'} disabled={unavailable}>Excel <DownOutlined aria-hidden="true" /></Button>
      </Dropdown>
    </Space>
    {busy && <span className="serial-actions-context" role="status">{busy === 'excel' ? 'Preparing Excel with all signal samples…' : 'Preparing PDF report…'}</span>}
    {error && <Alert type="error" showIcon title={error} closable onClose={() => setError(undefined)} />}
    <Modal title={`Signals for ${graphTestName}`} open={graphOpen} onCancel={() => { graphRequest.current += 1; setGraphOpen(false); }} footer={null}
      width="100vw" style={{ top: 0, maxWidth: '100vw', margin: 0, paddingBottom: 0 }} destroyOnHidden
      styles={{ container: { height: '100dvh', borderRadius: 0, padding: 0, display: 'flex', flexDirection: 'column' },
        header: { position: 'absolute', width: 1, height: 1, padding: 0, margin: -1,
          overflow: 'hidden', clipPath: 'inset(50%)', whiteSpace: 'nowrap', pointerEvents: 'none' },
        body: { flex: 1, minHeight: 0, padding: 0, overflow: 'hidden' } }}>
      {graphLoading || graphError ? <div className="signal-workspace">
        <div className="signal-legend">{testSelector}</div>
        <div className="signal-workspace-message">{graphLoading ? <Spin aria-label="Loading signals" />
          : <Alert type="error" showIcon title={graphError} action={<Button size="small" onClick={() => plot(graphTestId)}>Retry</Button>} />}</div>
      </div>
          : graphReport && <Suspense fallback={<Spin aria-label="Loading chart" />}>
            <SignalGraphs key={graphTestId} testName={graphTestName} testSelector={testSelector}
              signals={graphReport.tests[0].signals} sampleRate={graphReport.tests[0].run.sample_rate_hz} />
          </Suspense>}
    </Modal>
  </div>;
}
