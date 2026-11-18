export default [
  {
    path: '/user/login',
    name: 'login',
    layout: false,
    component: './user/login',
  },
  {
    path: '/user',
    redirect: '/user/login',
  },
  {
    path: '/backend-status',
    name: 'backend-status',
    icon: 'api',
    component: './BackendStatus',
  },
  {
    path: '/',
    redirect: '/backend-status',
  },
  {
    path: '/*',
    component: './exception/404',
  },
];
