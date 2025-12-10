import sys
from pathlib import Path

# Ensure the src directory is on sys.path so top-level packages (core, proxy, etc.) are importable
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
