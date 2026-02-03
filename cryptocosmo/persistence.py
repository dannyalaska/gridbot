import sqlite3
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple


class Persistence:
    """
    Lightweight SQLite persistence for runs and snapshots.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    mode TEXT,
                    symbol TEXT,
                    grid_center REAL,
                    grid_spacing REAL,
                    grid_lower REAL,
                    grid_upper REAL,
                    max_exposure REAL,
                    risk_start_equity REAL,
                    risk_max_equity REAL
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    tick INTEGER,
                    price REAL,
                    equity REAL,
                    base REAL,
                    quote REAL,
                    paused INTEGER,
                    drawdown REAL,
                    healthy INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                """
            )
            self.conn.commit()
        self._ensure_run_columns()

    def _ensure_run_columns(self) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(runs)")
            cols = {row["name"] for row in cur.fetchall()}
            if "risk_start_equity" not in cols:
                cur.execute("ALTER TABLE runs ADD COLUMN risk_start_equity REAL")
            if "risk_max_equity" not in cols:
                cur.execute("ALTER TABLE runs ADD COLUMN risk_max_equity REAL")
            self.conn.commit()

    def start_run(self, mode: str, symbol: str, grid: Dict[str, float]) -> int:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO runs (
                    mode,
                    symbol,
                    grid_center,
                    grid_spacing,
                    grid_lower,
                    grid_upper,
                    max_exposure,
                    risk_start_equity,
                    risk_max_equity
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mode,
                    symbol,
                    grid.get("center"),
                    grid.get("spacing"),
                    grid.get("lower"),
                    grid.get("upper"),
                    grid.get("max_exposure"),
                    None,
                    None,
                ),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def update_grid(self, run_id: int, grid: Dict[str, float]) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE runs
                SET grid_center = ?, grid_spacing = ?, grid_lower = ?, grid_upper = ?, max_exposure = ?
                WHERE id = ?
                """,
                (
                    grid.get("center"),
                    grid.get("spacing"),
                    grid.get("lower"),
                    grid.get("upper"),
                    grid.get("max_exposure"),
                    run_id,
                ),
            )
            self.conn.commit()

    def update_risk(self, run_id: int, start_equity: Optional[float], max_equity: Optional[float]) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE runs
                SET risk_start_equity = ?, risk_max_equity = ?
                WHERE id = ?
                """,
                (start_equity, max_equity, run_id),
            )
            self.conn.commit()

    def record_snapshot(
        self,
        run_id: int,
        tick: int,
        price: float,
        equity: float,
        base: float,
        quote: float,
        paused: bool,
        drawdown: float,
        healthy: bool,
    ) -> None:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO snapshots (run_id, tick, price, equity, base, quote, paused, drawdown, healthy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, tick, price, equity, base, quote, int(paused), drawdown, int(healthy)),
            )
            self.conn.commit()

    def last_run(self, mode: str, symbol: str) -> Optional[Tuple[int, Dict[str, float]]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, grid_center, grid_spacing, grid_lower, grid_upper, max_exposure
                FROM runs
                WHERE mode = ? AND symbol = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (mode, symbol),
            )
            row = cur.fetchone()
            if not row:
                return None
            grid = {
                "center": row["grid_center"],
                "spacing": row["grid_spacing"],
                "lower": row["grid_lower"],
                "upper": row["grid_upper"],
                "max_exposure": row["max_exposure"],
            }
            return int(row["id"]), grid

    def last_run_risk(self, mode: str, symbol: str) -> Optional[Dict[str, float]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT risk_start_equity, risk_max_equity
                FROM runs
                WHERE mode = ? AND symbol = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (mode, symbol),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"start_equity": row["risk_start_equity"], "max_equity": row["risk_max_equity"]}

    def recent_snapshots(self, run_id: int, limit: int = 300) -> list[Dict[str, float]]:
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT tick, price, equity, base, quote, paused, drawdown, healthy, created_at
                FROM snapshots
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (run_id, limit),
            )
            rows = cur.fetchall()
            snapshots = []
            for row in reversed(rows):
                snapshots.append(
                    {
                        "tick": row["tick"],
                        "price": row["price"],
                        "equity": row["equity"],
                        "base": row["base"],
                        "quote": row["quote"],
                        "paused": row["paused"],
                        "drawdown": row["drawdown"],
                        "healthy": row["healthy"],
                        "timestamp": row["created_at"],
                    }
                )
            return snapshots
