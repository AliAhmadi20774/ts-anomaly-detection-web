import { ClockCircleOutlined, ExperimentOutlined, NumberOutlined, RightOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { Link, useModel, useParams } from '@umijs/max';
import { Alert, Breadcrumb, Empty, Spin } from 'antd';
import { useEffect, useState } from 'react';
import { hasPermission } from '@/services/auth';
import { type MeasurementBatch, measurementBatches } from '@/services/measurementBatches';
import { formatTehranDateTime } from '@/utils/dateTime';
import TestResults from './TestResults';
import '../SerialBatchDetail/index.css';

export default function SerialDetailPage() {
  const { batchId, deviceId } = useParams<{ batchId: string; deviceId: string }>();
  const { initialState } = useModel('@@initialState');
  const canViewResults = hasPermission(initialState?.currentUser, 'devices.view_testrun');
  const [batch, setBatch] = useState<MeasurementBatch>();
  const [batchLoading, setBatchLoading] = useState(true);
  const [batchError, setBatchError] = useState<string>();
  const [selectedTestId, setSelectedTestId] = useState<string>();

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

  return (
    <PageContainer className="serial-detail-page" title="Serial details" breadcrumbRender={false}
      extra={batchId && <Link to={`/serial-batches/${batchId}`}>Back to batch</Link>}>
      <div className="batch-detail-content batch-detail-serial-page">
        <Breadcrumb className="batch-detail-breadcrumb" items={[
          { title: <Link to="/serial-batches">Serial batches</Link> },
          { title: batchId ? <Link to={`/serial-batches/${batchId}`}>Batch details</Link> : 'Batch details' },
          ...(device ? [{ title: device.serial_number }] : []),
          ...(selectedTest ? [{ title: selectedTest.test_name }] : []),
        ]} />
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
              testName={selectedTest.test_name} canView={canViewResults} />}
          </div>
        </>}
      </div>
    </PageContainer>
  );
}
