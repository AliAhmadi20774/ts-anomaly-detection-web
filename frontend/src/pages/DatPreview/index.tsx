import { InboxOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import {
  Alert, Button, Card, Collapse, Descriptions, List, Select, Space, Statistic,
  Table, Tag, Typography, Upload,
} from 'antd';
import type { TableColumnsType, UploadFile } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { type DatDevice, type DatFilePreview, type DatFormat, type DatPreview, type DatTest, previewDatFiles } from '@/services/datPreview';

function TestDetails({ test }: { test: DatTest }) {
  const table = test.flat_result_table;
  return (
    <Space orientation="vertical" style={{ width: '100%' }}>
      <Descriptions size="small" column={{ xs: 1, sm: 2 }} items={[
        { key: 'operator', label: 'Operator from DAT', children: test.operator_name || 'Not provided' },
        { key: 'date', label: 'Date from DAT', children: test.date_raw || 'Not provided' },
        { key: 'rate', label: 'Sample rate from definition', children: test.sample_rate_hz == null ? 'Not matched' : `${test.sample_rate_hz} Hz` },
      ]} />
      <Table rowKey={(_, index) => String(index)} size="small" pagination={false} dataSource={test.signals} scroll={{ x: 650 }} columns={[
        { title: 'Signal', dataIndex: 'name' },
        { title: 'Samples', dataIndex: 'sample_count' },
        { title: 'Invalid values', dataIndex: 'non_finite_count' },
        { title: 'First 5 values', dataIndex: 'sample', render: (values: (number | null)[]) => values.map((value) => value == null ? 'Invalid' : String(value)).join(', ') },
      ]} />
      {table && <Card size="small" title={`Flat results · ${table.row_count} rows`}>
        {!table.valid_shape && <Alert type="warning" title="Inconsistent table rows or columns" />}
        <Table size="small" pagination={false} rowKey={(_, index) => String(index)} scroll={{ x: 'max-content' }}
          dataSource={table.sample_rows} locale={{ emptyText: 'No rows' }}
          columns={table.columns.map((name, index) => ({ title: name, key: String(index), render: (_, row: string[]) => row[index] }))}
        />
        <Typography.Text type="secondary">Showing up to 5 rows.</Typography.Text>
      </Card>}
    </Space>
  );
}

function DeviceDetails({ device }: { device: DatDevice }) {
  return (
    <Card size="small" title={`${device.device_series} / ${device.serial_number}`}>
      {device.tests.length ? <Collapse items={device.tests.map((test, index) => ({
        key: String(index), label: `${test.name} · ${test.signals.length} signals`, children: <TestDetails test={test} />,
      }))} /> : <Typography.Text type="secondary">No tests in this device entry.</Typography.Text>}
    </Card>
  );
}

export default function DatPreviewPage() {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [fileFormat, setFileFormat] = useState<DatFormat>('auto');
  const [preview, setPreview] = useState<DatPreview>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const requestRef = useRef<AbortController | undefined>(undefined);
  useEffect(() => () => requestRef.current?.abort(), []);

  const handlePreview = async () => {
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    setError(undefined);
    setPreview(undefined);
    try {
      const selected = files.flatMap((file) => file.originFileObj ? [file.originFileObj] : []);
      const result = await previewDatFiles(selected, fileFormat, controller.signal);
      if (!controller.signal.aborted) setPreview(result);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Preview failed.');
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = undefined;
        setBusy(false);
      }
    }
  };

  const columns: TableColumnsType<DatFilePreview> = [
    { title: 'File', dataIndex: 'name', ellipsis: true },
    { title: 'Size', dataIndex: 'size', render: (bytes: number) => `${(bytes / 1024).toFixed(1)} KiB` },
    { title: 'Format', dataIndex: 'format', render: (value?: string) => value || '—' },
    { title: 'Status', dataIndex: 'status', render: (value: DatFilePreview['status']) => (
      <Tag color={{ ready: 'success', warning: 'warning', duplicate: 'default', error: 'error' }[value]}>{value}</Tag>
    ) },
    { title: 'Details', render: (_, record) => record.error || (record.duplicate_of ? `Same content as ${record.duplicate_of}` : `${record.devices?.length || 0} device entries`) },
  ];

  return (
    <PageContainer title="DAT file preview" subTitle="Select a batch of DAT files and inspect their contents before importing.">
      <Space orientation="vertical" size="large" style={{ width: '100%' }}>
        <Alert type="info" showIcon title="Preview only · no records are saved yet"
          description="Operator and date are read from each test in the file. Dates are shown exactly as supplied. Missing metadata is shown as Not provided."
        />
        <Card title="Select files">
          <Upload.Dragger multiple accept=".dat" beforeUpload={() => false} fileList={files} disabled={busy}
            onChange={({ fileList }) => { setFiles(fileList); setPreview(undefined); setError(undefined); }}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p>Choose DAT files or drop them here</p>
            <p>Up to 100 files, 32 MiB per file and 128 MiB per selection.</p>
          </Upload.Dragger>
          {files.length > 100 && <Alert type="warning" title="Select no more than 100 files." style={{ marginTop: 16 }} />}
          <Space wrap style={{ marginTop: 16 }}>
            <Select<DatFormat> aria-label="DAT format" value={fileFormat} disabled={busy}
              onChange={(value) => { setFileFormat(value); setPreview(undefined); }} style={{ minWidth: 160 }}
              options={[{ value: 'auto', label: 'Detect format' }, { value: 'current', label: 'Current format' }, { value: 'legacy', label: 'Legacy format' }]}
            />
            <Button type="primary" loading={busy} disabled={!files.length || files.length > 100} onClick={handlePreview}>Preview files</Button>
            {busy && <Button onClick={() => requestRef.current?.abort()}>Cancel</Button>}
            <Typography.Text>{files.length} files selected</Typography.Text>
          </Space>
        </Card>
        {error && <Alert type="error" showIcon title={error} />}
        {preview && <>
          <Card title="Selection summary" extra={`Previewed by personnel code ${preview.previewed_by_code}`}>
            <Space wrap size="large">
              <Statistic title="Readable files" value={preview.summary.readable} />
              <Statistic title="Errors" value={preview.summary.errors} />
              <Statistic title="Duplicates in selection" value={preview.summary.duplicates} />
              <Statistic title="Devices" value={preview.summary.devices} />
              <Statistic title="Tests" value={preview.summary.tests} />
              <Statistic title="Signals" value={preview.summary.signals} />
            </Space>
          </Card>
          <Table<DatFilePreview> columns={columns} dataSource={preview.files} rowKey="index" pagination={{ defaultPageSize: 10 }} scroll={{ x: 850 }}
            expandable={{ rowExpandable: (record) => Boolean(record.devices?.length), expandedRowRender: (record) => (
              <Space orientation="vertical" style={{ width: '100%' }}>
                {!!record.warnings?.length && <Alert type="warning" showIcon title="Review before importing" description={
                  <List size="small" dataSource={record.warnings} renderItem={(warning) => <List.Item>{warning}</List.Item>} />
                } />}
                {record.devices?.map((device, index) => <DeviceDetails key={index} device={device} />)}
              </Space>
            ) }}
          />
        </>}
      </Space>
    </PageContainer>
  );
}
