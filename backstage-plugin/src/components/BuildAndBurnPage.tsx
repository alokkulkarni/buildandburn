import React, { useState, useEffect } from 'react';
import {
  Content,
  ContentHeader,
  SupportButton,
  Table,
  TableColumn,
  Progress,
  EmptyState,
  Button, 
  InfoCard,
  StructuredMetadataTable,
  Tabs,
  Tab,
} from '@backstage/core-components';
import { useApi, configApiRef } from '@backstage/core-plugin-api';
import { Grid, Box, Typography, makeStyles } from '@material-ui/core';
import Alert from '@material-ui/lab/Alert';
import { buildAndBurnApiRef } from '../api';
import { Environment, TriggerWorkflowOptions } from '../types';
import { ManifestDialog } from './ManifestDialog';
import { WorkflowRunsPanel } from './WorkflowRunsPanel';

const useStyles = makeStyles((theme) => ({
  tabPanel: {
    padding: theme.spacing(3),
  },
  statusActive: {
    color: theme.palette.success.main,
  },
  statusCreating: {
    color: theme.palette.info.main,
  },
  statusDestroying: {
    color: theme.palette.warning.main,
  },
  statusFailed: {
    color: theme.palette.error.main,
  },
}));

interface TabPanelProps {
  children?: React.ReactNode;
  index: any;
  value: any;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  const classes = useStyles();

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`env-tabpanel-${index}`}
      aria-labelledby={`env-tab-${index}`}
      {...other}
    >
      {value === index && <Box className={classes.tabPanel}>{children}</Box>}
    </div>
  );
}

type BuildAndBurnPageProps = {
  title?: string;
};

