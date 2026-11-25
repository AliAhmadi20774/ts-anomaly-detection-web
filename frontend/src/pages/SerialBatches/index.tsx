import type { ProColumns } from '@ant-design/pro-components';
import { PageContainer, ProFormSelect, ProTable } from '@ant-design/pro-components';
import { Link, useModel } from '@umijs/max';
import { Alert, Input, Space } from 'antd';
import { useState } from 'react';
import { type MeasurementBatch, measurementBatches } from '@/services/measurementBatches';
import { formatTehranDateTime } from '@/utils/dateTime';
import { hasPermission } from '@/services/auth';
import { deviceOptions } from '@/services/definitions';

export default function SerialBatchesPage() {
  const [loadError, setLoadError] = useState<string>();
  const [deviceType, setDeviceType] = useState<string>();
  const [serialSearch, setSerialSearch] = useState('');
  const [current, setCurrent] = useState(1);
  const { initialState } = useModel('@@initialState');
  const canViewDevices = hasPermission(initialState?.currentUser, 'devices.view_devicetype');

  const columns: ProColumns<MeasurementBatch>[] = [
    { title: 'Received at', dataIndex: 'created_at', search: false,
      render: (_, batch) => <Link to={`/serial-batches/${batch.id}`}>{formatTehranDateTime(batch.created_at)}</Link> },
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
        params={{ device_type: deviceType, search: serialSearch }}
        options={{ density: false, fullScreen: false, setting: false }}
        pagination={{ current, onChange: setCurrent, defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: [20, 50, 100] }}
        toolBarRender={() => [<Space key="filters" wrap>
          {canViewDevices && <ProFormSelect noStyle
          placeholder="All device types" debounceTime={300} request={({ keyWords }) => deviceOptions(keyWords)}
          fieldProps={{ 'aria-label': 'Filter by device type', style: { width: 220 }, allowClear: true,
            showSearch: true, filterOption: false, value: deviceType,
            onChange: (value: string | undefined) => { setCurrent(1); setDeviceType(value); } }}
          />}
          <Input.Search aria-label="Search serial number" placeholder="Search serial number" allowClear
            style={{ width: 220 }} onSearch={(value) => { setCurrent(1); setSerialSearch(value.trim()); }} />
        </Space>]}
        request={async (params) => {
          setLoadError(undefined);
          const result = await measurementBatches.list({ page: params.current, page_size: params.pageSize,
            device_type: params.device_type, search: params.search || undefined });
          return { data: result.results, success: true, total: result.count };
        }}
        onRequestError={(error) => setLoadError(error.message)}
      />
    </PageContainer>
  );
}
