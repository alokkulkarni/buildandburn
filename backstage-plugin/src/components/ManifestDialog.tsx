import React, { useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
} from '@material-ui/core';

const DEFAULT_MANIFEST = `name: my-project
region: us-west-2

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

export interface ManifestDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (manifest: string) => void;
}

export const ManifestDialog = ({ open, onClose, onSubmit }: ManifestDialogProps) => {
  const [manifest, setManifest] = useState(DEFAULT_MANIFEST);

  const handleSubmit = () => {
    onSubmit(manifest);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby="manifest-dialog-title"
      fullWidth
      maxWidth="md"
    >
      <DialogTitle id="manifest-dialog-title">Create Build and Burn Environment</DialogTitle>
      <DialogContent>
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
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="primary">
          Cancel
        </Button>
        <Button onClick={handleSubmit} color="primary" variant="contained">
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
}; 