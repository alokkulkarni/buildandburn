# Build and Burn Backstage Plugin

This plugin integrates the Build and Burn system with Backstage, allowing you to create, manage, and monitor disposable Kubernetes environments directly from your developer portal.

## Features

- Create environments directly from manifest YAML
- Trigger GitHub Actions workflows to manage environments
- Monitor GitHub Actions workflow runs in real-time
- View environment details and access information
- Destroy environments when no longer needed

## Installation

### For the Frontend Plugin

1. Install the plugin package in your Backstage app:

```bash
# From your Backstage root directory
yarn add --cwd packages/app @internal/plugin-buildandburn
```

2. Add the plugin to your Backstage app:

```tsx
// In packages/app/src/App.tsx
import { BuildAndBurnPage } from '@internal/plugin-buildandburn';

// Add to your routes
<Route path="/build-and-burn" element={<BuildAndBurnPage />} />
```

3. Add the plugin to your sidebar:

```tsx
// In packages/app/src/components/Root/Root.tsx
import BuildIcon from '@material-ui/icons/Build';

// Add to your sidebar items
<SidebarItem icon={BuildIcon} to="build-and-burn" text="Build & Burn" />
```

4. Register the API:

```tsx
// In packages/app/src/apis.ts
import { buildAndBurnApiRef, BuildAndBurnClient } from '@internal/plugin-buildandburn';

// Add to your API factories
createApiFactory({
  api: buildAndBurnApiRef,
  deps: { configApi: configApiRef },
  factory: ({ configApi }) => new BuildAndBurnClient({
    baseUrl: configApi.getString('backend.baseUrl') + '/api/buildandburn',
  }),
})
```

### For the Backend Plugin

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

Add the following to your `app-config.yaml`:

```yaml
github:
  token: ${GITHUB_TOKEN}

backend:
  baseUrl: http://localhost:7007
```

You will need to provide a GitHub personal access token with the `repo` and `workflow` scopes to enable GitHub Actions integration.

## Usage

### Creating an Environment

1. Navigate to the Build and Burn page in your Backstage portal
2. Click the "Create Environment" button
3. Choose your creation method:
   - **Direct Manifest**: Enter a YAML manifest to create an environment directly
   - **GitHub Actions**: Configure a GitHub repository and action to create via GitHub Actions

### Managing GitHub Actions Workflows

To trigger a GitHub Actions workflow:

1. Select the "GitHub Actions" tab in the creation dialog
2. Enter the GitHub repository owner and name
3. Choose the action to perform (`up`, `down`, `info`, or `list`)
4. Configure action-specific parameters
5. Click "Trigger Workflow"

The workflow will be triggered, and you can monitor its progress in the "GitHub Workflows" tab.

### Viewing Workflow Runs

1. Click the "Workflows" button on an environment
2. View all workflow runs for the repository
3. Click "View Logs" to see detailed logs for a specific run
4. Click "Open in GitHub" to view the run in GitHub

### Destroying an Environment

1. Click the "Destroy" button on an environment
2. Confirm the destruction
3. If the environment is linked to a GitHub repository, a workflow will be triggered to destroy it
4. Otherwise, the environment will be destroyed directly

## Development

To start the plugin in development mode:

```bash
# From your Backstage root directory
yarn start
```

To run the backend separately:

```bash
# From the plugin directory
yarn start:backend
```

## Testing

```bash
# From the plugin directory
yarn test
```

## Production Readiness

This plugin is designed for production use and includes:

1. **Error Handling**: Comprehensive error handling for all API calls
2. **TypeScript Types**: Full typing for all components and APIs
3. **Real-time Updates**: Automatic polling for active workflow runs
4. **Integration Testing**: Tests for all major components and APIs

## GitHub Actions Integration Details

This plugin integrates with GitHub Actions in the following ways:

1. **Triggering Workflows**: Triggering workflow_dispatch events on the Build and Burn workflow
2. **Listing Workflow Runs**: Retrieving all runs for the workflow
3. **Run Details**: Getting detailed information about workflow runs
4. **Logs**: Fetching and displaying logs from workflow jobs

The workflow must be named `buildandburn.yml` and located in the `.github/workflows` directory of your repository.

## Troubleshooting

Common issues:

1. **GitHub Token Issues**: Ensure your GitHub token has the `repo` and `workflow` scopes
2. **Missing Workflow**: Ensure the repository contains a `.github/workflows/buildandburn.yml` file
3. **Plugin Configuration**: Check the backend baseUrl in your app-config.yaml
4. **API Connection**: Verify the backend plugin is properly registered and running 