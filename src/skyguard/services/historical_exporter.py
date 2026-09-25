"""Historical Telemetry Exporter and Excel Partition Synchronizer for SkyGuard AI.

Generates partitioned Excel (.xlsx) and CSV archives partitioned by year and volume
(enforcing strict safety well below Excel's 1,048,576 row limit per sheet).
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from skyguard.config.settings import settings
from skyguard.services.historical_store import HistoricalStore

logger = logging.getLogger("skyguard.services.historical_exporter")

# Safe row limit per Excel file partition (well below Excel's 1,048,576 row ceiling)
MAX_ROWS_PER_EXCEL_PARTITION = 500_000


class HistoricalExporter:
    """Handles partitioned Excel generation, multi-format exports, and live partition sync."""

    def __init__(
        self,
        store: Optional[HistoricalStore] = None,
        export_dir: Optional[Path | str] = None,
    ) -> None:
        self.store = store or HistoricalStore()
        self.export_dir = Path(export_dir or settings.historical_export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_full_archive(self, start: Optional[str] = None, end: Optional[str] = None) -> dict[str, Any]:
        """Generate structured year-partitioned Excel files for the entire stored historical dataset."""
        df = self.store.get_dataframe(start=start, end=end)
        if df.empty:
            return {"success": True, "files_created": [], "total_rows_exported": 0}

        df["year"] = df["timestamp"].dt.year
        created_files: list[str] = []
        total_rows = len(df)

        for year, year_df in df.groupby("year"):
            year_dir = self.export_dir / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)

            year_df_clean = year_df.drop(columns=["year"], errors="ignore")
            year_rows = len(year_df_clean)

            if year_rows <= MAX_ROWS_PER_EXCEL_PARTITION:
                file_path = year_dir / f"aws_{year}.xlsx"
                year_df_clean.to_excel(file_path, index=False, engine="openpyxl")
                created_files.append(str(file_path))
            else:
                # Partition across multiple sub-files
                num_parts = (year_rows + MAX_ROWS_PER_EXCEL_PARTITION - 1) // MAX_ROWS_PER_EXCEL_PARTITION
                for part_idx in range(num_parts):
                    part_df = year_df_clean.iloc[
                        part_idx * MAX_ROWS_PER_EXCEL_PARTITION : (part_idx + 1) * MAX_ROWS_PER_EXCEL_PARTITION
                    ]
                    part_file = year_dir / f"aws_{year}_part_{part_idx + 1:02d}.xlsx"
                    part_df.to_excel(part_file, index=False, engine="openpyxl")
                    created_files.append(str(part_file))

        logger.info(
            "[HistoricalExporter] Full archive export completed: %d rows across %d files",
            total_rows,
            len(created_files),
        )
        return {
            "success": True,
            "export_directory": str(self.export_dir),
            "files_created": created_files,
            "total_rows_exported": total_rows,
        }

    def sync_live_observations_to_current_partition(
        self,
        new_observations: list[dict[str, Any]],
    ) -> Optional[str]:
        """Incrementally append/update current year's Excel partition without rewriting past years."""
        if not new_observations:
            return None

        current_year = datetime.now(timezone.utc).year
        year_dir = self.export_dir / str(current_year)
        year_dir.mkdir(parents=True, exist_ok=True)
        file_path = year_dir / f"aws_{current_year}.xlsx"

        # Export current year's data directly from store
        year_start = f"{current_year}-01-01 00:00:00"
        df_year = self.store.get_dataframe(start=year_start)
        if not df_year.empty:
            df_year.to_excel(file_path, index=False, engine="openpyxl")
            return str(file_path)
        return None

    def export_data_buffer(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        station_id: Optional[str] = None,
        export_format: str = "xlsx",
    ) -> tuple[io.BytesIO, str, str]:
        """Export filtered historical dataset into an in-memory buffer for HTTP download.

        Returns (buffer, filename, media_type).
        """
        station_ids = [station_id] if station_id else None
        df = self.store.get_dataframe(start=start, end=end, station_ids=station_ids)

        timestamp_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        stn_tag = f"_{station_id}" if station_id else "_pan_india"

        fmt = export_format.lower().strip()
        if fmt == "csv":
            buf = io.BytesIO()
            df.to_csv(buf, index=False, encoding="utf-8")
            buf.seek(0)
            filename = f"skyguard_historical{stn_tag}_{timestamp_tag}.csv"
            media_type = "text/csv"
            return buf, filename, media_type

        # Default: Excel .xlsx
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        filename = f"skyguard_historical{stn_tag}_{timestamp_tag}.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return buf, filename, media_type
