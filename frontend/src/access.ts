import { type CurrentUser, hasPermission } from '@/services/auth';

export default function access(initialState: { currentUser?: CurrentUser } | undefined) {
  const user = initialState?.currentUser;
  return {
    canAdmin: Boolean(user?.is_superuser),
    canViewDeviceTypes: hasPermission(user, 'devices.view_devicetype'),
    canViewTestDefinitions: hasPermission(user, 'devices.view_testdefinition'),
    canViewSignalDefinitions: hasPermission(user, 'devices.view_signaldefinition'),
    canViewTestRuns: hasPermission(user, 'devices.view_testrun'),
  };
}
