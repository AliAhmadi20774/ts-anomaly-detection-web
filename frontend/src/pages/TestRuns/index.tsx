import { PlusOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import {
  ModalForm, PageContainer, ProFormDateTimePicker, ProFormSelect, ProFormText,
  ProFormTextArea, ProTable,
} from '@ant-design/pro-components';
import { useModel } from '@umijs/max';
import { Alert, App, Button, Popconfirm, Space } from 'antd';
import dayjs from 'dayjs';
import { useRef, useState } from 'react';
import { hasPermission } from '@/services/auth';
import { testOptions } from '@/services/definitions';
import { type TestRun, type TestRunInput, testRuns } from '@/services/testRuns';

export default function TestRunsPage() {
  const { initialState } = useModel('@@initialState');
  const { message } = App.useApp();
  const actionRef = useRef<ActionType | undefined>(undefined);
  const [editing, setEditing] = useState<TestRun>();
  const [open, setOpen] = useState(false);
  const [loadError, setLoadError] = useState<string>();
  const user = initialState?.currentUser;
  const canViewTests = hasPermission(user, 'devices.view_testdefinition');
  const canAdd = hasPermission(user, 'devices.add_testrun') && canViewTests;
  const canChange = hasPermission(user, 'devices.change_testrun');
  const canDelete = hasPermission(user, 'devices.delete_testrun');

  const remove = async (record: TestRun) => {
    try {
      await testRuns.remove(record.id);
      message.success('Test run deleted.');
      void actionRef.current?.reload();
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Delete failed.');
    }
  };

  const columns: ProColumns<TestRun>[] = [
    { title: 'Serial number', dataIndex: 'device_serial_number', ellipsis: true },
    { title: 'Device type', dataIndex: 'device_type_name', search: false },
    { title: 'Test', dataIndex: 'test_name', search: false },
    {
      title: 'Test', dataIndex: 'test', valueType: 'select', hideInTable: true,
      search: canViewTests ? undefined : false,
      request: ({ keyWords }) => testOptions(keyWords),
      fieldProps: { showSearch: true, filterOption: false },
    },
    { title: 'Executed at', dataIndex: 'executed_at', valueType: 'dateTime', search: false },
    { title: 'Sample rate (Hz)', dataIndex: 'sample_rate_hz', search: false },
    { title: 'Recorded by', dataIndex: 'recorded_by_code', search: false },
    {
      title: 'Actions', valueType: 'option', width: 160,
      hideInTable: !canChange && !canDelete,
      render: (_, record) => (
        <Space>
          {canChange && <Button type="link" size="small" onClick={() => {
            setEditing(record); setOpen(true);
          }}>Edit</Button>}
          {canDelete && <Popconfirm title="Delete test run?"
            onConfirm={() => remove(record)} okText="Delete" okButtonProps={{ danger: true }}
          ><Button type="link" size="small" danger>Delete</Button></Popconfirm>}
        </Space>
      ),
    },
  ];

  return (
    <PageContainer title="Test runs" subTitle="Record actual test executions on devices by serial number.">
      {loadError && <Alert type="error" showIcon title={loadError} style={{ marginBottom: 16 }} />}
      <ProTable<TestRun>
        actionRef={actionRef} columns={columns} rowKey="id"
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        options={{ density: false, fullScreen: false, setting: false }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: [20, 50, 100] }}
        scroll={{ x: 1100 }}
        request={async (params) => {
          setLoadError(undefined);
          const result = await testRuns.list({
            page: params.current, page_size: params.pageSize,
            search: params.device_serial_number, test: params.test,
          });
          return { data: result.results, success: true, total: result.count };
        }}
        onRequestError={(error) => setLoadError(error.message)}
        toolBarRender={() => canAdd ? [
          <Button key="create" type="primary" icon={<PlusOutlined />} onClick={() => {
            setEditing(undefined); setOpen(true);
          }}>New test run</Button>,
        ] : []}
      />
      {open && <ModalForm<TestRunInput>
        name="test-run-form"
        title={editing ? 'Edit test run' : 'New test run'} open={open} onOpenChange={setOpen}
        initialValues={editing ? { ...editing, executed_at: dayjs(editing.executed_at) }
          : { executed_at: dayjs(), notes: '' }}
        dateFormatter={false}
        modalProps={{ destroyOnHidden: true }}
        submitter={{ searchConfig: { submitText: 'Save', resetText: 'Cancel' } }}
        onFinish={async (values) => {
          try {
            const data = { ...values, executed_at: dayjs(values.executed_at).toISOString() };
            if (editing) await testRuns.update(editing.id, data);
            else await testRuns.create(data);
            message.success('Test run saved.');
            void actionRef.current?.reload();
            return true;
          } catch (error) {
            message.error(error instanceof Error ? error.message : 'Save failed.');
            return false;
          }
        }}
      >
        <ProFormSelect name="test" label="Test" debounceTime={300}
          disabled={Boolean(editing)}
          rules={[{ required: true, message: 'Select a test.' }]}
          fieldProps={{ showSearch: true, filterOption: false, 'aria-label': 'Test' }}
          request={({ keyWords }) => {
            const selected = editing ? {
              value: editing.test, label: `${editing.device_type_name} / ${editing.test_name}`,
            } : undefined;
            return canViewTests ? testOptions(keyWords, selected)
              : Promise.resolve(selected ? [selected] : []);
          }}
        />
        <ProFormText name="device_serial_number" label="Serial number"
          fieldProps={{ maxLength: 128, 'aria-label': 'Serial number' }}
          rules={[{ required: true, whitespace: true, message: 'Enter a device serial number.' }]}
        />
        <ProFormDateTimePicker name="executed_at" label="Executed at"
          rules={[{ required: true, message: 'Enter the execution date and time.' }]}
        />
        <ProFormTextArea name="notes" label="Notes" />
        {editing && <Alert type="info" showIcon title={
          `Recorded by ${editing.recorded_by_code} · Sample rate: ${editing.sample_rate_hz} Hz`
        } />}
      </ModalForm>}
    </PageContainer>
  );
}
