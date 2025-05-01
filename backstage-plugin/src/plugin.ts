import {
  createPlugin,
  createRoutableExtension,
} from '@backstage/core-plugin-api';

import { rootRouteRef } from './routes';

export const buildAndBurnPlugin = createPlugin({
  id: 'buildandburn',
  routes: {
    root: rootRouteRef,
  },
});

export const BuildAndBurnPage = buildAndBurnPlugin.provide(
  createRoutableExtension({
    name: 'BuildAndBurnPage',
    component: () =>
      import('./components/BuildAndBurnPage').then(m => m.BuildAndBurnPage),
    mountPoint: rootRouteRef,
  }),
); 