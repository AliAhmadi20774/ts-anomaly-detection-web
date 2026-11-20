import { type CurrentUser, hasPermission } from '@/services/auth';

export default function access(initialState: { currentUser?: CurrentUser } | undefined) {
  const user = initialState?.currentUser;
  return {
    canAdmin: Boolean(user?.is_superuser),
    canViewDeviceTypes: hasPermission(user, 'devices.view_devicetype'),
    canViewTestDefinitions: hasPermission(user, 'devices.view_testdefinition'),
    canViewSignalDefinitions: hasPermission(user, 'devices.view_signaldefinition'),
    canViewSerialBatches: hasPermission(user, 'devices.view_measurementbatch'),
    canPreviewDat: ['devices.add_testrun', 'devices.view_devicetype', 'devices.view_testdefinition', 'devices.view_signaldefinition']
      .every((permission) => hasPermission(user, permission)),
  };
}
