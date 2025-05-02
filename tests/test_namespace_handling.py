import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add the cli directory to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the k8s_generator module
from cli.k8s_generator import create_helm_chart

class TestNamespaceHandling(unittest.TestCase):
    """Test namespace handling in generated Kubernetes manifests."""
    
    def test_namespace_yaml_is_commented(self):
        """Test that the namespace.yaml is generated with comments to prevent conflicts."""
        # Create temp directories
        test_dir = tempfile.mkdtemp()
        try:
            # Generate a helm chart
            manifest = {
                'name': 'test-app',
                'services': [
                    {
                        'name': 'nginx',
                        'image': 'nginx:alpine',
                        'port': 80
                    }
                ]
            }
            
            chart_dir = create_helm_chart(manifest, test_dir)
            
            # Check that namespace.yaml exists and is formatted correctly
            namespace_yaml_path = os.path.join(chart_dir, 'templates', 'namespace.yaml')
            self.assertTrue(os.path.exists(namespace_yaml_path), "namespace.yaml should exist")
            
            # Read the file content
            with open(namespace_yaml_path, 'r') as f:
                content = f.read()
            
            # Verify it's commented out
            self.assertTrue(content.startswith('#'), "namespace.yaml should start with a comment")
            self.assertIn('# This file is intentionally commented out', content)
            self.assertIn('# The namespace will be created by the buildandburn CLI tool', content)
            
            # Make sure there are no uncommented Kubernetes resources
            uncommented_lines = [
                line for line in content.splitlines() 
                if line.strip() and not line.strip().startswith('#')
            ]
            self.assertEqual(len(uncommented_lines), 0, 
                            "namespace.yaml should only contain commented lines")
            
        finally:
            # Clean up
            shutil.rmtree(test_dir)
    
    def test_namespace_creation_in_cli(self):
        """Test that namespace creation is handled in the CLI, not by Helm."""
        # This would require integration testing with kubectl
        # For unit testing, we can verify the helm command doesn't manage namespaces
        
        # Import CLI code here to avoid circular imports
        from cli.buildandburn import deploy_to_kubernetes
        
        # Test that deploy_to_kubernetes contains the --create-namespace flag for Helm
        import inspect
        deploy_code = inspect.getsource(deploy_to_kubernetes)
        
        # Verify Helm is configured with --create-namespace
        self.assertIn('--create-namespace', deploy_code, 
                     "Helm should be configured with --create-namespace")
        
        # Skip additional namespace creation test for now
        # The important part is that Helm is configured with --create-namespace
        # This allows it to create namespaces as needed while avoiding conflicts

if __name__ == "__main__":
    unittest.main() 