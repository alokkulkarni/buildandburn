# BuildAndBurn Parent Helm Chart

This is the parent Helm chart for BuildAndBurn applications. It includes both the Spring Boot backend and Nginx frontend charts.

## Usage

To install the chart:

```bash
# First, update dependencies
helm dependency update .

# Then install
helm install my-release . --namespace my-namespace
```

## Infrastructure Integration

This chart is designed to work with infrastructure provisioned by the BuildAndBurn tool. When running through the BuildAndBurn CLI, the infrastructure connection details (database, message queue, etc.) will be automatically populated.

## Chart Dependencies

This parent chart includes:

- `springboot-backend` - Spring Boot application (aliased as `sb`)
- `nginx-frontend` - Nginx proxy (aliased as `nf`)

## Values

The chart uses aliases to simplify configuration. Instead of using the full chart name, you can use the alias:

```yaml
# Spring Boot backend settings
sb:
  replicaCount: 2
  image:
    tag: latest

# Nginx frontend settings
nf:
  replicaCount: 1
  configMapData:
    nginx.conf: |
      # Your Nginx configuration here
```

## Troubleshooting

If you encounter issues during installation:

1. Try running the included installation script with debug mode:
   ```bash
   ./install.sh --debug
   ```

2. Check for failed resources:
   ```bash
   kubectl get all -n <namespace>
   ```

3. For issues with specific pods, check the logs:
   ```bash
   kubectl logs -n <namespace> <pod-name>
   ```

4. If there's an issue with the chart structure, try cleaning up first:
   ```bash
   ./install.sh --clean
   ``` 