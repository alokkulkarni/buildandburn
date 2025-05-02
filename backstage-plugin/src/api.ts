import { createApiRef } from '@backstage/core-plugin-api';
import { Environment, GithubWorkflowRun, TriggerWorkflowOptions, WorkflowRunLog } from './types';

export interface BuildAndBurnApi {
  listEnvironments(): Promise<Environment[]>;
  getEnvironment(id: string): Promise<Environment>;
  createEnvironment(manifest: string): Promise<Environment>;
  destroyEnvironment(id: string): Promise<void>;
  
  // GitHub Actions integration
  triggerGithubWorkflow(options: TriggerWorkflowOptions): Promise<GithubWorkflowRun>;
  getWorkflowRuns(repo: { owner: string, name: string }): Promise<GithubWorkflowRun[]>;
  getWorkflowRunLogs(runId: number, repo: { owner: string, name: string }): Promise<WorkflowRunLog>;
  getWorkflowRunStatus(runId: number, repo: { owner: string, name: string }): Promise<GithubWorkflowRun>;
}

export const buildAndBurnApiRef = createApiRef<BuildAndBurnApi>({
  id: 'plugin.buildandburn.api',
});

export class BuildAndBurnClient implements BuildAndBurnApi {
  private readonly baseUrl: string;

  constructor(options: { baseUrl: string }) {
    this.baseUrl = options.baseUrl;
  }

  async listEnvironments(): Promise<Environment[]> {
    const response = await fetch(`${this.baseUrl}/environments`);
    if (!response.ok) {
      throw new Error(`Failed to list environments: ${response.statusText}`);
    }
    return await response.json();
  }

  async getEnvironment(id: string): Promise<Environment> {
    const response = await fetch(`${this.baseUrl}/environments/${id}`);
    if (!response.ok) {
      throw new Error(`Failed to get environment: ${response.statusText}`);
    }
    return await response.json();
  }

  async createEnvironment(manifest: string): Promise<Environment> {
    const response = await fetch(`${this.baseUrl}/environments`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ manifest }),
    });
    if (!response.ok) {
      throw new Error(`Failed to create environment: ${response.statusText}`);
    }
    return await response.json();
  }

  async destroyEnvironment(id: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/environments/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Failed to destroy environment: ${response.statusText}`);
    }
  }

  // GitHub Actions integration
  async triggerGithubWorkflow(options: TriggerWorkflowOptions): Promise<GithubWorkflowRun> {
    const { action, repository, manifestPath, envId, noGenerateK8s, dryRun } = options;
    
    const response = await fetch(`${this.baseUrl}/github-actions/workflow`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action,
        repository,
        manifestPath,
        envId,
        noGenerateK8s,
        dryRun,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to trigger GitHub workflow: ${response.statusText}`);
    }
    
    return await response.json();
  }

  async getWorkflowRuns(repo: { owner: string, name: string }): Promise<GithubWorkflowRun[]> {
    const response = await fetch(
      `${this.baseUrl}/github-actions/workflow-runs?owner=${repo.owner}&repo=${repo.name}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch workflow runs: ${response.statusText}`);
    }
    
    return await response.json();
  }

  async getWorkflowRunLogs(runId: number, repo: { owner: string, name: string }): Promise<WorkflowRunLog> {
    const response = await fetch(
      `${this.baseUrl}/github-actions/workflow-runs/${runId}/logs?owner=${repo.owner}&repo=${repo.name}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch workflow run logs: ${response.statusText}`);
    }
    
    return await response.json();
  }

  async getWorkflowRunStatus(runId: number, repo: { owner: string, name: string }): Promise<GithubWorkflowRun> {
    const response = await fetch(
      `${this.baseUrl}/github-actions/workflow-runs/${runId}?owner=${repo.owner}&repo=${repo.name}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch workflow run status: ${response.statusText}`);
    }
    
    return await response.json();
  }
} 