export const BuildAndBurnPage = ({ title = 'Build and Burn Environments' }: BuildAndBurnPageProps) => {
  const classes = useStyles();
  const buildAndBurnApi = useApi(buildAndBurnApiRef);
  const configApi = useApi(configApiRef);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [selectedEnv, setSelectedEnv] = useState<Environment | undefined>();
  const [isManifestDialogOpen, setIsManifestDialogOpen] = useState(false);
  const [tabValue, setTabValue] = useState(0);

  // For GitHub repository selection
  const [selectedRepo, setSelectedRepo] = useState<{ owner: string; name: string } | undefined>();

  const fetchEnvironments = async () => {
    setLoading(true);
    setError(undefined);
    try {
      const result = await buildAndBurnApi.listEnvironments();
      setEnvironments(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEnvironments();
  }, []);

  const createEnvironment = async (manifest: string) => {
    setLoading(true);
    setError(undefined);
    try {
      await buildAndBurnApi.createEnvironment(manifest);
      fetchEnvironments();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const destroyEnvironment = async (envId: string) => {
    setLoading(true);
    setError(undefined);
    try {
      await buildAndBurnApi.destroyEnvironment(envId);
      fetchEnvironments();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const triggerGithubWorkflow = async (options: TriggerWorkflowOptions) => {
    setLoading(true);
    setError(undefined);
    try {
      await buildAndBurnApi.triggerGithubWorkflow(options);
      setSelectedRepo(options.repository);
      setTabValue(1); // Switch to workflow tab
    } catch (err) {
      setError(`Failed to trigger GitHub workflow: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.ChangeEvent<{}>, newValue: number) => {
    setTabValue(newValue);
  };

  const getStatusClass = (status: string) => {
    switch(status) {
      case 'active': return classes.statusActive;
      case 'creating': return classes.statusCreating;
      case 'destroying': return classes.statusDestroying;
      case 'failed': return classes.statusFailed;
      default: return '';
    }
  };

  const columns: TableColumn<Environment>[] = [
    {
      title: 'ID',
      field: 'id',
      highlight: true,
    },
    {
      title: 'Name',
      field: 'name',
    },
    {
      title: 'Created',
      field: 'createdAt',
      type: 'datetime',
    },
    {
      title: 'Status',
      field: 'status',
      render: (row: Environment) => (
        <Typography className={getStatusClass(row.status)}>
          {row.status}
        </Typography>
      ),
    },
    {
      title: 'GitHub',
      render: (row: Environment) => (
        row.githubRepository ? (
          <span>{row.githubRepository.owner}/{row.githubRepository.name}</span>
        ) : (
          <span>-</span>
        )
      ),
    },
    {
      title: 'Actions',
      render: (row: Environment) => (
        <>
          <Button
            color="primary"
            variant="outlined"
            size="small"
            onClick={() => setSelectedEnv(row)}
          >
            Details
          </Button>
          &nbsp;
          {row.githubRepository && (
            <>
              <Button
                color="primary"
                variant="outlined"
                size="small"
                onClick={() => {
                  setSelectedRepo(row.githubRepository);
                  setTabValue(1); // Switch to workflow tab
                }}
              >
                Workflows
              </Button>
              &nbsp;
            </>
          )}
          <Button
            color="secondary"
            variant="outlined"
            size="small"
            onClick={() => {
              if (window.confirm(`Are you sure you want to destroy environment ${row.id}?`)) {
                if (row.githubRepository) {
                  triggerGithubWorkflow({
                    action: 'down',
                    repository: row.githubRepository,
                    envId: row.id,
                  });
                } else {
                  destroyEnvironment(row.id);
                }
              }
            }}
          >
            Destroy
          </Button>
        </>
      ),
    },
  ];

  return (
    <Content>
      <ContentHeader title={title}>
        <Button
          variant="contained"
          color="primary"
          onClick={() => setIsManifestDialogOpen(true)}
        >
          Create Environment
        </Button>
        <SupportButton>
          Create and manage build-and-burn environments for development and testing.
        </SupportButton>
      </ContentHeader>

      {error && <Alert severity="error">{error}</Alert>}

      {loading && <Progress />}

      <Tabs value={tabValue} onChange={handleTabChange} aria-label="environment tabs">
        <Tab label="Environments" id="env-tab-0" aria-controls="env-tabpanel-0" />
        <Tab 
          label="GitHub Workflows" 
          id="env-tab-1" 
          aria-controls="env-tabpanel-1" 
          disabled={!selectedRepo}
        />
      </Tabs>

      <TabPanel value={tabValue} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <InfoCard title="Environments">
              <Table
                columns={columns}
                data={environments}
                options={{
                  search: true,
                  paging: true,
                  pageSize: 10,
                  padding: 'dense',
                }}
                emptyContent={
                  <EmptyState
                    missing="data"
                    title="No environments found"
                    description="Create a new build-and-burn environment to get started."
                  />
                }
                actions={[
                  {
                    icon: 'refresh',
                    tooltip: 'Refresh',
                    isFreeAction: true,
                    onClick: () => fetchEnvironments(),
                  },
                ]}
              />
            </InfoCard>
          </Grid>

          {selectedEnv && (
            <Grid item xs={12}>
              <InfoCard
                title={`Environment Details: ${selectedEnv.id}`}
                action={
                  <Button
                    color="primary"
                    variant="outlined"
                    size="small"
                    onClick={() => setSelectedEnv(undefined)}
                  >
                    Close
                  </Button>
                }
              >
                <StructuredMetadataTable
                  metadata={{
                    ID: selectedEnv.id,
                    Name: selectedEnv.name,
                    Created: selectedEnv.createdAt,
                    Status: selectedEnv.status,
                    Repository: selectedEnv.githubRepository 
                      ? `${selectedEnv.githubRepository.owner}/${selectedEnv.githubRepository.name}`
                      : 'None',
                    Services: selectedEnv.services?.map(svc => `${svc.name} (${svc.endpoint})`).join(', ') || 'No services',
                    Database: selectedEnv.database?.endpoint || 'None',
                    Queue: selectedEnv.messageQueue?.endpoint || 'None',
                  }}
                />
              </InfoCard>
            </Grid>
          )}
        </Grid>
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        {selectedRepo && (
          <WorkflowRunsPanel repository={selectedRepo} refreshInterval={5000} />
        )}
      </TabPanel>

      <ManifestDialog
        open={isManifestDialogOpen}
        onClose={() => setIsManifestDialogOpen(false)}
        onSubmit={manifest => {
          createEnvironment(manifest);
          setIsManifestDialogOpen(false);
        }}
        onTriggerGithubWorkflow={options => {
          triggerGithubWorkflow(options);
          setIsManifestDialogOpen(false);
        }}
      />
    </Content>
  );
}; 