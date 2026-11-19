import { LogoutOutlined } from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import { history, useModel } from '@umijs/max';
import { App, Dropdown } from 'antd';
import type { ReactNode } from 'react';
import { signOut } from '@/services/auth';

export function AvatarDropdown({ children }: { children?: ReactNode }) {
  const { setInitialState } = useModel('@@initialState');
  const { message } = App.useApp();
  const queryClient = useQueryClient();

  const logout = async () => {
    try {
      await signOut();
      queryClient.clear();
      await setInitialState((state) => ({ ...state, currentUser: undefined }));
      history.replace('/user/login');
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Sign out failed.');
    }
  };

  return (
    <Dropdown
      placement="bottomRight"
      trigger={['click']}
      menu={{
        items: [{ key: 'logout', icon: <LogoutOutlined />, label: 'Sign out' }],
        onClick: () => void logout(),
      }}
    >
      <button type="button" aria-label="Account menu" style={{ background: 'none', border: 0, cursor: 'pointer', padding: 0 }}>{children}</button>
    </Dropdown>
  );
}
