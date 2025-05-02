# Build and Burn Backstage Plugin

The Build and Burn Backstage plugin integrates the Build and Burn system with Backstage, allowing you to create, manage, and monitor disposable Kubernetes environments directly from your developer portal.

## Features

- Create environments directly from manifest YAML
- Trigger GitHub Actions workflows to manage environments
- Monitor GitHub Actions workflow runs in real-time
- View environment details and access information
- Destroy environments when no longer needed
- Real-time log viewing for workflow runs

## Architecture

The plugin consists of two main components:

1. **Frontend Plugin**: User interface components for Backstage
   - Environment management page
   - Manifest creation dialog
   - GitHub Actions workflow monitoring
   - Log viewer

2. **Backend Plugin**: Server-side components that:
   - Interface with GitHub Actions API
   - Manage environment metadata
   - Process manifests
   - Handle authentication and permissions

### Integration Points

The plugin integrates with several systems:

- **Backstage Core**: For UI components and API integration
- **GitHub Actions**: For triggering and monitoring workflows
- **Build and Burn CLI**: Indirectly through GitHub Actions workflows

## Installation

### Prerequisites

Before installing the plugin, ensure you have:

1. A running Backstage instance (version 1.0.0 or higher)
2. Node.js 14+ (16+ recommended)
3. Yarn
4. GitHub repositories with Build and Burn workflows configured
5. GitHub personal access token with `repo` and `workflow` scopes

### Frontend Plugin Installation

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

For production deployments, ensure you:

1. Store tokens securely using environment variables
2. Configure proper CORS settings if your frontend and backend are on different domains
3. Set up proper authentication for the API endpoints

## Usage

### Creating an Environment

There are two ways to create environments:

#### Direct Manifest Creation

1. Navigate to the Build and Burn page
2. Click the "Create Environment" button
3. Select the "Direct Manifest" tab
4. Enter your environment manifest in YAML format
5. Click "Create"

This method directly creates an environment using the backend API without GitHub Actions.

#### GitHub Actions Workflow

1. Navigate to the Build and Burn page
2. Click the "Create Environment" button
3. Select the "GitHub Actions" tab
4. Enter the GitHub repository owner and name
5. Select "Create Environment (up)" action
6. Enter the path to your manifest file in the repository
7. Configure optional parameters:
   - Skip K8s Generation
   - Dry Run
8. Click "Trigger Workflow"

This method triggers a GitHub Actions workflow in the specified repository, which will create the environment.

### Monitoring Environment Status

The main page shows a list of all environments with their:

- ID
- Name
- Creation timestamp
- Current status
- GitHub repository (if created via GitHub Actions)
- Actions (Details, Workflows, Destroy)

### Viewing Environment Details

Click the "Details" button on an environment to see:

- Service endpoints
- Database connection information
- Message queue details
- Associated GitHub repository

### Managing GitHub Actions Workflows

When you trigger a GitHub Actions workflow or click the "Workflows" button on an environment:

1. The plugin switches to the "GitHub Workflows" tab
2. Shows all workflow runs for the repository
3. Displays status, creation time, and available actions
4. Auto-refreshes active workflows every 10 seconds

### Viewing Workflow Logs

To view detailed logs from a workflow run:

1. Click "View Logs" on a workflow run
2. The plugin shows logs from all jobs in the workflow
3. For in-progress workflows, use "Refresh" to get the latest logs

### Destroying an Environment

1. Click the "Destroy" button on an environment
2. Confirm the destruction
3. If the environment is linked to a GitHub repository:
   - The plugin triggers a GitHub Actions workflow with the "down" action
   - The workflow destroys the environment resources
4. Otherwise, the environment is destroyed directly via the backend API

## GitHub Actions Integration

The plugin integrates with GitHub Actions to create and manage environments.

Key points:

1. Workflows must be named `buildandburn.yml` and located in `.github/workflows/`
2. The plugin supports the following actions:
   - `up`: Create an environment
   - `down`: Destroy an environment
   - `info`: Get environment information
   - `list`: List all environments

## Development

### Setting Up the Development Environment

1. Clone the repository
2. Install dependencies:
   ```bash
   yarn install
   ```
3. Start the development server:
   ```bash
   yarn start
   ```

### Testing

```bash
yarn test
```

This runs:
- Unit tests for frontend components
- Unit tests for API client
- Integration tests for GitHub Actions API

### Building for Production

```bash
yarn build
```

This creates a production-ready build in the `dist` directory.

## Troubleshooting

### Common Issues and Solutions

1. **GitHub Token Issues**:
   - Ensure your GitHub token has the `repo` and `workflow` scopes
   - Check that the token is correctly configured in `app-config.yaml`
   - Verify the token is not expired

2. **Missing Workflow File**:
   - Ensure the repository contains a `.github/workflows/buildandburn.yml` file
   - Check that the workflow file is properly configured with inputs for action, manifestPath, etc.

3. **Backend Connection Issues**:
   - Verify the backend plugin is properly registered
   - Check that the baseUrl in your Backstage configuration is correct
   - Ensure CORS is properly configured if needed

4. **Workflow Trigger Failures**:
   - Check that the repository owner and name are correct
   - Verify that you have permission to trigger workflows in the repository
   - Check the workflow file for errors

### Debugging

The plugin includes debug logging that can be enabled:

1. In the browser console, set `localStorage.debug = '*'`
2. Reload the page
3. Check the console for detailed log messages

For backend issues, check the Backstage backend logs.

## API Reference

### Frontend API

The plugin provides a `BuildAndBurnApi` interface with the following methods:

- `listEnvironments()`: List all environments
- `getEnvironment(id)`: Get details for a specific environment
- `createEnvironment(manifest)`: Create a new environment
- `destroyEnvironment(id)`: Destroy an environment
- `triggerGithubWorkflow(options)`: Trigger a GitHub Actions workflow
- `getWorkflowRuns(repo)`: Get all workflow runs for a repository
- `getWorkflowRunLogs(runId, repo)`: Get logs for a workflow run
- `getWorkflowRunStatus(runId, repo)`: Get the status of a workflow run

### Backend API

The backend plugin provides the following REST endpoints:

- `GET /api/buildandburn/environments`: List all environments
- `GET /api/buildandburn/environments/:id`: Get a specific environment
- `POST /api/buildandburn/environments`: Create a new environment
- `DELETE /api/buildandburn/environments/:id`: Delete an environment
- `POST /api/buildandburn/github-actions/workflow`: Trigger a GitHub Actions workflow
- `GET /api/buildandburn/github-actions/workflow-runs`: Get workflow runs
- `GET /api/buildandburn/github-actions/workflow-runs/:runId`: Get a specific workflow run
- `GET /api/buildandburn/github-actions/workflow-runs/:runId/logs`: Get logs for a workflow run

## Contributing

Contributions to the plugin are welcome! Please follow these steps:

1. Create an issue describing the feature or bug fix
2. Fork the repository
3. Create a branch for your changes (`git checkout -b feature/amazing-feature`)
4. Make your changes, including tests
5. Submit a pull request

For more details on contributing to the Build and Burn project as a whole, see the [CONTRIBUTING.md](../CONTRIBUTING.md) file in the root of the repository.

## License

This plugin is licensed under the Apache 2.0 License. 