// Build and Burn VS Code Extension

const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const yaml = require('js-yaml');

function executeCommand(command) {
  return new Promise((resolve, reject) => {
    exec(command, (error, stdout, stderr) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(stdout.trim());
    });
  });
}

// Show output channel
let outputChannel;

function showOutput(text) {
  if (!outputChannel) {
    outputChannel = vscode.window.createOutputChannel('Build and Burn');
  }
  outputChannel.appendLine(text);
  outputChannel.show();
}

async function createEnvironment() {
  try {
    // Find manifest file
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
      throw new Error('No workspace folder open');
    }
    
    const workspaceRoot = workspaceFolders[0].uri.fsPath;
    
    // Check for manifest file or prompt to select one
    const manifestFiles = ['manifest.yaml', 'manifest.yml', 'buildandburn.yaml', 'buildandburn.yml'];
    let manifestPath = null;
    
    for (const fileName of manifestFiles) {
      const filePath = path.join(workspaceRoot, fileName);
      if (fs.existsSync(filePath)) {
        manifestPath = filePath;
        break;
      }
    }
    
    if (!manifestPath) {
      // Prompt for manifest file
      const result = await vscode.window.showOpenDialog({
        canSelectMany: false,
        filters: {
          'YAML files': ['yaml', 'yml']
        },
        title: 'Select Build and Burn Manifest File'
      });
      
      if (result && result.length > 0) {
        manifestPath = result[0].fsPath;
      } else {
        throw new Error('No manifest file selected');
      }
    }
    
    showOutput(`Using manifest file: ${manifestPath}`);
    
    // Execute command
    const cmd = `buildandburn up --manifest "${manifestPath}"`;
    showOutput(`Executing: ${cmd}`);
    
    // Set up progress notification
    vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: 'Creating Build and Burn Environment',
      cancellable: false
    }, async (progress) => {
      progress.report({ message: 'Provisioning infrastructure...' });
      
      try {
        const result = await executeCommand(cmd);
        showOutput(result);
        
        // Extract environment ID from output
        const envIdMatch = result.match(/Environment ID: ([a-z0-9]+)/);
        if (envIdMatch && envIdMatch[1]) {
          const envId = envIdMatch[1];
          
          // Store environment ID in workspace state
          context.workspaceState.update('buildAndBurnEnvId', envId);
          
          vscode.window.showInformationMessage(`Build and Burn environment created with ID: ${envId}`);
        } else {
          vscode.window.showInformationMessage('Build and Burn environment created');
        }
      } catch (error) {
        showOutput(`Error: ${error.message}`);
        vscode.window.showErrorMessage(`Failed to create environment: ${error.message}`);
      }
    });
  } catch (error) {
    showOutput(`Error: ${error.message}`);
    vscode.window.showErrorMessage(`Failed to create environment: ${error.message}`);
  }
}

async function destroyEnvironment(context) {
  try {
    // Get environment ID
    let envId = context.workspaceState.get('buildAndBurnEnvId');
    
    if (!envId) {
      // Prompt for environment ID
      envId = await vscode.window.showInputBox({
        prompt: 'Enter the environment ID to destroy',
        placeHolder: 'e.g., a1b2c3d4'
      });
    }
    
    if (!envId) {
      throw new Error('No environment ID provided');
    }
    
    // Confirm destruction
    const confirmResult = await vscode.window.showWarningMessage(
      `Are you sure you want to destroy the environment ${envId}?`,
      { modal: true },
      'Yes',
      'No'
    );
    
    if (confirmResult !== 'Yes') {
      showOutput('Environment destruction cancelled');
      return;
    }
    
    // Execute command
    const cmd = `buildandburn down --env-id ${envId} --force`;
    showOutput(`Executing: ${cmd}`);
    
    // Set up progress notification
    vscode.window.withProgress({
      location: vscode.ProgressLocation.Notification,
      title: 'Destroying Build and Burn Environment',
      cancellable: false
    }, async (progress) => {
      try {
        const result = await executeCommand(cmd);
        showOutput(result);
        
        // Clear environment ID from workspace state
        context.workspaceState.update('buildAndBurnEnvId', undefined);
        
        vscode.window.showInformationMessage(`Build and Burn environment ${envId} destroyed`);
      } catch (error) {
        showOutput(`Error: ${error.message}`);
        vscode.window.showErrorMessage(`Failed to destroy environment: ${error.message}`);
      }
    });
  } catch (error) {
    showOutput(`Error: ${error.message}`);
    vscode.window.showErrorMessage(`Failed to destroy environment: ${error.message}`);
  }
}

