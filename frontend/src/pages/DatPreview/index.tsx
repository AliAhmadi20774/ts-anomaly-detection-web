import { InboxOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import {
  Alert, Button, Card, Collapse, Descriptions, List, Select, Space, Statistic,
  Table, Tag, Typography, Upload,
} from 'antd';
import type { TableColumnsType, UploadFile } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { deviceOptions, type SelectOption } from '@/services/definitions';
import { type DatDevice, type DatFilePreview, type DatImportResult, type DatPreview, type DatTest, importDatFiles, previewDatFiles } from '@/services/datPreview';
import { formatTehranDateTime } from '@/utils/dateTime';

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
  const [deviceType, setDeviceType] = useState<string>();
  const [deviceChoices, setDeviceChoices] = useState<SelectOption[]>([]);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [preview, setPreview] = useState<DatPreview>();
  const [importResult, setImportResult] = useState<DatImportResult>();
  const [error, setError] = useState<string>();
  const [operation, setOperation] = useState<'preview' | 'import' | null>(null);
  const busy = operation !== null;
  const importing = operation === 'import';
  const requestRef = useRef<AbortController | undefined>(undefined);
  useEffect(() => () => requestRef.current?.abort(), []);
  useEffect(() => {
    let active = true;
    setLoadingDevices(true);
    deviceOptions().then((choices) => { if (active) setDeviceChoices(choices); })
      .catch((failure) => { if (active) setError(failure instanceof Error ? failure.message : 'Unable to load device types.'); })
      .finally(() => { if (active) setLoadingDevices(false); });
    return () => { active = false; };
  }, []);

  const searchDevices = async (search: string) => {
    setLoadingDevices(true);
    try {
      const selected = deviceChoices.find((choice) => choice.value === deviceType);
      setDeviceChoices(await deviceOptions(search, selected));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Unable to load device types.');
    } finally {
      setLoadingDevices(false);
    }
  };

  const replaceFiles = (selected: UploadFile[]) => {
    if (!deviceType || busy || !selected.length) return;
    setFiles(selected);
    setPreview(undefined);
    setImportResult(undefined);
    setError(undefined);
  };

  const removeFile = (uid: string) => {
    setFiles((previous) => previous.filter((file) => file.uid !== uid));
    setPreview(undefined);
    setImportResult(undefined);
    setError(undefined);
  };

  const clearSelection = () => {
    setFiles([]);
    setPreview(undefined);
    setImportResult(undefined);
    setError(undefined);
  };

  const fileError = files.length > 100 ? 'Select no more than 100 files.'
    : files.some((file) => !file.name.toLowerCase().endsWith('.dat')) ? 'Select DAT files only.'
    : files.some((file) => (file.size ?? 0) > 32 * 1024 * 1024) ? 'Each file must be 32 MiB or smaller.'
    : files.reduce((total, file) => total + (file.size ?? 0), 0) > 128 * 1024 * 1024 ? 'The selection must be 128 MiB or smaller.'
    : undefined;

  const handlePreview = async () => {
    const controller = new AbortController();
    requestRef.current = controller;
    setOperation('preview');
    setError(undefined);
    setPreview(undefined);
    setImportResult(undefined);
    try {
      const selected = files.flatMap((file) => file.originFileObj ? [file.originFileObj] : []);
      const result = await previewDatFiles(selected, deviceType!, controller.signal);
      if (!controller.signal.aborted) setPreview(result);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Preview failed.');
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = undefined;
        setOperation(null);
      }
    }
  };

  const readyCurrentFiles = preview?.files.flatMap((item) => {
    const file = files[item.index]?.originFileObj;
    return item.status === 'ready' && item.format === 'current' && file ? [file] : [];
  }) ?? [];

  const handleImport = async () => {
    const controller = new AbortController();
    requestRef.current = controller;
    setOperation('import');
    setError(undefined);
    try {
      const result = await importDatFiles(readyCurrentFiles, deviceType!, controller.signal);
      if (!controller.signal.aborted) {
        setImportResult(result);
        if (result.summary.imported > 0) {
          setFiles([]);
          setPreview(undefined);
        }
      }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Import failed.');
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = undefined;
        setOperation(null);
      }
    }
  };

  const columns: TableColumnsType<DatFilePreview> = [
    { title: 'File', dataIndex: 'name', ellipsis: true },
    { title: 'Size', dataIndex: 'size', render: (bytes: number) => `${(bytes / 1024).toFixed(1)} KiB` },
    { title: 'Format', dataIndex: 'format', render: (value?: string) => value === 'legacy' ? 'Old format (preview only)' : value === 'current' ? 'Supported format' : '—' },
    { title: 'Status', dataIndex: 'status', render: (value: DatFilePreview['status']) => (
      <Tag color={{ ready: 'success', warning: 'warning', error: 'error' }[value]}>{value}</Tag>
    ) },
    { title: 'Details', render: (_, record) => record.error || `${record.devices?.length || 0} device entries` },
  ];

  return (
    <PageContainer title="DAT file preview" subTitle="Select a batch of DAT files and inspect their contents before importing.">
      <Space orientation="vertical" size="large" style={{ width: '100%' }}>
        <Alert type="info" showIcon title="Select a device type, then preview and import DAT files"
          description="The DAT format is detected automatically. Older files can be previewed but cannot be imported. Supported files also need complete test metadata."
        />
        <Card title="New DAT batch">
          <Space orientation="vertical" style={{ width: '100%', marginBottom: 16 }}>
            <Typography.Text>Select the device type for these DAT files</Typography.Text>
            <Select aria-label="Device type" placeholder="Select device type" value={deviceType}
              showSearch filterOption={false} options={deviceChoices} loading={loadingDevices}
              onSearch={searchDevices} onFocus={() => searchDevices('')} disabled={busy}
              onChange={(value: string) => { setDeviceType(value); clearSelection(); }}
              style={{ width: '100%', maxWidth: 400 }}
            />
          </Space>
          <Upload.Dragger multiple accept=".dat" disabled={busy || !deviceType} fileList={files}
            beforeUpload={(file, selection) => {
              if (file === selection[0]) replaceFiles(selection.map((item, index) => ({
                uid: String(index), name: item.name, size: item.size,
                type: item.type, originFileObj: item,
              })));
              return Upload.LIST_IGNORE;
            }}
            onRemove={(file) => { removeFile(file.uid); return true; }}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p>{deviceType ? 'Choose DAT files or drop them here' : 'Select a device type first'}</p>
            <p>Each new choice replaces the previous selection. Select multiple files together for one batch.</p>
          </Upload.Dragger>
          {files.length > 0 && <Button disabled={busy} onClick={clearSelection} style={{ marginTop: 16 }}>Clear selection</Button>}
          {fileError && <Alert type="warning" title={fileError} style={{ marginTop: 16 }} />}
          <Space wrap style={{ marginTop: 16 }}>
            <Button type="primary" loading={busy && !importing} disabled={!deviceType || !files.length || Boolean(fileError) || busy} onClick={handlePreview}>Preview files</Button>
            <Button loading={importing} disabled={busy || !deviceType || !readyCurrentFiles.length} onClick={handleImport}>
              Import {readyCurrentFiles.length} ready file{readyCurrentFiles.length === 1 ? '' : 's'}
            </Button>
            {busy && !importing && <Button onClick={() => requestRef.current?.abort()}>Cancel preview</Button>}
            <Typography.Text>{files.length} file{files.length === 1 ? '' : 's'} selected</Typography.Text>
          </Space>
        </Card>
        {error && <Alert type="error" showIcon title={error} />}
        {importResult && <Alert type={importResult.summary.errors || importResult.summary.skipped ? 'warning' : 'success'} showIcon
          title={`Imported ${importResult.summary.imported} files and ${importResult.summary.test_runs} test runs`}
          description={<List size="small" dataSource={importResult.files}
            renderItem={(item) => <List.Item>{item.name}: {item.status}
              {item.errors?.length ? ` — ${item.errors.join('; ')}` : ''}</List.Item>}
          />}
        />}
        {importResult?.batch && <Card title="Imported serial batch"
          extra={`Received ${formatTehranDateTime(importResult.batch.created_at)}`}>
          <Collapse items={importResult.batch.devices.map((device) => ({
            key: device.id,
            label: `${device.device_type} / ${device.serial_number} · ${device.tests.length} tests`,
            children: <List size="small" dataSource={device.tests}
              renderItem={(test) => <List.Item>{test.name} · {formatTehranDateTime(test.executed_at)}</List.Item>}
            />,
          }))} />
        </Card>}
        {preview && <>
          <Card title="Selection summary" extra={`Previewed by personnel code ${preview.previewed_by_code}`}>
            <Space wrap size="large">
              <Statistic title="Readable files" value={preview.summary.readable} />
              <Statistic title="Errors" value={preview.summary.errors} />
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
