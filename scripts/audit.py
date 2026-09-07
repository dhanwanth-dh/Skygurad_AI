#!/usr/bin/env python
"""Entry point: python scripts/audit.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skyguard.pipeline.audit import run_audit

if __name__ == "__main__":
    run_audit()
