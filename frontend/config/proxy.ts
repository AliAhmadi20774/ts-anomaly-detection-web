const backendOptions = {
  target: process.env.BACKEND_URL || 'http://127.0.0.1:8000',
  // Preserve the browser host so Django can validate same-origin CSRF requests.
  changeOrigin: false,
  pathRewrite: { '^/backend': '' },
};

const backendProxy = {
  '/backend/api/dat/import/': {
    ...backendOptions,
    // A batch stores all signal samples before returning its result.
    proxyTimeout: 120_000,
  },
  '/backend/': {
    ...backendOptions,
    proxyTimeout: 5000,
  },
};

export default {
  dev: backendProxy,
  test: backendProxy,
  pre: backendProxy,
};
