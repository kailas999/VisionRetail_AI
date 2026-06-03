import os
import sys

# Add the project root (parent of 'backend') to sys.path so 'ai' package can be resolved
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
