import { PlusOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { ModalForm, PageContainer, ProFormText, ProTable } from '@ant-design/pro-components';
import { useModel } from '@umijs/max';
import { Alert, App, Button, Popconfirm, Space } from 'antd';
import { useRef, useState } from 'react';
import { hasPermission } from '@/services/auth';
import { type DeviceType, type DeviceTypeInput, deviceTypes } from '@/services/definitions';

export default function DeviceTypesPage() {
  const { initialState } = useModel('@@initialState');
  const { message } = App.useApp();
  const actionRef = useRef<ActionType | undefined>(undefined);
  const [editing, setEditing] = useState<DeviceType>();
  const [open, setOpen] = useState(false);
  const [loadError, setLoadError] = useState<string>();
  const user = initialState?.currentUser;
  
  const canAdd = hasPermission(user, 'devices.add_devicetype');
  const canChange = hasPermission(user, 'devices.change_devicetype');
  const canDelete = hasPermission(user, 'devices.delete_devicetype');

  const remove = async (record: DeviceType) => {
    try {
      await deviceTypes.remove(record.id);
      message.success('Device type deleted.');
      void actionRef.current?.reload();
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Delete failed.');
    }
  };

  const columns: ProColumns<DeviceType>[] = [
    { title: 'Name', dataIndex: 'name', ellipsis: true },
    
    {
      title: 'Actions', valueType: 'option', width: 160,
      hideInTable: !canChange && !canDelete,
      render: (_, record) => (
        <Space>
          {canChange && <Button type="link" size="small" onClick={() => {
            setEditing(record); setOpen(true);
          }}>Edit</Button>}
          {canDelete && <Popconfirm
            title="Delete device type?"
            onConfirm={() => remove(record)} okText="Delete" okButtonProps={{ danger: true }}
          >
            <Button type="link" size="small" danger>Delete</Button>
          </Popconfirm>}
        </Space>
      ),
    },
  ];

  return (
    <PageContainer title="Device types" subTitle="Organize test definitions by device type.">
      {loadError && <Alert type="error" showIcon title={loadError} style={{ marginBottom: 16 }} />}
      <ProTable<DeviceType>
        actionRef={actionRef} columns={columns} rowKey="id"
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        options={{ density: false, fullScreen: false, setting: false }}
        pagination={{ defaultPageSize: 20, showSizeChanger: true, pageSizeOptions: [20, 50, 100] }}
        scroll={{ x: 480 }}
        request={async (params) => {
          setLoadError(undefined);
          const result = await deviceTypes.list({
            page: params.current, page_size: params.pageSize, search: params.name,
          });
          return { data: result.results, success: true, total: result.count };
        }}
        onRequestError={(error) => setLoadError(error.message)}
        toolBarRender={() => canAdd ? [
          <Button key="create" type="primary" icon={<PlusOutlined />} onClick={() => {
            setEditing(undefined); setOpen(true);
          }}>New device type</Button>,
        ] : []}
      />
      {open && <ModalForm<DeviceTypeInput>
        title={editing ? 'Edit device type' : 'New device type'}
        open={open} onOpenChange={setOpen} initialValues={editing}
        modalProps={{ destroyOnHidden: true }}
        submitter={{ searchConfig: { submitText: 'Save', resetText: 'Cancel' } }}
        onFinish={async (values) => {
          try {
            if (editing) await deviceTypes.update(editing.id, values);
            else await deviceTypes.create(values);
            message.success('Device type saved.');
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
        
      </ModalForm>}
    </PageContainer>
  );
}
