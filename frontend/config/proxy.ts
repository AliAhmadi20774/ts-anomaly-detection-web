const backendProxy = {
  '/backend/': {
    target: process.env.BACKEND_URL || 'http://127.0.0.1:8000',
    changeOrigin: true,
    pathRewrite: { '^/backend': '' },
    proxyTimeout: 5000,
  },
};

export default {
  dev: backendProxy,
  test: backendProxy,
  pre: backendProxy,
};
