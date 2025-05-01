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
  StructuredMetadataTable
} from '@backstage/core-components';
import { useApi, configApiRef } from '@backstage/core-plugin-api';
import { Grid } from '@material-ui/core';
import Alert from '@material-ui/lab/Alert';
import { buildAndBurnApiRef } from '../api';
import { Environment } from '../types';
import { ManifestDialog } from './ManifestDialog';

type BuildAndBurnPageProps = {
  title?: string;
};

export const BuildAndBurnPage = ({ title = 'Build and Burn Environments' }: BuildAndBurnPageProps) => {
  const buildAndBurnApi = useApi(buildAndBurnApiRef);
  const configApi = useApi(configApiRef);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [selectedEnv, setSelectedEnv] = useState<Environment | undefined>();
  const [isManifestDialogOpen, setIsManifestDialogOpen] = useState(false);

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
        <span style={{ color: row.status === 'active' ? 'green' : 'grey' }}>
          {row.status}
        </span>
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
          <Button
            color="secondary"
            variant="outlined"
            size="small"
            onClick={() => {
              if (window.confirm(`Are you sure you want to destroy environment ${row.id}?`)) {
                destroyEnvironment(row.id);
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
                  Service: selectedEnv.services?.map(svc => `${svc.name} (${svc.endpoint})`).join(', ') || 'No services',
                  Database: selectedEnv.database?.endpoint || 'None',
                  Queue: selectedEnv.messageQueue?.endpoint || 'None',
                }}
              />
            </InfoCard>
          </Grid>
        )}
      </Grid>

      <ManifestDialog
        open={isManifestDialogOpen}
        onClose={() => setIsManifestDialogOpen(false)}
        onSubmit={manifest => {
          createEnvironment(manifest);
          setIsManifestDialogOpen(false);
        }}
      />
    </Content>
  );
}; 