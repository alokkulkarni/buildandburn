import { Router } from 'express';
import { createServiceBuilder, loadBackendConfig } from '@backstage/backend-common';
import { ConfigReader } from '@backstage/config';
import { Logger } from 'winston';
import { createGithubActionsRouter } from './githubActionsApi';
import { Environment } from '../types';

// Sample data for development
const SAMPLE_ENVIRONMENTS: Environment[] = [
  {
    id: 'sample-env-1',
    name: 'Sample Environment 1',
    createdAt: new Date().toISOString(),
    status: 'active',
    githubRepository: {
      owner: 'sample-org',
      name: 'sample-repo',
    },
    services: [
      {
        name: 'frontend',
        endpoint: 'https://sample-frontend.example.com',
      },
      {
        name: 'backend',
        endpoint: 'https://sample-backend.example.com',
      },
    ],
    database: {
      endpoint: 'sample-db.example.com:5432',
      username: 'admin',
    },
  },
];

export interface RouterOptions {
  logger: Logger;
  config: ConfigReader;
}

export async function createRouter(
  options: RouterOptions,
): Promise<Router> {
  const { logger, config } = options;
  const router = Router();

  // GitHub Actions integration
  const githubActionsRouter = await createGithubActionsRouter(options);
  router.use('/github-actions', githubActionsRouter);

  // Basic environment CRUD operations
  router.get('/environments', (req, res) => {
    res.json(SAMPLE_ENVIRONMENTS);
  });

  router.get('/environments/:id', (req, res) => {
    const env = SAMPLE_ENVIRONMENTS.find(e => e.id === req.params.id);
    if (!env) {
      res.status(404).json({ error: 'Environment not found' });
      return;
    }
    res.json(env);
  });

  router.post('/environments', (req, res) => {
    const { manifest } = req.body;
    if (!manifest) {
      res.status(400).json({ error: 'Manifest is required' });
      return;
    }

    // In a real implementation, this would call the CLI
    // For now, we'll just add a sample environment
    const newEnv: Environment = {
      id: `env-${Date.now()}`,
      name: `Environment ${Date.now()}`,
      createdAt: new Date().toISOString(),
      status: 'active',
      services: [
        {
          name: 'sample-service',
          endpoint: 'https://sample-service.example.com',
        },
      ],
    };

    SAMPLE_ENVIRONMENTS.push(newEnv);
    res.status(201).json(newEnv);
  });

  router.delete('/environments/:id', (req, res) => {
    const index = SAMPLE_ENVIRONMENTS.findIndex(e => e.id === req.params.id);
    if (index < 0) {
      res.status(404).json({ error: 'Environment not found' });
      return;
    }

    // In a real implementation, this would call the CLI
    // For now, we'll just remove from our sample array
    SAMPLE_ENVIRONMENTS.splice(index, 1);
    res.status(204).send();
  });

  return router;
}

export async function createBackendModule() {
  const config = await loadBackendConfig({
    argv: process.argv,
    logger: console,
  });

  const service = createServiceBuilder({
    logger: console,
    config,
  })
    .loadConfig({
      configPaths: [
        {
          configPath: 'app-config.yaml',
          legacy: true,
        },
      ],
    })
    .addRouter('/api/buildandburn', await createRouter({
      logger: console,
      config: config,
    }));

  return await service.start({ port: 7007 });
}

if (require.main === module) {
  createBackendModule().catch(error => {
    console.error(`Backend failed to start up, ${error}`);
    process.exit(1);
  });
} 