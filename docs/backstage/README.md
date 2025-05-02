# Build and Burn Backstage Plugin

This plugin integrates the Build and Burn environment management system with Backstage, allowing developers to create, manage, and destroy their build-and-burn environments directly from the Backstage developer portal.

## Features

- Create environments directly from manifest YAML
- Trigger GitHub Actions workflows to manage environments
- Monitor GitHub Actions workflow runs in real-time
- View environment details and access information
- Destroy environments when no longer needed
- Real-time log viewing for workflow runs

## Installation

### Prerequisites

Before installing the plugin, ensure you have:

1. A running Backstage instance
2. Node.js 14+ (16+ recommended)
3. Yarn
4. GitHub integration configured in your Backstage instance

### Frontend Plugin Installation

1. Install the plugin in your Backstage app:

```bash
# From your Backstage app directory
yarn add --cwd packages/app @internal/plugin-buildandburn
```

2. Add the plugin to your Backstage app:

Edit your `packages/app/src/App.tsx` file to import and use the plugin:

```tsx
import { BuildAndBurnPage } from '@internal/plugin-buildandburn';

// Add to the FlatRoutes
<Route path="/build-and-burn" element={<BuildAndBurnPage />} />
```

3. Add the plugin to your sidebar:

Edit your `packages/app/src/components/Root/Root.tsx` file:

```tsx
import BuildIcon from '@material-ui/icons/Build';

// Add to the sidebar items
<SidebarItem icon={BuildIcon} to="build-and-burn" text="Build & Burn" />
```

4. Register the API client:

Edit your `packages/app/src/apis.ts` file:

```tsx
import { BuildAndBurnClient, buildAndBurnApiRef } from '@internal/plugin-buildandburn';

// Add to the ApiFactories
createApiFactory({
  api: buildAndBurnApiRef,
  deps: { configApi: configApiRef },
  factory: ({ configApi }) => new BuildAndBurnClient({
    baseUrl: configApi.getString('backend.baseUrl') + '/api/buildandburn',
  }),
}),
```

### Backend Plugin Installation

1. Create a backend plugin in your Backstage backend:

```bash
# From your Backstage root directory
yarn new --select backend-plugin --option id=buildandburn
```

2. Add the Build and Burn API routes to your backend:

```typescript
// In packages/backend/src/plugins/buildandburn.ts
import { createRouter } from '@internal/plugin-buildandburn/src/backend';
import { PluginEnvironment } from '../types';

export default async function createPlugin(
  env: PluginEnvironment,
): Promise<Router> {
  return createRouter({
    logger: env.logger,
    config: env.config,
  });
}
```

3. Add the plugin to your backend:

```typescript
// In packages/backend/src/index.ts
import buildandburn from './plugins/buildandburn';

// Add to your service builders
const buildandburnEnv = useHotMemoize(module, () => createEnv('buildandburn'));
apiRouter.use('/buildandburn', await buildandburn(buildandburnEnv));
```

## Configuration

Add the following to your Backstage `app-config.yaml`:

```yaml
github:
  token: ${GITHUB_TOKEN}

backend:
  baseUrl: http://localhost:7007
```

You will need to provide a GitHub personal access token with the `repo` and `workflow` scopes to enable GitHub Actions integration.

## Usage

Once installed, you can access the Build and Burn UI from the sidebar. The UI allows you to:

1. Create new environments using:
   - Direct YAML manifest entry
   - GitHub Actions workflows
2. View all your active environments
3. Get detailed information about each environment
4. Monitor GitHub Actions workflow runs
5. View workflow logs in real-time
6. Destroy environments when no longer needed

For detailed usage instructions, see:
- [GitHub Actions Integration](./github-actions-integration.md)
- [Template Usage](./template-usage.md)

## API Endpoints

The backend plugin provides the following REST endpoints:

- `GET /api/buildandburn/environments`: List all environments
- `GET /api/buildandburn/environments/{id}`: Get details of a specific environment
- `POST /api/buildandburn/environments`: Create a new environment
- `DELETE /api/buildandburn/environments/{id}`: Destroy an environment
- `POST /api/buildandburn/github-actions/workflow`: Trigger a GitHub Actions workflow
- `GET /api/buildandburn/github-actions/workflow-runs`: Get workflow runs
- `GET /api/buildandburn/github-actions/workflow-runs/{runId}`: Get a specific workflow run
- `GET /api/buildandburn/github-actions/workflow-runs/{runId}/logs`: Get logs for a workflow run

## Troubleshooting

If you encounter issues with the plugin:

1. **Plugin Not Appearing**: Check that it's properly added to App.tsx and Root.tsx
2. **API Connection Errors**: Verify the backend plugin is properly registered
3. **GitHub Integration Issues**: Ensure your GitHub token has the required scopes
4. **Missing Workflow Files**: Check that repositories have the correct workflow files

## Contributing

For information on contributing to the Build and Burn project, please see the [CONTRIBUTING.md](../../CONTRIBUTING.md) file in the root of the repository.

## License

This plugin is licensed under the Apache 2.0 License. 