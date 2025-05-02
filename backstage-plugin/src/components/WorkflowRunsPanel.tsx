import React, { useState, useEffect } from 'react';
import {
  Table,
  TableColumn,
  Progress,
  InfoCard,
  Link,
  StructuredMetadataTable,
} from '@backstage/core-components';
import { useApi } from '@backstage/core-plugin-api';
import { Grid, Button, Typography, Paper, makeStyles } from '@material-ui/core';
import Alert from '@material-ui/lab/Alert';
import { buildAndBurnApiRef } from '../api';
import { GithubWorkflowRun, WorkflowRunLog } from '../types';

const useStyles = makeStyles((theme) => ({
  logContainer: {
    backgroundColor: theme.palette.background.default,
    color: theme.palette.text.primary,
    fontFamily: 'monospace',
    padding: theme.spacing(2),
    maxHeight: '500px',
    overflowY: 'auto',
    whiteSpace: 'pre-wrap',
    fontSize: '0.8rem',
  },
  statusRunning: {
    color: theme.palette.info.main,
  },
  statusSuccess: {
    color: theme.palette.success.main,
  },
  statusFailure: {
    color: theme.palette.error.main,
  },
  statusWaiting: {
    color: theme.palette.grey[500],
  },
}));

interface WorkflowRunsPanelProps {
  repository: {
    owner: string;
    name: string;
  };
  refreshInterval?: number; // in milliseconds
}

export const WorkflowRunsPanel = ({
  repository,
  refreshInterval = 10000, // default to 10 seconds
}: WorkflowRunsPanelProps) => {
  const classes = useStyles();
  const buildAndBurnApi = useApi(buildAndBurnApiRef);
  const [workflowRuns, setWorkflowRuns] = useState<GithubWorkflowRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<GithubWorkflowRun | undefined>();
  const [runLogs, setRunLogs] = useState<WorkflowRunLog | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const fetchWorkflowRuns = async () => {
    try {
      setLoading(true);
      setError(undefined);
      const runs = await buildAndBurnApi.getWorkflowRuns(repository);
      setWorkflowRuns(runs);
      
      // If there's a selected run, update its status
      if (selectedRun) {
        const updatedRun = runs.find(run => run.id === selectedRun.id);
        if (updatedRun) {
          setSelectedRun(updatedRun);
        }
      }
    } catch (err) {
      setError(`Failed to fetch workflow runs: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchWorkflowRunLogs = async (runId: number) => {
    try {
      setLoading(true);
      setError(undefined);
      const logs = await buildAndBurnApi.getWorkflowRunLogs(runId, repository);
      setRunLogs(logs);
    } catch (err) {
      setError(`Failed to fetch workflow run logs: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchWorkflowRuns();
  }, [repository.owner, repository.name]);

  // Set up polling for active workflow runs
  useEffect(() => {
    const hasActiveRuns = workflowRuns.some(
      run => run.status === 'queued' || run.status === 'in_progress'
    );

    // If there are active runs or a selected run is active, poll for updates
    if (hasActiveRuns || 
        (selectedRun && 
         (selectedRun.status === 'queued' || selectedRun.status === 'in_progress'))) {
      const intervalId = setInterval(fetchWorkflowRuns, refreshInterval);
      return () => clearInterval(intervalId);
    }
    
    return undefined;
  }, [workflowRuns, selectedRun, refreshInterval]);

  // Fetch logs when a run is selected
  useEffect(() => {
    if (selectedRun) {
      fetchWorkflowRunLogs(selectedRun.id);
    } else {
      setRunLogs(null);
    }
  }, [selectedRun]);

  const getStatusIcon = (status: string, conclusion: string | null) => {
    if (status === 'queued') return '⏳';
    if (status === 'in_progress') return '🔄';
    if (status === 'completed') {
      if (conclusion === 'success') return '✅';
      if (conclusion === 'failure') return '❌';
      return '⚠️';
    }
    return '❓';
  };

  const getStatusClass = (status: string, conclusion: string | null) => {
    if (status === 'queued') return classes.statusWaiting;
    if (status === 'in_progress') return classes.statusRunning;
    if (status === 'completed') {
      if (conclusion === 'success') return classes.statusSuccess;
      if (conclusion === 'failure') return classes.statusFailure;
      return '';
    }
    return '';
  };

  const columns: TableColumn<GithubWorkflowRun>[] = [
    {
      title: 'ID',
      field: 'id',
    },
    {
      title: 'Name',
      field: 'name',
    },
    {
      title: 'Status',
      render: (row: GithubWorkflowRun) => (
        <Typography className={getStatusClass(row.status, row.conclusion)}>
          {getStatusIcon(row.status, row.conclusion)} {row.status} {row.conclusion && `(${row.conclusion})`}
        </Typography>
      ),
    },
    {
      title: 'Created',
      field: 'created_at',
      type: 'datetime',
    },
    {
      title: 'Actions',
      render: (row: GithubWorkflowRun) => (
        <>
          <Button
            color="primary"
            variant="outlined"
            size="small"
            onClick={() => setSelectedRun(row)}
          >
            View Logs
          </Button>
          &nbsp;
          <Button
            component={Link}
            to={row.url}
            color="primary"
            variant="outlined"
            size="small"
          >
            Open in GitHub
          </Button>
        </>
      ),
    },
  ];

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <InfoCard
          title={`GitHub Workflow Runs - ${repository.owner}/${repository.name}`}
          action={
            <Button
              color="primary"
              onClick={fetchWorkflowRuns}
              disabled={loading}
            >
              Refresh
            </Button>
          }
        >
          {error && <Alert severity="error">{error}</Alert>}
          {loading && <Progress />}

          <Table
            columns={columns}
            data={workflowRuns}
            options={{
              paging: true,
              pageSize: 5,
              search: false,
              sorting: true,
              padding: 'dense',
            }}
            emptyContent={
              <Typography variant="body1">No workflow runs found</Typography>
            }
          />
        </InfoCard>
      </Grid>

      {selectedRun && (
        <Grid item xs={12}>
          <InfoCard
            title={`Run Details: ${selectedRun.name} (${selectedRun.id})`}
            action={
              <Button
                color="primary"
                variant="outlined"
                size="small"
                onClick={() => setSelectedRun(undefined)}
              >
                Close
              </Button>
            }
          >
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <StructuredMetadataTable
                  metadata={{
                    ID: selectedRun.id,
                    Name: selectedRun.name,
                    Status: `${selectedRun.status} ${selectedRun.conclusion ? `(${selectedRun.conclusion})` : ''}`,
                    Branch: selectedRun.head_branch,
                    Event: selectedRun.event,
                    Created: new Date(selectedRun.created_at).toLocaleString(),
                    Updated: new Date(selectedRun.updated_at).toLocaleString(),
                  }}
                />
              </Grid>

              <Grid item xs={12}>
                <Typography variant="h6">Logs</Typography>
                {loading && <Progress />}
                {runLogs ? (
                  <Paper className={classes.logContainer}>
                    {runLogs.content}
                  </Paper>
                ) : (
                  <Typography variant="body2">No logs available</Typography>
                )}
              </Grid>
            </Grid>
          </InfoCard>
        </Grid>
      )}
    </Grid>
  );
}; 