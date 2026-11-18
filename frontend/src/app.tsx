import type { Settings as LayoutSettings } from '@ant-design/pro-components';
import type { RequestConfig, RunTimeLayoutConfig } from '@umijs/max';
import { history, Link } from '@umijs/max';
import type { ReactNode } from 'react';
import ErrorBoundary from '@/components/ErrorBoundary';
import OfflineBanner from '@/components/OfflineBanner';
import { AvatarDropdown } from '@/components/RightContent/AvatarDropdown';
import { currentUser as queryCurrentUser } from '@/services/ant-design-pro/api';
import defaultSettings from '../config/defaultSettings';
import { errorConfig } from './requestErrorConfig';

const loginPath = '/user/login';

export async function getInitialState(): Promise<{
  settings?: Partial<LayoutSettings>;
  currentUser?: API.CurrentUser;
  fetchUserInfo?: () => Promise<API.CurrentUser | undefined>;
}> {
  const fetchUserInfo = async () => {
    try {
      const response = await queryCurrentUser({ skipErrorHandler: true });
      return response.data;
    } catch {
      const { pathname, search, hash } = history.location;
      history.replace(
        `${loginPath}?redirect=${encodeURIComponent(pathname + search + hash)}`,
      );
      return undefined;
    }
  };

  return {
    settings: defaultSettings,
    fetchUserInfo,
    currentUser:
      history.location.pathname === loginPath ? undefined : await fetchUserInfo(),
  };
}

export const layout: RunTimeLayoutConfig = ({ initialState }) => ({
  ...initialState?.settings,
  menuItemRender: (item, dom) =>
    item.path ? <Link to={item.path}>{dom}</Link> : dom,
  actionsRender: false,
  avatarProps: {
    title: initialState?.currentUser?.name,
    render: (_, children) => <AvatarDropdown>{children}</AvatarDropdown>,
  },
  footerRender: false,
  links: [],
  ErrorBoundary,
  onPageChange: () => {
    const { pathname, search, hash } = history.location;
    if (!initialState?.currentUser && pathname !== loginPath) {
      history.replace(
        `${loginPath}?redirect=${encodeURIComponent(pathname + search + hash)}`,
      );
    }
  },
});

export const request: RequestConfig = { baseURL: '', ...errorConfig };

export function rootContainer(container: ReactNode) {
  return (
    <>
      <OfflineBanner />
      <ErrorBoundary>{container}</ErrorBoundary>
    </>
  );
}
