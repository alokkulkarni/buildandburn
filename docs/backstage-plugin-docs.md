# Build and Burn Backstage Plugin

## Overview

The Build and Burn Backstage Plugin is a frontend integration that connects the Backstage developer portal with the Build and Burn CLI tool. It provides a user-friendly interface for developers to create, manage, and destroy ephemeral Kubernetes environments directly from within Backstage.

## Purpose

The plugin serves as a web-based management interface for the Build and Burn system, enabling developers to:

1. Create disposable Kubernetes environments using YAML manifests
2. Monitor the status of active environments
3. Get detailed information about running environments, including access points and service endpoints
4. Destroy environments when no longer needed

This integration makes the Build and Burn functionality accessible through Backstage's unified developer portal, eliminating the need for developers to use the CLI directly.

## Architecture

The Backstage plugin follows a client-server architecture:

1. **Frontend Plugin**: A React-based UI that integrates with the Backstage UI framework
2. **Backend API**: REST endpoints that communicate with the Build and Burn CLI tool

### Frontend Components

The plugin consists of the following key components:

- **BuildAndBurnPage**: The main page component that displays a list of environments and details
- **ManifestDialog**: A dialog for creating new environments by submitting YAML manifests
- **BuildAndBurnClient**: An API client that communicates with the backend

### Backend Integration

The plugin requires a backend service that exposes these REST endpoints:

- `GET /api/buildandburn/environments` - List all environments
- `GET /api/buildandburn/environments/{id}` - Get details of a specific environment
- `POST /api/buildandburn/environments` - Create a new environment
- `DELETE /api/buildandburn/environments/{id}` - Destroy an environment

The backend implementation calls the Build and Burn CLI with appropriate parameters:

```bash
# List environments
buildandburn list

# Get environment info
buildandburn info --env-id <id>

# Create environment
buildandburn up --manifest <manifest-file>

# Destroy environment
buildandburn down --env-id <id>
```

## Data Model

The plugin works with the following data models:

- **Environment**: Represents a running Build and Burn environment
  - id: Unique identifier
  - name: Name of the environment
  - createdAt: Timestamp when created
  - status: Current status (active, creating, destroying, failed)
  - services: Deployed services and their endpoints
  - database: Database connection information (if applicable)
  - messageQueue: Message queue information (if applicable)

## User Workflow

1. **Creating an Environment**:
   - User clicks "Create Environment" button
   - User enters a YAML manifest defining the environment
   - Backend calls `buildandburn up --manifest <file>` with the manifest
   - UI refreshes to show the new environment

2. **Viewing Environment Details**:
   - User clicks on an environment in the list
   - Backend calls `buildandburn info --env-id <id>` with the environment ID
   - UI displays detailed information about the environment

3. **Destroying an Environment**:
   - User clicks "Destroy" button for an environment
   - Backend calls `buildandburn down --env-id <id>` with the environment ID
   - UI refreshes to remove the destroyed environment

## Installation

### Frontend

1. Install the plugin in your Backstage app:
   ```bash
   yarn add --cwd packages/app @internal/plugin-buildandburn
   ```

2. Add the plugin to your Backstage app routes:
   ```tsx
   import { BuildAndBurnPage } from '@internal/plugin-buildandburn';
   
   // Add to the FlatRoutes
   <Route path="/build-and-burn" element={<BuildAndBurnPage />} />
   ```

3. Add the plugin to your sidebar:
   ```tsx
   import BuildIcon from '@material-ui/icons/Build';
   
   // Add to the sidebar items
   <SidebarItem icon={BuildIcon} to="build-and-burn" text="Build & Burn" />
   ```

4. Register the API client:
   ```ts
   import { BuildAndBurnClient, buildAndBurnApiRef } from '@internal/plugin-buildandburn';
   
   // Add to the ApiFactories
   createApiFactory({
     api: buildAndBurnApiRef,
     deps: { configApi: configApiRef },
     factory: ({ configApi }) => new BuildAndBurnClient({
       baseUrl: configApi.getString('buildandburn.baseUrl'),
     }),
   })
   ```

### Backend

Create a backend plugin that implements the required API endpoints:

