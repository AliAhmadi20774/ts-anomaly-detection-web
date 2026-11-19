import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { LoginForm, ProFormText } from '@ant-design/pro-components';
import { Helmet, history, useModel } from '@umijs/max';
import { Alert } from 'antd';
import { useEffect, useState } from 'react';
import { type LoginParams, signIn } from '@/services/auth';
import settings from '../../../../config/defaultSettings';

function getSafeRedirectUrl(redirect: string | null): string {
  if (!redirect?.startsWith('/') || redirect.startsWith('//')) return '/';
  try {
    const url = new URL(redirect, window.location.origin);
    return url.origin === window.location.origin && url.pathname !== '/user/login'
      ? `${url.pathname}${url.search}${url.hash}` : '/';
  } catch {
    return '/';
  }
}

export default function Login() {
  const [error, setError] = useState<string>();
  const { initialState, setInitialState } = useModel('@@initialState');

  useEffect(() => {
    if (initialState?.currentUser) {
      const redirect = new URL(window.location.href).searchParams.get('redirect');
      history.replace(getSafeRedirectUrl(redirect));
    }
  }, [initialState?.currentUser]);

  const handleSubmit = async (values: LoginParams) => {
    setError(undefined);
    try {
      const currentUser = await signIn(values);
      await setInitialState((state) => ({ ...state, currentUser }));
      return true;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Sign in failed.');
      return false;
    }
  };

  return (
    <div className="login-page">
      <Helmet><title>Sign in - {settings.title}</title></Helmet>
      <LoginForm<LoginParams>
        logo={<img alt="" src="/logo.svg" />}
        title={settings.title}
        subTitle="Sign in with your personnel code."
        contentStyle={{ width: '100%', maxWidth: 360 }}
        submitter={{ searchConfig: { submitText: 'Sign in' } }}
        onFinish={handleSubmit}
      >
        {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 24 }} />}
        <ProFormText
          name="username" label="Personnel code"
          fieldProps={{ prefix: <UserOutlined />, autoComplete: 'username' }}
          rules={[{ required: true, message: 'Enter your personnel code.' }]}
        />
        <ProFormText.Password
          name="password" label="Password"
          fieldProps={{ prefix: <LockOutlined />, autoComplete: 'current-password' }}
          rules={[{ required: true, message: 'Enter your password.' }]}
        />
      </LoginForm>
    </div>
  );
}
