import { ClockCircleOutlined, ExperimentOutlined, NumberOutlined, RightOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { Link, useModel, useParams } from '@umijs/max';
import { Alert, Breadcrumb, Empty, Spin } from 'antd';
import { useEffect, useState } from 'react';
import { hasPermission } from '@/services/auth';
import { type MeasurementBatch, measurementBatches } from '@/services/measurementBatches';
import { formatTehranDateTime } from '@/utils/dateTime';
import TestResults from './TestResults';
import SerialActions from './SerialActions';
import useTestData from './useTestData';
import type { ReportTest, TestReport } from '@/utils/testReport';
import '../SerialBatchDetail/index.css';

export default function SerialDetailPage() {
  const { batchId, deviceId } = useParams<{ batchId: string; deviceId: string }>();
  const { initialState } = useModel('@@initialState');
  const canViewResults = hasPermission(initialState?.currentUser, 'devices.view_testrun');
  const [batch, setBatch] = useState<MeasurementBatch>();
  const [batchLoading, setBatchLoading] = useState(true);
  const [batchError, setBatchError] = useState<string>();
  const [selectedTestId, setSelectedTestId] = useState<string>();
  const { getDetail, getSignals } = useTestData(deviceId, canViewResults);

  useEffect(() => {
    let active = true;
    setBatchLoading(true);
    setBatchError(undefined);
    setBatch(undefined);
    setSelectedTestId(undefined);
    if (!batchId || !deviceId) {
      setBatchError('Serial was not specified.');
      setBatchLoading(false);
      return () => { active = false; };
    }
    measurementBatches.detail(batchId).then((result) => {
      if (!active) return;
      const device = result.devices.find((item) => item.id === deviceId);
      if (!device) {
        setBatchError('Serial number was not found in this batch.');
        return;
      }
      setBatch(result);
      setSelectedTestId(device.tests[0]?.id);
    }).catch((error) => {
      if (active) setBatchError(error instanceof Error ? error.message : 'Could not load this serial number.');
    }).finally(() => {
      if (active) setBatchLoading(false);
    });
    return () => { active = false; };
  }, [batchId, deviceId]);

  const device = batch?.devices.find((item) => item.id === deviceId);
  const selectedTest = device?.tests.find((test) => test.id === selectedTestId);

  const loadReport = async (all: boolean): Promise<TestReport> => {
    if (!batch || !device || !selectedTest) throw new Error('Select a test first.');
    const tests: ReportTest[] = [];
    for (const run of all ? device.tests : [selectedTest]) {
      const [detail, signals] = await Promise.all([getDetail(run.id), getSignals(run.id)]);
      tests.push({ run, detail, signals });
    }
    return { serialNumber: device.serial_number, deviceType: device.device_type_name,
      deviceTypeId: device.device_type, deviceRunId: device.id,
      batchId: batch.id, receivedAt: batch.created_at, recordedBy: batch.recorded_by_code, tests };
  };

  return (
    <PageContainer className="serial-detail-page" title={false} breadcrumbRender={false}>
      <div className="batch-detail-content batch-detail-serial-page">
        <header className="serial-detail-toolbar">
          <div className="serial-detail-heading"><h1>Serial details</h1>
            <Breadcrumb className="batch-detail-breadcrumb" items={[
              { title: <Link to="/serial-batches">Serial batches</Link> },
              { title: batchId ? <Link to={`/serial-batches/${batchId}`}>Batch details</Link> : 'Batch details' },
              ...(device ? [{ title: device.serial_number }] : []),
              ...(selectedTest ? [{ title: selectedTest.test_name }] : []),
            ]} />
          </div>
          <div className="serial-detail-tools">
            {selectedTest && <SerialActions key={selectedTest.id} testName={selectedTest.test_name}
              disabled={!canViewResults} loadReport={loadReport} />}
            {batchId && <Link className="serial-back-link" to={`/serial-batches/${batchId}`}>Back to batch</Link>}
          </div>
        </header>
        {batchLoading && <div className="batch-detail-loading"><Spin size="large" /></div>}
        {batchError && <Alert type="error" showIcon title={batchError} />}
        {batch && device && <>
          <section className="batch-detail-summary" aria-label="Serial overview">
            <div className="batch-detail-summary-main">
              <span className="batch-detail-summary-icon"><NumberOutlined /></span>
              <div>
                <span className="batch-detail-eyebrow">SERIAL NUMBER</span>
                <h2>{device.serial_number}</h2>
                <p>Tests and results recorded for this serial.</p>
              </div>
            </div>
            <div className="batch-detail-metrics">
              <div><span>Device type</span><strong>{device.device_type_name}</strong></div>
              <div><span>Tests</span><strong>{device.tests.length}</strong></div>
              <div><span>Received at</span><strong>{formatTehranDateTime(batch.created_at)}</strong></div>
            </div>
          </section>

          <div className="batch-detail-main">
            <section className="batch-detail-panel batch-detail-tests-panel" aria-label={`Tests for ${device.serial_number}`}>
              <div className="batch-detail-panel-header">
                <div><h2>Tests</h2><p>Select a test to view results.</p></div>
                <span className="batch-detail-count">{device.tests.length}</span>
              </div>
              <div className="batch-detail-test-list">
                {device.tests.map((run) => <button key={run.id} type="button"
                  className={`batch-detail-test-item${run.id === selectedTestId ? ' is-selected' : ''}`}
                  aria-pressed={run.id === selectedTestId} aria-label={run.test_name}
                  onClick={() => setSelectedTestId(run.id)}>
                  <span className="batch-detail-test-icon"><ExperimentOutlined /></span>
                  <span className="batch-detail-test-copy">
                    <strong>{run.test_name}</strong>
                    <small><ClockCircleOutlined /> {formatTehranDateTime(run.executed_at)}</small>
                  </span>
                  <RightOutlined className="batch-detail-chevron" aria-hidden="true" />
                </button>)}
                {!device.tests.length && <Empty description="No tests for this serial number" />}
              </div>
            </section>

            {selectedTest && <TestResults key={selectedTest.id} runId={selectedTest.id}
              testName={selectedTest.test_name} canView={canViewResults} getDetail={getDetail} />}
          </div>
        </>}
      </div>
    </PageContainer>
  );
}
