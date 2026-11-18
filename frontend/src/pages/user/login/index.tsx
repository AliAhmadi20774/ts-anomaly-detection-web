import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { LoginForm, ProFormText } from '@ant-design/pro-components';
import { Helmet, history, useModel } from '@umijs/max';
import { Alert, App } from 'antd';
import { useEffect, useState } from 'react';
import { login } from '@/services/ant-design-pro/api';
import settings from '../../../../config/defaultSettings';

function getSafeRedirectUrl(redirect: string | null): string {
  if (!redirect?.startsWith('/') || redirect.startsWith('//')) return '/';
  try {
    const url = new URL(redirect, window.location.origin);
    return url.origin === window.location.origin
      ? `${url.pathname}${url.search}${url.hash}`
      : '/';
  } catch {
    return '/';
  }
}

export default function Login() {
  const [invalidCredentials, setInvalidCredentials] = useState(false);
  const { initialState, setInitialState } = useModel('@@initialState');
  const { message } = App.useApp();

  useEffect(() => {
    if (initialState?.currentUser) {
      const redirect = new URL(window.location.href).searchParams.get('redirect');
      history.replace(getSafeRedirectUrl(redirect));
    }
  }, [initialState?.currentUser]);

  const handleSubmit = async (values: API.LoginParams) => {
    setInvalidCredentials(false);
    try {
      const result = await login({ ...values, type: 'account' });
      if (result.status !== 'ok') {
        setInvalidCredentials(true);
        return false;
      }
      const currentUser = await initialState?.fetchUserInfo?.();
      if (!currentUser) throw new Error('Unable to load the account.');
      await setInitialState((state) => ({ ...state, currentUser }));
      return true;
    } catch {
      message.error('Sign in failed. Please try again.');
      return false;
    }
  };

  return (
    <div className="login-page">
      <Helmet><title>Sign in - {settings.title}</title></Helmet>
      <LoginForm<API.LoginParams>
        logo={<img alt="" src="/logo.svg" />}
        title={settings.title}
        subTitle="Demo account: admin / ant.design"
        contentStyle={{ width: '100%', maxWidth: 360 }}
        submitter={{ searchConfig: { submitText: 'Sign in' } }}
        onFinish={handleSubmit}
      >
        {invalidCredentials && (
          <Alert
            type="error"
            showIcon
            title="Incorrect username or password."
            style={{ marginBottom: 24 }}
          />
        )}
        <ProFormText
          name="username"
          label="Username"
          fieldProps={{ prefix: <UserOutlined />, autoComplete: 'username' }}
          rules={[{ required: true, message: 'Enter your username.' }]}
        />
        <ProFormText.Password
          name="password"
          label="Password"
          fieldProps={{ prefix: <LockOutlined />, autoComplete: 'current-password' }}
          rules={[{ required: true, message: 'Enter your password.' }]}
        />
      </LoginForm>
    </div>
  );
}
