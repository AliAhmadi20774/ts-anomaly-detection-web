import { DatabaseOutlined, RightOutlined, SearchOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { Link, useParams } from '@umijs/max';
import { Alert, Breadcrumb, Empty, Input, Spin } from 'antd';
import { useEffect, useState } from 'react';
import { type MeasurementBatch, measurementBatches } from '@/services/measurementBatches';
import { formatTehranDateTime } from '@/utils/dateTime';
import './index.css';

export default function SerialBatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const [batch, setBatch] = useState<MeasurementBatch>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [serialSearch, setSerialSearch] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(undefined);
    setBatch(undefined);
    setSerialSearch('');
    if (!batchId) {
      setError('Batch was not specified.');
      setLoading(false);
      return () => { active = false; };
    }
    measurementBatches.detail(batchId).then((result) => {
      if (active) setBatch(result);
    }).catch((failure) => {
      if (active) setError(failure instanceof Error ? failure.message : 'Could not load this batch.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [batchId]);

  const visibleDevices = batch?.devices.filter((device) =>
    `${device.device_type_name} ${device.serial_number}`.toLowerCase().includes(serialSearch.toLowerCase().trim()),
  ) ?? [];

  return (
    <PageContainer title="Batch details" breadcrumbRender={false} extra={<Link to="/serial-batches">Back to batches</Link>}>
      <div className="batch-detail-content">
        <Breadcrumb className="batch-detail-breadcrumb" items={[
          { title: <Link to="/serial-batches">Serial batches</Link> },
          { title: 'Batch details' },
        ]} />
        {loading && <div className="batch-detail-loading"><Spin size="large" /></div>}
        {error && <Alert type="error" showIcon title={error} />}
        {batch && <>
          <section className="batch-detail-summary" aria-label="Batch overview">
            <div className="batch-detail-summary-main">
              <span className="batch-detail-summary-icon"><DatabaseOutlined /></span>
              <div>
                <span className="batch-detail-eyebrow">DATA IMPORT</span>
                <h2>Received {formatTehranDateTime(batch.created_at)}</h2>
                <p>Select a serial number to inspect its measurements.</p>
              </div>
            </div>
            <div className="batch-detail-metrics">
              <div><span>Device type</span><strong>{[...new Set(batch.devices.map((device) => device.device_type_name))].join(', ') || '—'}</strong></div>
              <div><span>Serial numbers</span><strong>{batch.devices.length}</strong></div>
              <div><span>Recorded by</span><strong>{batch.recorded_by_code}</strong></div>
            </div>
          </section>

          <section className="batch-detail-panel" aria-label="Serial numbers">
            <div className="batch-detail-panel-header">
              <div><h2>Serial numbers</h2><p>Each serial has its own tests and signals.</p></div>
              <span className="batch-detail-count">{batch.devices.length}</span>
            </div>
            {batch.devices.length > 0 && <div className="batch-detail-search">
              <Input aria-label="Find a serial" placeholder="Find a serial" prefix={<SearchOutlined />}
                value={serialSearch} onChange={(event) => setSerialSearch(event.target.value)} allowClear />
            </div>}
            <div className="batch-detail-serial-grid">
              {visibleDevices.map((device) => <Link key={device.id}
                className="batch-detail-serial-item"
                aria-label={`${device.device_type_name} / ${device.serial_number} · ${device.tests.length} tests`}
                to={`/serial-batches/${batchId}/serials/${device.id}`}>
                <span className="batch-detail-serial-mark" aria-hidden="true">{device.serial_number.slice(0, 2).toUpperCase()}</span>
                <span className="batch-detail-serial-copy">
                  <strong>{device.serial_number}</strong>
                  <small>{device.device_type_name} · {device.tests.length} tests</small>
                </span>
                <RightOutlined className="batch-detail-chevron" aria-hidden="true" />
              </Link>)}
              {!batch.devices.length && <Empty description="No serials in this batch" />}
              {!!batch.devices.length && !visibleDevices.length && <Empty description="No matching serial numbers" />}
            </div>
          </section>
        </>}
      </div>
    </PageContainer>
  );
}