async function getEnvironmentInfo(context) {
  try {
    // Get environment ID
    let envId = context.workspaceState.get('buildAndBurnEnvId');
    
    if (!envId) {
      // Prompt for environment ID
      envId = await vscode.window.showInputBox({
        prompt: 'Enter the environment ID to get information',
        placeHolder: 'e.g., a1b2c3d4'
      });
    }
    
    if (!envId) {
      throw new Error('No environment ID provided');
    }
    
    // Execute command
    const cmd = `buildandburn info --env-id ${envId}`;
    showOutput(`Executing: ${cmd}`);
    
    const result = await executeCommand(cmd);
    showOutput(result);
    
    // Show information in a webview panel
    const panel = vscode.window.createWebviewPanel(
      'buildAndBurnInfo',
      `Build and Burn: ${envId}`,
      vscode.ViewColumn.One,
      { enableScripts: true }
    );
    
    // Format output as HTML
    panel.webview.html = `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Build and Burn Environment Info</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 20px; }
          pre { background-color: #f5f5f5; padding: 10px; overflow: auto; }
          h1 { color: #333; }
          .info-item { margin-bottom: 20px; }
          .info-title { font-weight: bold; margin-bottom: 5px; }
        </style>
      </head>
      <body>
        <h1>Build and Burn Environment: ${envId}</h1>
        <pre>${result}</pre>
      </body>
      </html>
    `;
  } catch (error) {
    showOutput(`Error: ${error.message}`);
    vscode.window.showErrorMessage(`Failed to get environment info: ${error.message}`);
  }
}

async function createManifest() {
  try {
    // Create a new manifest file
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
      throw new Error('No workspace folder open');
    }
    
    const workspaceRoot = workspaceFolders[0].uri.fsPath;
    const manifestPath = path.join(workspaceRoot, 'manifest.yaml');
    
    // Check if file already exists
    if (fs.existsSync(manifestPath)) {
      const confirmResult = await vscode.window.showWarningMessage(
        'Manifest file already exists. Do you want to overwrite it?',
        { modal: true },
        'Yes',
        'No'
      );
      
      if (confirmResult !== 'Yes') {
        showOutput('Manifest creation cancelled');
        return;
      }
    }
    
    // Create sample manifest content
    const manifestContent = `name: ${path.basename(workspaceRoot)}
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
    
    // Write manifest file
    fs.writeFileSync(manifestPath, manifestContent);
    
    // Open the file in editor
    const document = await vscode.workspace.openTextDocument(manifestPath);
    await vscode.window.showTextDocument(document);
    
    vscode.window.showInformationMessage('Created new Build and Burn manifest file');
  } catch (error) {
    showOutput(`Error: ${error.message}`);
    vscode.window.showErrorMessage(`Failed to create manifest: ${error.message}`);
  }
}

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  showOutput('Build and Burn extension activated');
  
  let createCmd = vscode.commands.registerCommand('buildandburn.createEnvironment', () => {
    createEnvironment(context);
  });
  
  let destroyCmd = vscode.commands.registerCommand('buildandburn.destroyEnvironment', () => {
    destroyEnvironment(context);
  });
  
  let infoCmd = vscode.commands.registerCommand('buildandburn.getEnvironmentInfo', () => {
    getEnvironmentInfo(context);
  });
  
  let createManifestCmd = vscode.commands.registerCommand('buildandburn.createManifest', createManifest);
  
  context.subscriptions.push(createCmd);
  context.subscriptions.push(destroyCmd);
  context.subscriptions.push(infoCmd);
  context.subscriptions.push(createManifestCmd);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate
}; 