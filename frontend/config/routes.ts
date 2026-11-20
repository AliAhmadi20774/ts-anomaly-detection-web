export default [
  { path: '/user/login', name: 'login', layout: false, component: './user/login' },
  { path: '/user', redirect: '/user/login' },
  {
    path: '/device-types', name: 'device-types', icon: 'appstore',
    component: './DeviceTypes', access: 'canViewDeviceTypes',
  },
  {
    path: '/test-definitions', name: 'test-definitions', icon: 'experiment',
    component: './TestDefinitions', access: 'canViewTestDefinitions',
  },
  {
    path: '/signal-definitions', name: 'signal-definitions', icon: 'lineChart',
    component: './SignalDefinitions', access: 'canViewSignalDefinitions',
  },
  {
    path: '/serial-batches', name: 'serial-batches', icon: 'database',
    component: './SerialBatches', access: 'canViewSerialBatches',
  },
  {
    path: '/serial-batches/:batchId/serials/:deviceId', name: 'serial-detail',
    component: './SerialDetail', access: 'canViewSerialBatches', hideInMenu: true,
  },
  {
    path: '/serial-batches/:batchId', name: 'serial-batch-detail',
    component: './SerialBatchDetail', access: 'canViewSerialBatches', hideInMenu: true,
  },
  { path: '/test-runs', redirect: '/serial-batches' },
  {
    path: '/dat-preview', name: 'dat-preview', icon: 'upload',
    component: './DatPreview', access: 'canPreviewDat',
  },
  {
    path: '/backend-status', name: 'backend-status', icon: 'api',
    component: './BackendStatus',
  },
  { path: '/', redirect: '/backend-status' },
  { path: '/*', component: './exception/404' },
];
