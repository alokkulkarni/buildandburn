import React, { useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
  Grid,
  FormControlLabel,
  Checkbox,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Typography,
  Tabs,
  Tab,
  Box,
} from '@material-ui/core';
import { TriggerWorkflowOptions } from '../types';

const DEFAULT_MANIFEST = `name: my-project
region: eu-west-2

# Services to deploy
services:
  - name: backend-api
    image: my-registry/backend:latest
    port: 8080
    replicas: 1
  
  - name: frontend
    image: my-registry/frontend:latest
    port: 3000
    replicas: 1

# Infrastructure dependencies
dependencies:
  - type: database
    provider: postgres
    version: "13"
    storage: 20
    instance_class: db.t3.small
  
  - type: queue
    provider: rabbitmq
    version: "3.9.16"
    instance_class: mq.t3.micro
`;

interface TabPanelProps {
  children?: React.ReactNode;
  index: any;
  value: any;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && <Box p={3}>{children}</Box>}
    </div>
  );
}

export interface ManifestDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (manifest: string) => void;
  onTriggerGithubWorkflow: (options: TriggerWorkflowOptions) => void;
}

export const ManifestDialog = ({ 
  open, 
  onClose, 
  onSubmit,
  onTriggerGithubWorkflow 
}: ManifestDialogProps) => {
  const [manifest, setManifest] = useState(DEFAULT_MANIFEST);
  const [tabValue, setTabValue] = useState(0);
  
  // GitHub Actions options
  const [repoOwner, setRepoOwner] = useState('');
  const [repoName, setRepoName] = useState('');
  const [action, setAction] = useState<'up' | 'down' | 'info' | 'list'>('up');
  const [manifestPath, setManifestPath] = useState('manifest.yaml');
  const [envId, setEnvId] = useState('');
  const [noGenerateK8s, setNoGenerateK8s] = useState(false);
  const [dryRun, setDryRun] = useState(false);

  const handleSubmitManifest = () => {
    onSubmit(manifest);
    onClose();
  };

  const handleTriggerWorkflow = () => {
    onTriggerGithubWorkflow({
      action,
      repository: {
        owner: repoOwner,
        name: repoName,
      },
      manifestPath: action === 'up' ? manifestPath : undefined,
      envId: action === 'down' || action === 'info' ? envId : undefined,
      noGenerateK8s: action === 'up' ? noGenerateK8s : undefined,
      dryRun: action === 'up' ? dryRun : undefined,
    });
    onClose();
  };

  const handleTabChange = (event: React.ChangeEvent<{}>, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby="manifest-dialog-title"
      fullWidth
      maxWidth="md"
    >
      <DialogTitle id="manifest-dialog-title">Build and Burn Environment</DialogTitle>
      <DialogContent>
        <Tabs value={tabValue} onChange={handleTabChange} aria-label="workflow options tabs">
          <Tab label="Direct Manifest" />
          <Tab label="GitHub Actions" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <DialogContentText>
            Define your environment in YAML format. Include services to deploy and infrastructure dependencies.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            id="manifest"
            label="Manifest"
            fullWidth
            multiline
            rows={20}
            value={manifest}
            onChange={(e) => setManifest(e.target.value)}
            variant="outlined"
          />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <DialogContentText>
            Trigger a GitHub Actions workflow to create or manage your environment.
          </DialogContentText>
          
          <Grid container spacing={3}>
            <Grid item xs={6}>
              <TextField
                margin="dense"
                id="repoOwner"
                label="Repository Owner"
                fullWidth
                value={repoOwner}
                onChange={(e) => setRepoOwner(e.target.value)}
                variant="outlined"
                required
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                margin="dense"
                id="repoName"
                label="Repository Name"
                fullWidth
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
                variant="outlined"
                required
              />
            </Grid>
            <Grid item xs={12}>
              <FormControl variant="outlined" fullWidth margin="dense">
                <InputLabel id="action-label">Action</InputLabel>
                <Select
                  labelId="action-label"
                  id="action"
                  value={action}
                  onChange={(e) => setAction(e.target.value as any)}
                  label="Action"
                >
                  <MenuItem value="up">Create Environment (up)</MenuItem>
                  <MenuItem value="down">Destroy Environment (down)</MenuItem>
                  <MenuItem value="info">Get Environment Info (info)</MenuItem>
                  <MenuItem value="list">List Environments (list)</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {action === 'up' && (
              <>
                <Grid item xs={12}>
                  <TextField
                    margin="dense"
                    id="manifestPath"
                    label="Manifest Path"
                    fullWidth
                    value={manifestPath}
                    onChange={(e) => setManifestPath(e.target.value)}
                    variant="outlined"
                    helperText="Path to the manifest YAML file in the repository"
                  />
                </Grid>
                <Grid item xs={6}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={noGenerateK8s}
                        onChange={(e) => setNoGenerateK8s(e.target.checked)}
                        name="noGenerateK8s"
                        color="primary"
                      />
                    }
                    label="Skip K8s Generation"
                  />
                </Grid>
                <Grid item xs={6}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={dryRun}
                        onChange={(e) => setDryRun(e.target.checked)}
                        name="dryRun"
                        color="primary"
                      />
                    }
                    label="Dry Run"
                  />
                </Grid>
              </>
            )}

            {(action === 'down' || action === 'info') && (
              <Grid item xs={12}>
                <TextField
                  margin="dense"
                  id="envId"
                  label="Environment ID"
                  fullWidth
                  value={envId}
                  onChange={(e) => setEnvId(e.target.value)}
                  variant="outlined"
                  required
                  helperText="ID of the environment to manage"
                />
              </Grid>
            )}
          </Grid>
        </TabPanel>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="primary">
          Cancel
        </Button>
        {tabValue === 0 ? (
          <Button onClick={handleSubmitManifest} color="primary" variant="contained">
            Create
          </Button>
        ) : (
          <Button 
            onClick={handleTriggerWorkflow} 
            color="primary" 
            variant="contained"
            disabled={!repoOwner || !repoName || (action === 'up' && !manifestPath) || ((action === 'down' || action === 'info') && !envId)}
          >
            Trigger Workflow
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}; 