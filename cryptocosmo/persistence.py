import sqlite3
from pathlib import Path
from typing import Dict, Optional, Tuple


class Persistence:
    """
    Lightweight SQLite persistence for runs and snapshots.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
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
                max_exposure REAL
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

    def start_run(self, mode: str, symbol: str, grid: Dict[str, float]) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO runs (mode, symbol, grid_center, grid_spacing, grid_lower, grid_upper, max_exposure)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mode,
                symbol,
                grid.get("center"),
                grid.get("spacing"),
                grid.get("lower"),
                grid.get("upper"),
                grid.get("max_exposure"),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_grid(self, run_id: int, grid: Dict[str, float]) -> None:
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

