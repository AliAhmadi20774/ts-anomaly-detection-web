import { LogoutOutlined } from '@ant-design/icons';
import { history, useModel } from '@umijs/max';
import { Dropdown } from 'antd';
import type { ReactNode } from 'react';
import { outLogin } from '@/services/ant-design-pro/api';

export function AvatarDropdown({ children }: { children?: ReactNode }) {
  const { setInitialState } = useModel('@@initialState');

  const logout = async () => {
    try {
      await outLogin();
    } finally {
      await setInitialState((state) => ({ ...state, currentUser: undefined }));
      history.replace('/user/login');
    }
  };

  return (
    <Dropdown
      placement="bottomRight"
      menu={{
        items: [{ key: 'logout', icon: <LogoutOutlined />, label: 'Sign out' }],
        onClick: () => void logout().catch(() => undefined),
      }}
    >
      {children}
    </Dropdown>
  );
}
