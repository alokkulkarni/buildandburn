import { Router } from 'express';
import { ConfigReader } from '@backstage/config';
import { createRouter } from '@backstage/backend-common';
import { GithubWorkflowRun, TriggerWorkflowOptions, WorkflowRunLog } from '../types';
import { Octokit } from '@octokit/rest';
import { Logger } from 'winston';

interface RouterOptions {
  logger: Logger;
  config: ConfigReader;
}

// GitHub Actions workflow ID for the buildandburn workflow
const WORKFLOW_FILENAME = 'buildandburn.yml';

export async function createGithubActionsRouter(
  options: RouterOptions,
): Promise<Router> {
  const { logger, config } = options;
  const router = await createRouter({ logger });

  const getOctokit = async () => {
    const token = config.getString('github.token');
    return new Octokit({ auth: token });
  };

  // Get the workflow ID from a repository
  const getWorkflowId = async (octokit: Octokit, owner: string, repo: string): Promise<number> => {
    const { data: workflows } = await octokit.actions.listRepoWorkflows({
      owner,
      repo,
    });

    const buildAndBurnWorkflow = workflows.workflows.find(
      workflow => workflow.path.endsWith(WORKFLOW_FILENAME),
    );

    if (!buildAndBurnWorkflow) {
      throw new Error(`Workflow ${WORKFLOW_FILENAME} not found in ${owner}/${repo}`);
    }

    return buildAndBurnWorkflow.id;
  };

  // Get all workflow runs
  router.get('/workflow-runs', async (req, res) => {
    const { owner, repo } = req.query as { owner: string; repo: string };
    
    if (!owner || !repo) {
      return res.status(400).json({ error: 'owner and repo parameters are required' });
    }

    try {
      const octokit = await getOctokit();
      const workflowId = await getWorkflowId(octokit, owner, repo);

      const { data } = await octokit.actions.listWorkflowRuns({
        owner,
        repo,
        workflow_id: workflowId,
      });

      // Transform to our data model
      const runs: GithubWorkflowRun[] = data.workflow_runs.map(run => ({
        id: run.id,
        name: run.name || 'Build and Burn Workflow',
        status: run.status as any,
        conclusion: run.conclusion,
        url: run.html_url,
        created_at: run.created_at,
        updated_at: run.updated_at,
        head_branch: run.head_branch,
        repository: {
          name: repo,
          owner: {
            login: owner,
          },
        },
        event: run.event,
      }));

      res.json(runs);
    } catch (error) {
      logger.error(`Failed to get workflow runs for ${owner}/${repo}`, error);
      res.status(500).json({ error: error.message });
    }
  });

  // Get a specific workflow run
  router.get('/workflow-runs/:runId', async (req, res) => {
    const { runId } = req.params;
    const { owner, repo } = req.query as { owner: string; repo: string };
    
    if (!owner || !repo) {
      return res.status(400).json({ error: 'owner and repo parameters are required' });
    }

    try {
      const octokit = await getOctokit();
      
      const { data: run } = await octokit.actions.getWorkflowRun({
        owner,
        repo,
        run_id: parseInt(runId, 10),
      });

      // Transform to our data model
      const workflowRun: GithubWorkflowRun = {
        id: run.id,
        name: run.name || 'Build and Burn Workflow',
        status: run.status as any,
        conclusion: run.conclusion,
        url: run.html_url,
        created_at: run.created_at,
        updated_at: run.updated_at,
        head_branch: run.head_branch,
        repository: {
          name: repo,
          owner: {
            login: owner,
          },
        },
        event: run.event,
      };

      res.json(workflowRun);
    } catch (error) {
      logger.error(`Failed to get workflow run ${runId} for ${owner}/${repo}`, error);
      res.status(500).json({ error: error.message });
    }
  });

  // Get workflow run logs
  router.get('/workflow-runs/:runId/logs', async (req, res) => {
    const { runId } = req.params;
    const { owner, repo } = req.query as { owner: string; repo: string };
    
    if (!owner || !repo) {
      return res.status(400).json({ error: 'owner and repo parameters are required' });
    }

    try {
      const octokit = await getOctokit();
      
      // Get the logs URL
      const { data: runData } = await octokit.actions.getWorkflowRun({
        owner,
        repo,
        run_id: parseInt(runId, 10),
      });

      // Get the jobs for this run
      const { data: jobsData } = await octokit.actions.listJobsForWorkflowRun({
        owner,
        repo,
        run_id: parseInt(runId, 10),
      });

      // Collect logs from all jobs
      let allLogs = '';
      for (const job of jobsData.jobs) {
        try {
          const { data: logsData } = await octokit.actions.downloadJobLogsForWorkflowRun({
            owner,
            repo,
            job_id: job.id,
          });
          
          allLogs += `\n\n=== Job: ${job.name} (${job.status}) ===\n\n`;
          allLogs += logsData;
        } catch (e) {
          allLogs += `\n\nFailed to get logs for job ${job.name}: ${e.message}\n\n`;
        }
      }

      const logs: WorkflowRunLog = {
        id: parseInt(runId, 10),
        run_id: parseInt(runId, 10),
        content: allLogs || 'No logs available',
      };

      res.json(logs);
    } catch (error) {
      logger.error(`Failed to get logs for workflow run ${runId} for ${owner}/${repo}`, error);
      res.status(500).json({ 
        id: parseInt(runId, 10),
        run_id: parseInt(runId, 10),
        content: `Error: ${error.message}`,
      });
    }
  });

  // Trigger a workflow
  router.post('/workflow', async (req, res) => {
    const { 
      action, 
      repository, 
      manifestPath, 
      envId, 
      noGenerateK8s,
      dryRun 
    } = req.body as TriggerWorkflowOptions;

    if (!repository?.owner || !repository?.name || !action) {
      return res.status(400).json({ 
        error: 'repository.owner, repository.name, and action are required' 
      });
    }

    // Validate specific parameters
    if (action === 'up' && !manifestPath) {
      return res.status(400).json({ error: 'manifestPath is required for up action' });
    }

    if ((action === 'down' || action === 'info') && !envId) {
      return res.status(400).json({ error: 'envId is required for down/info actions' });
    }

    try {
      const octokit = await getOctokit();
      const { owner, name: repo } = repository;
      const workflowId = await getWorkflowId(octokit, owner, repo);

      // Prepare inputs based on action
      const inputs: Record<string, string> = {
        action,
      };

      if (action === 'up') {
        inputs.manifest_path = manifestPath!;
        
        if (noGenerateK8s) {
          inputs.no_generate_k8s = 'true';
        }
        
        if (dryRun) {
          inputs.dry_run = 'true';
        }
      }

      if (action === 'down' || action === 'info') {
        inputs.env_id = envId!;
      }

      // Trigger the workflow
      const { data } = await octokit.actions.createWorkflowDispatch({
        owner,
        repo,
        workflow_id: workflowId,
        ref: 'main', // Using main branch by default
        inputs,
      });

      // Get the latest run
      const { data: runsList } = await octokit.actions.listWorkflowRuns({
        owner,
        repo,
        workflow_id: workflowId,
        per_page: 1,
      });

      if (runsList.workflow_runs.length === 0) {
        return res.status(202).json({ 
          message: 'Workflow triggered successfully, but no runs found yet',
        });
      }

      const latestRun = runsList.workflow_runs[0];
      
      // Transform to our data model
      const workflowRun: GithubWorkflowRun = {
        id: latestRun.id,
        name: latestRun.name || 'Build and Burn Workflow',
        status: latestRun.status as any,
        conclusion: latestRun.conclusion,
        url: latestRun.html_url,
        created_at: latestRun.created_at,
        updated_at: latestRun.updated_at,
        head_branch: latestRun.head_branch,
        repository: {
          name: repo,
          owner: {
            login: owner,
          },
        },
        event: latestRun.event,
      };

      res.status(201).json(workflowRun);
    } catch (error) {
      logger.error(`Failed to trigger workflow in ${repository.owner}/${repository.name}`, error);
      res.status(500).json({ error: error.message });
    }
  });

  return router;
} 