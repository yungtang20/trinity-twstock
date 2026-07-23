"""Read-only database health checks and guarded SQLite maintenance."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from twstock.commands.data_repair import collect_quality_report
from twstock.db import get_connection, get_path


VACUUM_MIN_RECLAIM_BYTES = 100 * 1024 * 1024
VACUUM_MIN_RECLAIM_RATIO = 0.05
VACUUM_FREE_SPACE_MULTIPLIER = 2.1


@dataclass(frozen=True)
class DatabaseHealthReport:
    """Snapshot of structural, quality, and reclaimable-space diagnostics."""

    database_path: Path
    file_size_bytes: int
    wal_size_bytes: int
    page_size: int
    page_count: int
    freelist_count: int
    reclaimable_bytes: int
    reclaimable_ratio: float
    quick_check: str
    quality_counts: dict[str, int]

    @property
    def is_healthy(self) -> bool:
        """Return whether SQLite's structural check passed."""
        return self.quick_check.lower() == "ok"

    @property
    def vacuum_recommended(self) -> bool:
        """Return whether reclaimable space justifies rewriting the database."""
        return self.is_healthy and (
            self.reclaimable_bytes >= VACUUM_MIN_RECLAIM_BYTES
            or self.reclaimable_ratio >= VACUUM_MIN_RECLAIM_RATIO
        )


def build_database_health_report() -> DatabaseHealthReport:
    """Run read-only SQLite and known-data-quality diagnostics."""
    database_path = Path(get_path())
    connection = get_connection(readonly=True)
    try:
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        freelist_count = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
        quick_row = connection.execute("PRAGMA quick_check(1)").fetchone()
        quick_check = str(quick_row[0] if quick_row else "unknown")
        quality_counts = collect_quality_report(connection)
    finally:
        connection.close()

    file_size_bytes = database_path.stat().st_size if database_path.exists() else 0
    wal_path = Path(f"{database_path}-wal")
    wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0
    reclaimable_bytes = page_size * freelist_count
    allocated_bytes = page_size * page_count
    reclaimable_ratio = reclaimable_bytes / allocated_bytes if allocated_bytes else 0.0

    return DatabaseHealthReport(
        database_path=database_path,
        file_size_bytes=file_size_bytes,
        wal_size_bytes=wal_size_bytes,
        page_size=page_size,
        page_count=page_count,
        freelist_count=freelist_count,
        reclaimable_bytes=reclaimable_bytes,
        reclaimable_ratio=reclaimable_ratio,
        quick_check=quick_check,
        quality_counts=quality_counts,
    )


def run_database_optimize() -> None:
    """Ask SQLite to update planner statistics where it considers useful."""
    connection = get_connection()
    try:
        connection.execute("PRAGMA optimize")
        connection.commit()
    finally:
        connection.close()


def save_database_backup(destination_dir: str | Path | None = None) -> Path:
    """Create and verify a consistent SQLite backup using the backup API."""
    database_path = Path(get_path())
    backup_dir = Path(destination_dir) if destination_dir is not None else database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = backup_dir / f"{database_path.stem}_{timestamp}.db"

    source = get_connection(readonly=True)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
        check_row = target.execute("PRAGMA quick_check(1)").fetchone()
        if not check_row or str(check_row[0]).lower() != "ok":
            raise sqlite3.DatabaseError("備份檔 quick_check 未通過")
    except Exception:
        target.close()
        source.close()
        destination.unlink(missing_ok=True)
        raise
    else:
        target.close()
        source.close()
    return destination


def run_guarded_database_vacuum(report: DatabaseHealthReport | None = None) -> Path:
    """Back up and VACUUM only when health and reclaim thresholds permit it."""
    report = report or build_database_health_report()
    if not report.is_healthy:
        raise sqlite3.DatabaseError("資料庫結構檢查未通過，禁止執行 VACUUM")
    if not report.vacuum_recommended:
        raise ValueError("目前可回收空間不足，不需要執行 VACUUM")

    free_bytes = shutil.disk_usage(report.database_path.parent).free
    required_bytes = int(report.file_size_bytes * VACUUM_FREE_SPACE_MULTIPLIER)
    if free_bytes < required_bytes:
        raise OSError(
            f"磁碟空間不足：至少需要 {required_bytes / (1024**3):.2f} GiB 可用空間"
        )

    backup_path = save_database_backup()
    connection = get_connection()
    try:
        connection.execute("VACUUM")
    finally:
        connection.close()
    return backup_path
