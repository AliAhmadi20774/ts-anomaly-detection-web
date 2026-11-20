import type { ProColumns } from '@ant-design/pro-components';
import { PageContainer, ProTable } from '@ant-design/pro-components';
import { Link } from '@umijs/max';
import { Alert } from 'antd';
import { useState } from 'react';
import { type MeasurementBatch, measurementBatches } from '@/services/measurementBatches';

export default function SerialBatchesPage() {
  const [loadError, setLoadError] = useState<string>();

  const columns: ProColumns<MeasurementBatch>[] = [
    { title: 'Received at', dataIndex: 'created_at', valueType: 'dateTime', search: false,
      render: (dom, batch) => <Link to={`/serial-batches/${batch.id}`}>{dom}</Link> },
    {
      title: 'Device type', key: 'device_type', search: false,
      render: (_, batch) => [...new Set(batch.devices.map((device) => device.device_type_name))].join(', ') || '—',
    },
    { title: 'Serials', key: 'serials', search: false, render: (_, batch) => batch.devices.length },
    { title: 'Recorded by', dataIndex: 'recorded_by_code', search: false },
  ];

  return (
    <PageContainer title="Serial batches" subTitle="Select a batch to browse its serial numbers and tests.">
      {loadError && <Alert type="error" showIcon title={loadError} style={{ marginBottom: 16 }} />}
      <ProTable<MeasurementBatch>
        rowKey="id" columns={columns} search={false}
        options={{ density: false, fullScreen: false, setting: false }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: [20, 50, 100] }}
        request={async (params) => {
          setLoadError(undefined);
          const result = await measurementBatches.list({ page: params.current, page_size: params.pageSize });
          return { data: result.results, success: true, total: result.count };
        }}
        onRequestError={(error) => setLoadError(error.message)}
      />
    </PageContainer>
  );
}
