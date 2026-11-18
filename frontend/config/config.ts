import { join } from 'node:path';
import { defineConfig } from '@umijs/max';
import defaultSettings from './defaultSettings';
import proxy from './proxy';
import routes from './routes';

const { UMI_ENV = 'dev' } = process.env;

export default defineConfig({
  alias: { '@root': join(__dirname, '..') },
  hash: true,
  publicPath: '/',
  routes,
  ignoreMomentLocale: true,
  proxy: proxy[UMI_ENV as keyof typeof proxy],
  fastRefresh: true,
  model: {},
  initialState: {},
  title: 'Anomaly Detection',
  layout: { locale: true, ...defaultSettings },
  moment2dayjs: { preset: 'antd' },
  locale: { default: 'en-US', antd: true, baseNavigator: false },
  antd: {
    appConfig: {},
    configProvider: {
      variant: 'filled',
      theme: {
        token: {
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
      },
    },
  },
  request: {},
  reactQuery: {},
  access: {},
  headScripts: [{ src: '/scripts/loading.js', async: true }],
  // Only demo account login is needed until real authentication is added.
  mock: { exclude: ['mock/!(user).ts'] },
  utoopack: {
    devServer: { dynamicHmrChunkLists: true, lazyDynamicImports: true },
  },
  define: {
    'process.env.COMMIT_HASH': '',
    __APP_VERSION__: require('../package.json').version,
    __UMI_VERSION__: require('@umijs/max/package.json').version,
    __UTOO_VERSION__: require('@utoo/pack/package.json').version,
  },
});
