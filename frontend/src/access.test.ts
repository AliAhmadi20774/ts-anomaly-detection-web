import { describe, expect, it } from 'vitest';
import access from './access';
import type { CurrentUser } from './services/auth';

const user: CurrentUser = {
  id: 2, username: '002', name: '002', is_superuser: false,
  permissions: ['devices.view_testdefinition'],
};

describe('Django permissions', () => {
  it('shows only the definition pages allowed by backend permissions', () => {
    expect(access({ currentUser: user })).toEqual({
      canAdmin: false, canViewDeviceTypes: false,
      canViewTestDefinitions: true, canViewSignalDefinitions: false,
      canViewSerialBatches: false,
      canPreviewDat: false,
    });
  });

  it('allows a superuser to access every definition page', () => {
    expect(Object.values(access({
      currentUser: { ...user, is_superuser: true, permissions: [] },
    })).every(Boolean)).toBe(true);
  });

  it('does not grant access without an authenticated user', () => {
    expect(Object.values(access(undefined)).some(Boolean)).toBe(false);
  });

  it('grants batch access independently of definition access', () => {
    const permissions = access({ currentUser: {
      ...user, permissions: ['devices.view_measurementbatch'],
    } });
    expect(permissions.canViewSerialBatches).toBe(true);
    expect(permissions.canViewTestDefinitions).toBe(false);
  });
});
