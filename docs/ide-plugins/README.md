# Build and Burn IDE Plugins

Build and Burn environments can be managed directly from your IDE with our plugins. Currently, we support Visual Studio Code, with plans to support other popular IDEs in the future.

## Visual Studio Code Extension

### Installation

#### Method 1: Install from VSIX file

1. Download the latest `buildandburn-0.1.0.vsix` file from the [releases page](https://github.com/yourusername/buildandburn/releases)
2. Open VS Code
3. Go to Extensions view (Ctrl+Shift+X / Cmd+Shift+X)
4. Click on the "..." menu in the top-right corner of the Extensions panel
5. Select "Install from VSIX..."
6. Browse to the downloaded VSIX file and select it

#### Method 2: Build and Install from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/buildandburn.git
   ```

2. Navigate to the VS Code extension directory:
   ```bash
   cd buildandburn/ide-plugins/vscode
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Package the extension:
   ```bash
   npm run package
   ```

5. Install the packaged extension:
   ```bash
   code --install-extension buildandburn-0.1.0.vsix
   ```

### Prerequisites

Before using the extension, ensure you have the following installed:

1. **Build and Burn CLI**: Install using `pip install buildandburn`
2. **AWS CLI**: For managing AWS resources
3. **Terraform**: For provisioning infrastructure
4. **kubectl**: For interacting with Kubernetes clusters
5. **Helm**: For deploying applications to Kubernetes

AWS credentials should be configured in your environment using one of the following methods:
- AWS CLI: `aws configure`
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- AWS profile: `~/.aws/credentials`

### Usage

The extension adds the following commands to VS Code, accessible via the Command Palette (Ctrl+Shift+P / Cmd+Shift+P):

- **Build and Burn: Create Environment**: Create a new environment from a manifest file
- **Build and Burn: Destroy Environment**: Destroy an existing environment
- **Build and Burn: Get Environment Info**: View details about an existing environment
- **Build and Burn: List Environments**: List all environments
- **Build and Burn: Create Manifest File**: Generate a new manifest file template

#### Creating an Environment

1. Open your project in VS Code
2. Create a manifest file (`manifest.yaml`) or use the "Create Manifest File" command
3. Customize the manifest with your services and dependencies
4. Run the "Create Environment" command
5. Select any additional options:
   - **Dry Run**: Validate without creating resources
   - **Skip K8s Generation**: Use custom Kubernetes resources
6. The extension will use the manifest file to create a new environment
7. Once completed, you'll see the environment details in the output panel

#### Environment Commands

When you run the "Create Environment" command, the extension executes:

```bash
buildandburn up --manifest /path/to/manifest.yaml [--dry-run] [--no-generate-k8s]
```

For the "Get Environment Info" command:

```bash
buildandburn info --env-id <env_id>
```

For the "Destroy Environment" command:

```bash
buildandburn down --env-id <env_id>
```

For the "List Environments" command:

```bash
buildandburn list
```

#### Context Menu Integration

The extension adds context menu items to YAML files in the Explorer view:

- Right-click on a manifest file and select "Build and Burn: Create Environment" 
- Right-click on a manifest file and select "Build and Burn: Validate Environment" (performs a dry run)

### Environment Explorer View

The extension provides an Environment Explorer view in the sidebar that shows:

1. All your Build and Burn environments
2. Status of each environment (active, creating, failed)
3. Key information such as creation time and AWS region

You can right-click on any environment in the view to:
- View detailed information
- Open the application URL in a browser
- Connect to the Kubernetes cluster
- Destroy the environment

## Coming Soon

We're working on plugins for other popular IDEs:

- IntelliJ IDEA (and other JetBrains IDEs)
- Eclipse
- Visual Studio

## Troubleshooting

If you encounter issues with the extension:

1. Check the Build and Burn output panel for detailed error messages
2. Ensure the Build and Burn CLI is properly installed and accessible in your PATH
3. Verify that your AWS credentials are correctly configured
4. Make sure all prerequisites (Terraform, kubectl) are installed and accessible

Common error messages:

- **"Command not found: buildandburn"**: The CLI is not installed or not in your PATH
- **"AWS credentials not found"**: Configure AWS credentials with one of the methods above
- **"Failed to create environment"**: Check the output panel for detailed error messages from the CLI

## Contributing

Contributions to the IDE plugins are welcome! See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines on how to contribute.

## License

MIT 