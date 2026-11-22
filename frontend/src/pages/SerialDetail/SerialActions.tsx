import { DownOutlined, FileExcelOutlined, FilePdfOutlined, LineChartOutlined } from '@ant-design/icons';
import { Alert, Button, Dropdown, Modal, Space, Spin, Tooltip } from 'antd';
import { useState } from 'react';
import { completeExcel } from '@/utils/resultExcel';
import { downloadFile, type TestReport } from '@/utils/testReport';
import { showPdfReport } from '@/utils/testPdf';
import SignalGraphs from './SignalGraphs';

export default function SerialActions({ testName, disabled, loadReport }: {
  testName: string;
  disabled: boolean;
  loadReport: (all: boolean) => Promise<TestReport>;
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
      const report = await loadReport(all);
      if (kind === 'excel') {
        const blob = await completeExcel(report);
        const scope = all ? 'all_tests' : `${report.tests[0].run.test_name}_${report.tests[0].run.id.slice(0, 8)}`;
        downloadFile(blob, `${report.serialNumber}_${scope}_complete.xlsx`);
      } else if (preview && !preview.closed) await showPdfReport(preview, report);
    } catch (failure) {
      preview?.close();
      setError(failure instanceof Error ? failure.message : 'Could not prepare the report.');
    } finally { setBusy(undefined); }
  };

  const unavailable = disabled || Boolean(busy);
  return <div className="serial-actions" aria-label="Test actions">
    <span className="serial-actions-context">Actions for <strong>{testName}</strong></span>
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
      <Space.Compact>
        <Button type="primary" icon={<FileExcelOutlined aria-hidden="true" />} onClick={() => exportReport('excel')}
          loading={busy === 'excel'} disabled={unavailable}>Full Excel</Button>
        <Dropdown trigger={['click']} menu={{ items: [{ key: 'all', label: 'Excel: all tests in this serial' }], onClick: () => exportReport('excel', true) }} disabled={unavailable}>
          <Button type="primary" aria-label="Excel export options" disabled={unavailable} icon={<DownOutlined aria-hidden="true" />} />
        </Dropdown>
      </Space.Compact>
    </Space>
    {busy && <span className="serial-actions-context" role="status">Preparing {busy === 'excel' ? 'Excel' : 'PDF'} with all signal samples…</span>}
    {error && <Alert type="error" showIcon title={error} closable onClose={() => setError(undefined)} />}
    <Modal title={`Signals for ${testName}`} open={graphOpen} onCancel={() => setGraphOpen(false)} footer={null} width={1100} destroyOnHidden>
      {graphLoading ? <div className="batch-detail-results-loading"><Spin aria-label="Loading signals" /></div>
        : graphError ? <Alert type="error" showIcon title={graphError} action={<Button size="small" onClick={plot}>Retry</Button>} />
          : graphReport && <SignalGraphs signals={graphReport.tests[0].signals} />}
    </Modal>
  </div>;
}
