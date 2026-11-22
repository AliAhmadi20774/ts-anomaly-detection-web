import { ReloadOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Descriptions, Space, Tag } from 'antd';
import { getBackendHealth } from './service';
import { formatTehranDateTime } from '@/utils/dateTime';

export default function BackendStatus() {
  const health = useQuery({
    queryKey: ['backend', 'health'],
    queryFn: ({ signal }) => getBackendHealth(signal),
    retry: false,
    refetchOnWindowFocus: false,
  });

  return (
    <PageContainer
      title="Backend connection"
      subTitle="Check the connection to the Python API."
    >
      <Space orientation="vertical" size="large" style={{ width: '100%' }}>
        <Card
          title="API health"
          extra={
            <Button
              icon={<ReloadOutlined />}
              loading={health.isFetching}
              onClick={() => void health.refetch()}
            >
              Check again
            </Button>
          }
        >
          {health.isPending ? (
            <Alert type="info" title="Checking the API…" showIcon />
          ) : health.isError ? (
            <Alert
              type="error"
              showIcon
              title="API connection failed"
              description={`${health.error.message} Check that the backend is running, then try again.`}
            />
          ) : (
            <Descriptions
              column={1}
              items={[
                {
                  key: 'status',
                  label: 'Status',
                  children: <Tag color="success">Connected</Tag>,
                },
                {
                  key: 'response',
                  label: 'API response',
                  children: <code>{JSON.stringify(health.data)}</code>,
                },
                {
                  key: 'checked',
                  label: 'Last checked',
                  children: formatTehranDateTime(health.dataUpdatedAt),
                },
              ]}
            />
          )}
        </Card>
      </Space>
    </PageContainer>
  );
}
