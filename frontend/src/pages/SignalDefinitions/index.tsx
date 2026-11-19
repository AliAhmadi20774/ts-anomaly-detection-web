import { PlusOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { ModalForm, PageContainer, ProFormSelect, ProFormText, ProTable } from '@ant-design/pro-components';
import { useModel } from '@umijs/max';
import { Alert, App, Button, Popconfirm, Space } from 'antd';
import { useRef, useState } from 'react';
import { hasPermission } from '@/services/auth';
import { type SignalDefinition, type SignalDefinitionInput, signalDefinitions, testOptions } from '@/services/definitions';

export default function SignalDefinitionsPage() {
  const { initialState } = useModel('@@initialState');
  const { message } = App.useApp();
  const actionRef = useRef<ActionType | undefined>(undefined);
  const [editing, setEditing] = useState<SignalDefinition>();
  const [open, setOpen] = useState(false);
  const [loadError, setLoadError] = useState<string>();
  const user = initialState?.currentUser;
  const canViewParents = hasPermission(user, 'devices.view_testdefinition');
  const canAdd = hasPermission(user, 'devices.add_signaldefinition') && canViewParents;
  const canChange = hasPermission(user, 'devices.change_signaldefinition');
  const canDelete = hasPermission(user, 'devices.delete_signaldefinition');

  const remove = async (record: SignalDefinition) => {
    try {
      await signalDefinitions.remove(record.id);
      message.success('Signal definition deleted.');
      void actionRef.current?.reload();
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Delete failed.');
    }
  };

  const columns: ProColumns<SignalDefinition>[] = [
    { title: 'Name', dataIndex: 'name', ellipsis: true },
    { title: 'Device type', dataIndex: 'device_type_name', search: false },
    { title: 'Test', dataIndex: 'test_name', search: false },
    {
      title: 'Test', dataIndex: 'test', valueType: 'select', hideInTable: true,
      search: canViewParents ? undefined : false, request: ({ keyWords }) => testOptions(keyWords),
      fieldProps: { showSearch: true, filterOption: false },
    },
    {
      title: 'Actions', valueType: 'option', width: 160,
      hideInTable: !canChange && !canDelete,
      render: (_, record) => (
        <Space>
          {canChange && <Button type="link" size="small" onClick={() => {
            setEditing(record); setOpen(true);
          }}>Edit</Button>}
          {canDelete && <Popconfirm
            title="Delete signal definition?"
            onConfirm={() => remove(record)} okText="Delete" okButtonProps={{ danger: true }}
          >
            <Button type="link" size="small" danger>Delete</Button>
          </Popconfirm>}
        </Space>
      ),
    },
  ];

  return (
    <PageContainer title="Signal definitions" subTitle="Define the signals available within each test.">
      {loadError && <Alert type="error" showIcon title={loadError} style={{ marginBottom: 16 }} />}
      <ProTable<SignalDefinition>
        actionRef={actionRef} columns={columns} rowKey="id"
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        options={{ density: false, fullScreen: false, setting: false }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: [20, 50, 100] }}
        scroll={{ x: 760 }}
        request={async (params) => {
          setLoadError(undefined);
          const result = await signalDefinitions.list({
            page: params.current, page_size: params.pageSize, search: params.name, test: params.test,
          });
          return { data: result.results, success: true, total: result.count };
        }}
        onRequestError={(error) => setLoadError(error.message)}
        toolBarRender={() => canAdd ? [
          <Button key="create" type="primary" icon={<PlusOutlined />} onClick={() => {
            setEditing(undefined); setOpen(true);
          }}>New signal definition</Button>,
        ] : []}
      />
      {open && <ModalForm<SignalDefinitionInput>
        title={editing ? 'Edit signal definition' : 'New signal definition'}
        open={open} onOpenChange={setOpen} initialValues={editing}
        modalProps={{ destroyOnHidden: true }}
        submitter={{ searchConfig: { submitText: 'Save', resetText: 'Cancel' } }}
        onFinish={async (values) => {
          try {
            if (editing) await signalDefinitions.update(editing.id, values);
            else await signalDefinitions.create(values);
            message.success('Signal definition saved.');
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
        <ProFormSelect name="test" label="Test" debounceTime={300}
          rules={[{ required: true, message: 'Select a test.' }]}
          fieldProps={{ showSearch: true, filterOption: false, disabled: !canViewParents }}
          request={({ keyWords }) => {
            const selected = editing ? {
              value: editing.test, label: `${editing.device_type_name} / ${editing.test_name}`,
            } : undefined;
            return canViewParents ? testOptions(keyWords, selected)
              : Promise.resolve(selected ? [selected] : []);
          }}
        />
      </ModalForm>}
    </PageContainer>
  );
}
