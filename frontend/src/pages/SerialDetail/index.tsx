import { ClockCircleOutlined, ExperimentOutlined, NumberOutlined, RightOutlined } from '@ant-design/icons';
import { Line } from '@ant-design/plots';
import { PageContainer } from '@ant-design/pro-components';
import { Link, useModel, useParams } from '@umijs/max';
import { Alert, Breadcrumb, Empty, Select, Spin, Tag, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { hasPermission } from '@/services/auth';
import { type MeasurementBatch, measurementBatches } from '@/services/measurementBatches';
import { type SignalTraceData, type SignalTraceSummary, testRuns } from '@/services/testRuns';
import '../SerialBatchDetail/index.css';

export default function SerialDetailPage() {
  const { batchId, deviceId } = useParams<{ batchId: string; deviceId: string }>();
  const { initialState } = useModel('@@initialState');
  const canViewSignals = hasPermission(initialState?.currentUser, 'devices.view_testrun');
  const [batch, setBatch] = useState<MeasurementBatch>();
  const [batchLoading, setBatchLoading] = useState(true);
  const [batchError, setBatchError] = useState<string>();
  const [selectedTestId, setSelectedTestId] = useState<string>();
  const [signalList, setSignalList] = useState<SignalTraceSummary[]>([]);
  const [selectedSignalId, setSelectedSignalId] = useState<string>();
  const [selectedSignal, setSelectedSignal] = useState<SignalTraceData>();
  const [signalLoading, setSignalLoading] = useState(false);
  const [samplesLoading, setSamplesLoading] = useState(false);
  const [signalError, setSignalError] = useState<string>();

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

  useEffect(() => {
    let active = true;
    setSignalList([]);
    setSelectedSignalId(undefined);
    setSelectedSignal(undefined);
    setSignalError(undefined);
    if (!selectedTest || !canViewSignals) return () => { active = false; };
    setSignalLoading(true);
    testRuns.signals(selectedTest.id).then((signals) => {
      if (active) {
        setSignalList(signals);
        setSelectedSignalId(signals[0]?.id);
      }
    }).catch((error) => {
      if (active) setSignalError(error instanceof Error ? error.message : 'Could not load signals.');
    }).finally(() => {
      if (active) setSignalLoading(false);
    });
    return () => { active = false; };
  }, [selectedTest?.id, canViewSignals]);

  useEffect(() => {
    let active = true;
    setSelectedSignal(undefined);
    if (!selectedTest || !selectedSignalId) return () => { active = false; };
    setSamplesLoading(true);
    setSignalError(undefined);
    testRuns.signalSamples(selectedTest.id, selectedSignalId).then((signal) => {
      if (active) setSelectedSignal(signal);
    }).catch((error) => {
      if (active) setSignalError(error instanceof Error ? error.message : 'Could not load samples.');
    }).finally(() => {
      if (active) setSamplesLoading(false);
    });
    return () => { active = false; };
  }, [selectedTest?.id, selectedSignalId]);

  const chartData = selectedSignal ? (() => {
    const stride = Math.max(1, Math.ceil(selectedSignal.samples.length / 1000));
    const points = selectedSignal.samples.flatMap((value, index) => index % stride === 0 ? [{ sample: index, value }] : []);
    const last = selectedSignal.samples.length - 1;
    if (last >= 0 && last % stride !== 0) points.push({ sample: last, value: selectedSignal.samples[last] });
    return points;
  })() : [];

  return (
    <PageContainer title="Serial details" breadcrumbRender={false}
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
                <p>Tests and signal traces recorded for this serial.</p>
              </div>
            </div>
            <div className="batch-detail-metrics">
              <div><span>Device type</span><strong>{device.device_type_name}</strong></div>
              <div><span>Tests</span><strong>{device.tests.length}</strong></div>
              <div><span>Received at</span><strong>{new Date(batch.created_at).toLocaleString()}</strong></div>
            </div>
          </section>

          <div className="batch-detail-main">
            <section className="batch-detail-panel" aria-label={`Tests for ${device.serial_number}`}>
              <div className="batch-detail-panel-header">
                <div><h2>Tests for {device.serial_number}</h2><p>Choose a test to inspect its signals.</p></div>
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
                    <small><ClockCircleOutlined /> {new Date(run.executed_at).toLocaleString()}</small>
                  </span>
                  <Tag variant="filled">{run.sample_rate_hz} Hz</Tag>
                  <RightOutlined className="batch-detail-chevron" aria-hidden="true" />
                </button>)}
                {!device.tests.length && <Empty description="No tests for this serial number" />}
              </div>
            </section>

            {selectedTest && <section className="batch-detail-panel" aria-label={`Signals for ${selectedTest.test_name}`}>
              <div className="batch-detail-panel-header">
                <div><span className="batch-detail-eyebrow">SELECTED TEST</span><h2>Signals for {selectedTest.test_name}</h2></div>
                {selectedSignal && <Tag color="blue" variant="filled">{selectedSignal.samples.length} samples</Tag>}
              </div>
              <div className="batch-detail-signal-body">
                {!canViewSignals ? <Typography.Text type="secondary">Signal access is unavailable for your account.</Typography.Text> : <>
                  {signalError && <Alert type="error" showIcon title={signalError} />}
                  {(signalLoading || samplesLoading) && <Spin />}
                  {!signalLoading && signalList.length === 0 && !signalError && <Empty description="No stored signals for this test" />}
                  {signalList.length > 0 && <>
                    <Select aria-label="Signal" className="batch-detail-signal-select" value={selectedSignalId}
                      options={signalList.map((signal) => ({ value: signal.id, label: `${signal.name} (${signal.sample_count} samples)` }))}
                      onChange={setSelectedSignalId} />
                    {selectedSignal && <div className="batch-detail-chart">
                      <Line data={chartData} xField="sample" yField="value" height={320} />
                    </div>}
                  </>}
                </>}
              </div>
            </section>}
          </div>
        </>}
      </div>
    </PageContainer>
  );
}
