import { apiRequest } from './client';

export interface CurrentUser {
  id: number;
  username: string;
  name: string;
  is_superuser: boolean;
  permissions: string[];
}

export interface LoginParams {
  username: string;
  password: string;
}

export function getCurrentUser() {
  return apiRequest<CurrentUser>('/auth/me/');
}

export async function signIn(values: LoginParams) {
  await apiRequest<{ csrfToken: string }>('/auth/csrf/');
  return apiRequest<CurrentUser>('/auth/login/', { method: 'POST', data: values });
}

export function signOut() {
  return apiRequest<void>('/auth/logout/', { method: 'POST', data: {} });
}

export function hasPermission(user: CurrentUser | undefined, permission: string): boolean {
  return Boolean(user && (user.is_superuser || user.permissions.includes(permission)));
}
