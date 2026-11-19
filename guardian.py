"""Run without installation: python guardian.py --help."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from guardian.cli import main

if __name__ == "__main__":
    main()

