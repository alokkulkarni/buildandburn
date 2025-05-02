import unittest
import sys
import os
import tempfile
import yaml
import shutil

# Add the cli directory to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cli.buildandburn import generate_env_id, load_manifest, ensure_k8s_resources

class TestBasic(unittest.TestCase):
    def test_generate_env_id(self):
        """Test that generate_env_id returns a string of the correct length."""
        env_id = generate_env_id()
        self.assertIsInstance(env_id, str)
        self.assertEqual(len(env_id), 8)
    
    def test_env_id_uniqueness(self):
        """Test that generate_env_id returns unique IDs."""
        env_ids = [generate_env_id() for _ in range(100)]
        self.assertEqual(len(env_ids), len(set(env_ids)), "Generated env IDs should be unique")
        
    def test_load_manifest(self):
        """Test that load_manifest correctly loads YAML files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            manifest_content = """
            name: test-app
            region: eu-west-2
            k8s_path: './custom-k8s/test-app'
            services:
              - name: nginx
                image: nginx:alpine
                port: 80
            """
            temp_file.write(manifest_content)
            temp_file.flush()
            
            try:
                manifest = load_manifest(temp_file.name)
                self.assertEqual(manifest['name'], 'test-app')
                self.assertEqual(manifest['region'], 'eu-west-2')
                self.assertEqual(manifest['k8s_path'], './custom-k8s/test-app')
                self.assertEqual(len(manifest['services']), 1)
                self.assertEqual(manifest['services'][0]['name'], 'nginx')
            finally:
                os.unlink(temp_file.name)
                
    def test_k8s_path_handling(self):
        """Test that k8s_path in manifest is properly handled."""
        # Create temp directories and files
        test_dir = tempfile.mkdtemp()
        try:
            # Create test manifest
            manifest_file = os.path.join(test_dir, 'test-manifest.yaml')
            
            # Use absolute path for k8s_path
            k8s_dir = os.path.join(test_dir, 'test-k8s')
            os.makedirs(k8s_dir, exist_ok=True)
            
            with open(manifest_file, 'w') as f:
                f.write(f"""
                name: test-app
                region: eu-west-2
                k8s_path: '{k8s_dir}'
                services:
                  - name: nginx
                    image: nginx:alpine
                    port: 80
                """)
                
            # Create dummy Chart.yaml
            with open(os.path.join(k8s_dir, 'Chart.yaml'), 'w') as f:
                f.write("""
                apiVersion: v2
                name: test-app
                version: 0.1.0
                """)
                
            # Load manifest
            manifest = load_manifest(manifest_file)
            
            # Test k8s resources handling with --no-generate-k8s
            project_dir = os.path.join(test_dir, 'project')
            os.makedirs(project_dir, exist_ok=True)
            
            # Since we're providing a k8s_path, ensure_k8s_resources shouldn't generate
            # new resources, but instead should use the existing ones
            k8s_dir_result = ensure_k8s_resources(
                manifest, 
                os.path.join(project_dir, 'k8s'), 
                project_dir, 
                auto_generate=False
            )
            
            # Check that it returned the path from the manifest
            self.assertEqual(k8s_dir_result, k8s_dir)
            
        finally:
            # Clean up
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    unittest.main() 