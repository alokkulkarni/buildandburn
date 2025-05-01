# Contributing to Build and Burn

We love your input! We want to make contributing to Build and Burn as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Development Process

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

### Pull Requests

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Pull Request Process

1. Update the README.md or documentation with details of changes if appropriate
2. Update any example code that might be affected by your change
3. The PR should work with the existing tests or include new tests for the feature
4. Once your PR gets approved by at least one reviewer, it will be merged

## Project Structure

The project is organized as follows:

```
buildandburn/
├── terraform/           # Terraform modules for infrastructure
├── k8s/                 # Kubernetes templates for services
├── cli/                 # CLI tool for creating/managing environments
├── ide-plugin/          # IDE integrations (VS Code, etc.)
├── backstage-plugin/    # Backstage plugin for developer portal integration
└── docs/                # Documentation
```

## Development Environment Setup

### Prerequisites

- Python 3.7+
- Node.js 14+
- Terraform 1.0+
- kubectl
- AWS CLI

### Setup Steps

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/buildandburn.git
   cd buildandburn
   ```

2. Set up CLI tool in development mode
   ```bash
   cd cli
   pip install -e .
   ```

3. Set up IDE plugin development (VS Code example)
   ```bash
   cd ide-plugin/vscode
   npm install
   ```

4. Set up Backstage plugin development
   ```bash
   cd backstage-plugin
   npm install
   ```

## Testing

### Testing the CLI

```bash
cd cli
pytest
```

### Testing the VS Code extension

In VS Code:
1. Open the extension folder (`ide-plugin/vscode`)
2. Press F5 to start debugging
3. A new VS Code window will open with the extension loaded

## Coding Style

### Python

We follow PEP 8 guidelines for Python code. Use `flake8` for linting:

```bash
flake8 cli/
```

### JavaScript/TypeScript

We use ESLint and Prettier for JavaScript/TypeScript code:

```bash
cd ide-plugin/vscode
npm run lint
```

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License. 