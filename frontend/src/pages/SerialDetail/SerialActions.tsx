import { DownOutlined, FileExcelOutlined, FilePdfOutlined, LineChartOutlined } from '@ant-design/icons';
import { Alert, Button, Dropdown, Modal, Space, Spin, Tooltip } from 'antd';
import { lazy, Suspense, useState } from 'react';
import { completeExcel } from '@/utils/resultExcel';
import { downloadFile, type TestReport } from '@/utils/testReport';
import { showPdfReport } from '@/utils/testPdf';
import './SignalGraphs.css';
const SignalGraphs = lazy(() => import('./SignalGraphs'));

export default function SerialActions({ testName, disabled, loadReport }: {
  testName: string;
  disabled: boolean;
  loadReport: (all: boolean, includeSignals?: boolean) => Promise<TestReport>;
}) {
  const [busy, setBusy] = useState<'excel' | 'pdf'>();
  const [error, setError] = useState<string>();
  const [graphOpen, setGraphOpen] = useState(false);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string>();
  const [graphReport, setGraphReport] = useState<TestReport>();

  const plot = async () => {
    setGraphOpen(true);
    setGraphLoading(true);
    setGraphError(undefined);
    try { setGraphReport(await loadReport(false)); }
    catch (failure) { setGraphError(failure instanceof Error ? failure.message : 'Could not load signals.'); }
    finally { setGraphLoading(false); }
  };

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
      <Button icon={<LineChartOutlined aria-hidden="true" />} onClick={plot} disabled={unavailable}>Plot signals</Button>
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
    <Modal title={`Signals for ${testName}`} open={graphOpen} onCancel={() => setGraphOpen(false)} footer={null}
      width="100vw" style={{ top: 0, maxWidth: '100vw', margin: 0, paddingBottom: 0 }} destroyOnHidden
      styles={{ container: { height: '100dvh', borderRadius: 0, padding: 0, display: 'flex', flexDirection: 'column' },
        header: { position: 'absolute', width: 1, height: 1, padding: 0, margin: -1,
          overflow: 'hidden', clipPath: 'inset(50%)', whiteSpace: 'nowrap', pointerEvents: 'none' },
        body: { flex: 1, minHeight: 0, padding: 0, overflow: 'hidden' } }}>
      {graphLoading ? <div className="signal-workspace-message"><Spin aria-label="Loading signals" /></div>
        : graphError ? <div className="signal-workspace-message"><Alert type="error" showIcon title={graphError} action={<Button size="small" onClick={plot}>Retry</Button>} /></div>
          : graphReport && <Suspense fallback={<Spin aria-label="Loading chart" />}>
            <SignalGraphs testName={testName} signals={graphReport.tests[0].signals} sampleRate={graphReport.tests[0].run.sample_rate_hz} />
          </Suspense>}
    </Modal>
  </div>;
}
