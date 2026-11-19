import { PlusOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { ModalForm, PageContainer, ProFormSelect, ProFormDigit, ProFormText, ProTable } from '@ant-design/pro-components';
import { useModel } from '@umijs/max';
import { Alert, App, Button, Popconfirm, Space } from 'antd';
import { useRef, useState } from 'react';
import { hasPermission } from '@/services/auth';
import { type TestDefinition, type TestDefinitionInput, testDefinitions, deviceOptions } from '@/services/definitions';

export default function TestDefinitionsPage() {
  const { initialState } = useModel('@@initialState');
  const { message } = App.useApp();
  const actionRef = useRef<ActionType | undefined>(undefined);
  const [editing, setEditing] = useState<TestDefinition>();
  const [open, setOpen] = useState(false);
  const [loadError, setLoadError] = useState<string>();
  const user = initialState?.currentUser;
  const canViewParents = hasPermission(user, 'devices.view_devicetype');
  const canAdd = hasPermission(user, 'devices.add_testdefinition') && canViewParents;
  const canChange = hasPermission(user, 'devices.change_testdefinition');
  const canDelete = hasPermission(user, 'devices.delete_testdefinition');

  const remove = async (record: TestDefinition) => {
    try {
      await testDefinitions.remove(record.id);
      message.success('Test definition deleted.');
      void actionRef.current?.reload();
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Delete failed.');
    }
  };

  const columns: ProColumns<TestDefinition>[] = [
    { title: 'Name', dataIndex: 'name', ellipsis: true },
    { title: 'Device type', dataIndex: 'device_type_name', search: false },
    {
      title: 'Device type', dataIndex: 'device_type', valueType: 'select', hideInTable: true,
      search: canViewParents ? undefined : false, request: ({ keyWords }) => deviceOptions(keyWords),
      fieldProps: { showSearch: true, filterOption: false },
    },
    { title: 'Sample rate (Hz)', dataIndex: 'sample_rate_hz', search: false },
    {
      title: 'Actions', valueType: 'option', width: 160,
      hideInTable: !canChange && !canDelete,
      render: (_, record) => (
        <Space>
          {canChange && <Button type="link" size="small" onClick={() => {
            setEditing(record); setOpen(true);
          }}>Edit</Button>}
          {canDelete && <Popconfirm
            title="Delete test definition?"
            onConfirm={() => remove(record)} okText="Delete" okButtonProps={{ danger: true }}
          >
            <Button type="link" size="small" danger>Delete</Button>
          </Popconfirm>}
        </Space>
      ),
    },
  ];

  return (
    <PageContainer title="Test definitions" subTitle="Define tests and their sampling rates for each device type.">
      {loadError && <Alert type="error" showIcon title={loadError} style={{ marginBottom: 16 }} />}
      <ProTable<TestDefinition>
        actionRef={actionRef} columns={columns} rowKey="id"
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        options={{ density: false, fullScreen: false, setting: false }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: [20, 50, 100] }}
        scroll={{ x: 760 }}
        request={async (params) => {
          setLoadError(undefined);
          const result = await testDefinitions.list({
            page: params.current, page_size: params.pageSize, search: params.name, device_type: params.device_type,
          });
          return { data: result.results, success: true, total: result.count };
        }}
        onRequestError={(error) => setLoadError(error.message)}
        toolBarRender={() => canAdd ? [
          <Button key="create" type="primary" icon={<PlusOutlined />} onClick={() => {
            setEditing(undefined); setOpen(true);
          }}>New test definition</Button>,
        ] : []}
      />
      {open && <ModalForm<TestDefinitionInput>
        title={editing ? 'Edit test definition' : 'New test definition'}
        open={open} onOpenChange={setOpen} initialValues={editing}
        modalProps={{ destroyOnHidden: true }}
        submitter={{ searchConfig: { submitText: 'Save', resetText: 'Cancel' } }}
        onFinish={async (values) => {
          try {
            if (editing) await testDefinitions.update(editing.id, values);
            else await testDefinitions.create(values);
            message.success('Test definition saved.');
            void actionRef.current?.reload();
            return true;
          } catch (error) {
            message.error(error instanceof Error ? error.message : 'Save failed.');
            return false;
          }
        }}
      >
        <ProFormText name="name" label="Name" rules={[
          { required: true, whitespace: true, message: 'Enter a name.' },
        ]} />
        <ProFormSelect name="device_type" label="Device type" debounceTime={300}
          rules={[{ required: true, message: 'Select a device type.' }]}
          fieldProps={{ showSearch: true, filterOption: false, disabled: !canViewParents }}
          request={({ keyWords }) => {
            const selected = editing
              ? { value: editing.device_type, label: editing.device_type_name } : undefined;
            return canViewParents ? deviceOptions(keyWords, selected)
              : Promise.resolve(selected ? [selected] : []);
          }}
        />
        <ProFormDigit name="sample_rate_hz" label="Sample rate (Hz)"
          rules={[
            { required: true, message: 'Enter a sample rate.' },
            { validator: (_: unknown, value: number | null | undefined) => value == null || (Number.isFinite(value) && value > 0)
              ? Promise.resolve() : Promise.reject(new Error('Enter a number greater than zero.')) },
          ]}
        />
      </ModalForm>}
    </PageContainer>
  );
}
