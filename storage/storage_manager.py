"""
storage/storage_manager.py
──────────────────────────
Handles persistence of validated ScrapedResult → DrawSession objects.

Writes to:
  1. A master JSON file  (append-mode, deduplicated by session_id)
  2. A master CSV file   (one row per DrawEntry, append-mode)

Both files are safe for concurrent single-process access (file-lock via
simple read-modify-write with atomic rename). Thread-safe for asyncio usage.

Schema is decoupled from storage — the DB layer (Phase 3) can replace this
by implementing the same interface.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

from models.schemas import DrawSession, ScrapedResult

log = logging.getLogger("storage")

# CSV column order
_CSV_COLUMNS = [
    "session_id",
    "source_id",
    "source_url",
    "draw_date",
    "draw_time",
    "state",
    "banca",
    "premio",
    "milhar",
    "centena",
    "dezena",
    "grupo",
    "bicho",
    "super5",
    "scraped_at_utc",
]


class StorageManager:
    def __init__(self, json_path: str, csv_path: str) -> None:
        self._json_path = Path(json_path)
        self._csv_path  = Path(csv_path)
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_ids: set[str] = self._load_existing_ids()

    # ── Public API ───────────────────────────────────────────────────────────

    def save(self, result: ScrapedResult) -> int:
        """
        Persist all sessions in the result.
        Returns number of new sessions written (0 if all duplicates).
        """
        new_sessions = [
            s for s in result.sessions
            if s.session_id not in self._seen_ids
        ]

        if not new_sessions:
            log.info(f"[storage] All {len(result.sessions)} session(s) already stored — skip.")
            return 0

        self._append_json(new_sessions)
        self._append_csv(new_sessions)

        for s in new_sessions:
            self._seen_ids.add(s.session_id)

        log.info(f"[storage] Saved {len(new_sessions)} new session(s).")
        return len(new_sessions)

    # ── JSON ─────────────────────────────────────────────────────────────────

    def _load_existing_ids(self) -> set[str]:
        if not self._json_path.exists():
            return set()
        try:
            with self._json_path.open(encoding="utf-8") as f:
                records = json.load(f)
            return {r.get("session_id", "") for r in records}
        except Exception as exc:
            log.warning(f"[storage] Could not read existing JSON: {exc}")
            return set()

    def _append_json(self, sessions: List[DrawSession]) -> None:
        # Load existing
        existing: list = []
        if self._json_path.exists():
            try:
                with self._json_path.open(encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass

        # Append new records
        for s in sessions:
            existing.append(s.model_dump(mode="json"))

        # Atomic write (write to tmp, then rename)
        self._atomic_write_json(existing)

    def _atomic_write_json(self, data: list) -> None:
        tmp_path = self._json_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        tmp_path.replace(self._json_path)
        log.debug(f"[storage] JSON updated: {self._json_path}")

    # ── CSV ──────────────────────────────────────────────────────────────────

    def _append_csv(self, sessions: List[DrawSession]) -> None:
        write_header = not self._csv_path.exists()

        with self._csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
            if write_header:
                writer.writeheader()

            for s in sessions:
                super5_str = (
                    ",".join(str(n) for n in s.super5.numbers) if s.super5 else ""
                )
                for entry in s.entries:
                    writer.writerow({
                        "session_id":    s.session_id,
                        "source_id":     s.source_id.value,
                        "source_url":    s.source_url,
                        "draw_date":     s.draw_date,
                        "draw_time":     s.draw_time,
                        "state":         s.state or "",
                        "banca":         s.banca or "",
                        "premio":        entry.premio,
                        "milhar":        entry.milhar,
                        "centena":       entry.centena,
                        "dezena":        entry.dezena,
                        "grupo":         entry.grupo,
                        "bicho":         entry.bicho,
                        "super5":        super5_str,
                        "scraped_at_utc": s.scraped_at_utc.isoformat(),
                    })

        log.debug(f"[storage] CSV updated: {self._csv_path}")

    # ── Query helpers (future DB interface anchor) ────────────────────────────

    def get_latest_session(self, source_id: str) -> dict | None:
        """Return the most recently saved session for a given source."""
        if not self._json_path.exists():
            return None
        try:
            with self._json_path.open(encoding="utf-8") as f:
                records = json.load(f)
            filtered = [r for r in records if r.get("source_id") == source_id]
            if not filtered:
                return None
            return sorted(filtered, key=lambda r: r.get("scraped_at_utc", ""))[-1]
        except Exception as exc:
            log.error(f"[storage] get_latest_session error: {exc}")
            return None

    def get_today_sessions(self, source_id: str, date_str: str) -> List[dict]:
        """Return all sessions for a source on a specific date (dd/mm/yyyy)."""
        if not self._json_path.exists():
            return []
        try:
            with self._json_path.open(encoding="utf-8") as f:
                records = json.load(f)
            return [
                r for r in records
                if r.get("source_id") == source_id and r.get("draw_date") == date_str
            ]
        except Exception as exc:
            log.error(f"[storage] get_today_sessions error: {exc}")
            return []
