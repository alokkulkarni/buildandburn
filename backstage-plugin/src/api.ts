import { createApiRef } from '@backstage/core-plugin-api';
import { Environment } from './types';

export interface BuildAndBurnApi {
  listEnvironments(): Promise<Environment[]>;
  getEnvironment(id: string): Promise<Environment>;
  createEnvironment(manifest: string): Promise<Environment>;
  destroyEnvironment(id: string): Promise<void>;
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
} 