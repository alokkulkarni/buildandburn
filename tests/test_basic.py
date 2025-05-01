import unittest
import sys
import os

# Add the cli directory to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cli.buildandburn import generate_env_id

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

if __name__ == "__main__":
    unittest.main() 