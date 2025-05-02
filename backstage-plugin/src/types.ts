export interface Service {
  name: string;
  endpoint: string;
}

export interface Database {
  endpoint: string;
  username?: string;
}

export interface MessageQueue {
  endpoint: string;
  username?: string;
}

export interface GithubWorkflowRun {
  id: number;
  name: string;
  status: 'queued' | 'in_progress' | 'completed' | 'failure' | 'success';
  conclusion: string | null;
  url: string;
  created_at: string;
  updated_at: string;
  head_branch: string;
  repository: {
    name: string;
    owner: {
      login: string;
    };
  };
  event: string;
}

export interface WorkflowRunLog {
  id: number;
  run_id: number;
  content: string;
}

export interface TriggerWorkflowOptions {
  action: 'up' | 'down' | 'info' | 'list';
  repository: {
    owner: string;
    name: string;
  };
  manifestPath?: string;
  envId?: string;
  noGenerateK8s?: boolean;
  dryRun?: boolean;
}

export interface Environment {
  id: string;
  name: string;
  createdAt: string;
  status: 'active' | 'creating' | 'destroying' | 'failed';
  githubRepository?: {
    owner: string;
    name: string;
  };
  latestWorkflowRun?: GithubWorkflowRun;
  services?: Service[];
  database?: Database;
  messageQueue?: MessageQueue;
} 