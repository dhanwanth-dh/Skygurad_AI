"""Historical Data Ingestion Manager for SkyGuard AI.

Orchestrates multi-year historical telemetry retrieval from official IMD sources,
incremental synchronization, duplicate deduplication, station discovery, and storage.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from skyguard.config.settings import settings
from skyguard.services.historical_data_provider import (
    HistoricalDataProvider,
    IMDHistoricalDataProvider,
)
from skyguard.services.historical_store import HistoricalStore

logger = logging.getLogger("skyguard.services.historical_data_manager")


class HistoricalDataManager:
    """Coordinates historical AWS observation ingestion, date-range slicing, and synchronization."""

    def __init__(
        self,
        provider: Optional[HistoricalDataProvider] = None,
        store: Optional[HistoricalStore] = None,
        historical_years: Optional[int] = None,
    ) -> None:
        self.provider = provider or IMDHistoricalDataProvider()
        self.store = store or HistoricalStore()
        self.historical_years = historical_years or settings.historical_years
        self._is_ingesting = False
        self._last_error: Optional[str] = None

    def calculate_target_date_range(self) -> tuple[str, str]:
        """Calculate dynamic (start_date, end_date) based on HISTORICAL_YEARS."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=int(self.historical_years * 365.25))
        return start.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")

    def run_ingestion(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        station_ids: Optional[list[str]] = None,
        chunk_days: int = 30,
        progress_callback: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Execute historical telemetry download and persistence across chunked date intervals."""
        if not start_date or not end_date:
            calc_start, calc_end = self.calculate_target_date_range()
            start_date = start_date or calc_start
            end_date = end_date or calc_end

        self._is_ingesting = True
        logger.info(
            "[HistoricalManager] Starting historical ingestion: %s to %s (Target: %d years)",
            start_date,
            end_date,
            self.historical_years,
        )

        total_new_records = 0
        stations_seen: set[str] = set()
        dt_start = datetime.fromisoformat(start_date.replace(" ", "T"))
        dt_end = datetime.fromisoformat(end_date.replace(" ", "T"))

        current_dt = dt_start
        total_days = max(1, (dt_end - dt_start).days)
        error_messages = []

        while current_dt < dt_end:
            next_dt = min(dt_end, current_dt + timedelta(days=chunk_days))
            chunk_start = current_dt.strftime("%Y-%m-%d %H:%M:%S")
            chunk_end = next_dt.strftime("%Y-%m-%d %H:%M:%S")

            records, err = self.provider.fetch(
                start_datetime=chunk_start,
                end_datetime=chunk_end,
                station_ids=station_ids,
            )

            if err:
                error_messages.append(err)
                logger.info("[HistoricalManager] Chunk %s to %s: %s", chunk_start, chunk_end, err)
            elif records:
                inserted = self.store.insert_observations(records)
                total_new_records += inserted
                for r in records:
                    if r.get("station_id"):
                        stations_seen.add(str(r["station_id"]))

            elapsed_days = (next_dt - dt_start).days
            progress_pct = min(100.0, round((elapsed_days / total_days) * 100.0, 1))

            if progress_callback:
                progress_callback({
                    "progress": progress_pct,
                    "records_inserted": total_new_records,
                    "stations_discovered": len(stations_seen),
                    "current_chunk": f"{chunk_start} to {chunk_end}",
                })

            current_dt = next_dt

        self._is_ingesting = False
        status_info = self.store.get_status()

        result = {
            "success": True,
            "new_records_inserted": total_new_records,
            "stations_discovered": len(stations_seen),
            "total_records_in_store": status_info["records"],
            "total_stations_in_store": status_info["stations"],
            "oldest_observation": status_info["oldest_observation"],
            "latest_observation": status_info["latest_observation"],
            "years_available": status_info["years_available"],
            "provider_status": self.provider.get_provider_status(),
            "notes": list(set(error_messages)),
        }
        logger.info(
            "[HistoricalManager] Ingestion complete. Stored: %d total observations, %d stations",
            status_info["records"],
            status_info["stations"],
        )
        return result

    def get_status(self) -> dict[str, Any]:
        """Return comprehensive historical ingestion status."""
        store_status = self.store.get_status()
        calc_start, calc_end = self.calculate_target_date_range()
        return {
            **store_status,
            "target_historical_years": self.historical_years,
            "target_date_range": {
                "start": calc_start,
                "end": calc_end,
            },
            "is_ingesting": self._is_ingesting,
            "provider_status": self.provider.get_provider_status(),
            "last_error": self._last_error,
        }


def cli_main() -> None:
    """Command-line entry point for historical ingestion."""
    parser = argparse.ArgumentParser(description="SkyGuard AI — Historical IMD AWS Data Ingestion")
    parser.add_argument("--start", type=str, default=None, help="Start timestamp (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--end", type=str, default=None, help="End timestamp (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--years", type=int, default=15, help="Historical years depth (default: 15)")
    parser.add_argument("--stations", type=str, default="all", help="'all' or comma-separated station IDs")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    stn_list = None if args.stations.lower() == "all" else [s.strip() for s in args.stations.split(",")]
    mgr = HistoricalDataManager(historical_years=args.years)

    print("=" * 60)
    print("SkyGuard Historical Ingestion")
    print("=" * 60)
    print(f"Source: IMD Official AWS API")
    print(f"Target Depth: {args.years} years")

    def print_progress(p: dict[str, Any]) -> None:
        pct = p["progress"]
        bar_len = 30
        filled = int(bar_len * pct / 100.0)
        bar = "=" * filled + "-" * (bar_len - filled)
        sys.stdout.write(f"\rProgress: [{bar}] {pct:.1f}% | Records: {p['records_inserted']:,} | Stations: {p['stations_discovered']}")
        sys.stdout.flush()

    res = mgr.run_ingestion(
        start_date=args.start,
        end_date=args.end,
        station_ids=stn_list,
        progress_callback=print_progress,
    )
    print("\n" + "=" * 60)
    print(f"Summary: Stored {res['total_records_in_store']:,} records across {res['total_stations_in_store']} stations.")
    if res.get("notes"):
        for note in res["notes"]:
            print(f"Note: {note}")
    print("=" * 60)


if __name__ == "__main__":
    cli_main()
