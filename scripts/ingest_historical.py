"""SkyGuard AI — Historical IMD AWS Data Ingestion CLI.

Usage:
    python scripts/ingest_historical.py --start 2011-01-01 --end 2026-09-21 --years 15 --stations all
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to python path
workspace_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace_root / "src"))
sys.path.insert(0, str(workspace_root))

from skyguard.services.historical_data_manager import cli_main

if __name__ == "__main__":
    cli_main()