```typescript
// packages/backend/src/plugins/buildandburn.ts
import { createRouter } from '@backstage/backend-common';
import { Router } from 'express';
import { spawn } from 'child_process';
import { Logger } from 'winston';
import fs from 'fs';
import path from 'path';
import os from 'os';

export default async function createPlugin(
  router: Router,
  logger: Logger,
): Promise<Router> {
  const cliPath = process.env.BUILDANDBURN_CLI_PATH || 'buildandburn';
  const workDir = process.env.BUILDANDBURN_WORK_DIR || path.join(os.homedir(), '.buildandburn');
  
  // List all environments
  router.get('/environments', async (req, res) => {
    try {
      const { stdout } = await executeCommand(cliPath, ['list', '--json']);
      const environments = JSON.parse(stdout);
      res.json(environments);
    } catch (error) {
      logger.error(`Failed to list environments: ${error}`);
      res.status(500).json({ error: 'Failed to list environments' });
    }
  });
  
  // Get environment details
  router.get('/environments/:id', async (req, res) => {
    try {
      const { stdout } = await executeCommand(cliPath, ['info', '--env-id', req.params.id, '--json']);
      const environment = JSON.parse(stdout);
      res.json(environment);
    } catch (error) {
      logger.error(`Failed to get environment: ${error}`);
      res.status(500).json({ error: 'Failed to get environment' });
    }
  });
  
  // Create environment
  router.post('/environments', async (req, res) => {
    try {
      const { manifest } = req.body;
      const manifestFile = path.join(os.tmpdir(), `manifest-${Date.now()}.yaml`);
      
      // Write manifest to temporary file
      fs.writeFileSync(manifestFile, manifest);
      
      // Create environment
      const { stdout } = await executeCommand(
        cliPath, 
        ['up', '--manifest', manifestFile, '--json']
      );
      
      // Parse output
      const environment = JSON.parse(stdout);
      
      // Cleanup
      fs.unlinkSync(manifestFile);
      
      res.json(environment);
    } catch (error) {
      logger.error(`Failed to create environment: ${error}`);
      res.status(500).json({ error: 'Failed to create environment' });
    }
  });
  
  // Destroy environment
  router.delete('/environments/:id', async (req, res) => {
    try {
      await executeCommand(cliPath, ['down', '--env-id', req.params.id, '--auto-approve']);
      res.json({ success: true });
    } catch (error) {
      logger.error(`Failed to destroy environment: ${error}`);
      res.status(500).json({ error: 'Failed to destroy environment' });
    }
  });
  
  return router;
}

function executeCommand(command, args) {
  return new Promise((resolve, reject) => {
    const process = spawn(command, args);
    let stdout = '';
    let stderr = '';
    
    process.stdout.on('data', (data) => { stdout += data.toString(); });
    process.stderr.on('data', (data) => { stderr += data.toString(); });
    
    process.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(`Command failed with code ${code}: ${stderr}`));
      }
    });
  });
}
```

## Configuration

Add the following to your Backstage app-config.yaml:

```yaml
backend:
  env:
    BUILDANDBURN_CLI_PATH: /usr/local/bin/buildandburn
    BUILDANDBURN_WORK_DIR: /var/lib/backstage/buildandburn

buildandburn:
  baseUrl: http://localhost:7007/api/buildandburn
```

The plugin requires the Build and Burn CLI to be installed on the Backstage backend server. Ensure that the CLI and all its dependencies (Terraform, kubectl, etc.) are properly installed and configured.

## Security Considerations

- The backend should validate manifest files before executing them
- Access to the plugin should be restricted to authorized users via Backstage permissions
- Environment lifecycle should be monitored to avoid resource leaks
- AWS credentials must be securely managed on the backend server

## Troubleshooting

Common issues:

1. **Connection errors**: Check that the backend API is running and accessible
2. **CLI not found**: Ensure the Build and Burn CLI is installed and in the PATH of the backend server
3. **Permission errors**: Verify the backend has permissions to execute the CLI
4. **Missing dependencies**: Check that Terraform, kubectl, and other dependencies are installed
5. **Invalid manifests**: Verify that submitted YAML adheres to the required format

For detailed error logs, check:
- Backstage backend logs
- Build and Burn logs in `~/.buildandburn/` or your configured work directory 