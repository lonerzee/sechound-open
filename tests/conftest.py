import sys
from pathlib import Path

# Make the flat tools/ modules importable in tests, same as the tools do at runtime.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
