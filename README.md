# CryptoCosmo Grid Bot

Conservative grid trading bot with simulation and sandbox support.

## Setup
- Install deps: `python3 -m pip install -r requirements.txt`
- Copy `config.yaml` and tweak values as needed.

## Modes
- **simulation**: uses an in-memory exchange with a random walk price feed.
- **sandbox**: uses `ccxt` against Binance spot testnet (`testnet.binance.vision`). Set env vars:
  - `BINANCE_SANDBOX_API_KEY`
  - `BINANCE_SANDBOX_API_SECRET`
  - flip `exchange.dry_run` to `false` in `config.yaml` to place real sandbox orders.

## Run
- Simulation: `python3 main.py --mode simulation`
- Sandbox: `python3 main.py --mode sandbox`

## High/Low Bounds
`grid.lower_bound` and `grid.upper_bound` clamp trading to a desired range; new buys pause outside the band.

## Web UI Dashboard
- Run: `uvicorn dashboard:app --host 0.0.0.0 --port 8787 --reload` (or `python3 dashboard.py`)
- UI lives at `http://localhost:8787` with:
  - Start/stop controls
  - Symbol picker
  - Grid window adjustments (center/spacing/lower/upper/max exposure)
  - Live agent status (GridTrader, RiskGuard, PerformanceAnalyst, Sentiment, Health, ProfitSweeper) and logs

## Components
- GridTrader maintains staggered buy levels and pairs sells after fills.
- RiskGuard enforces daily loss, drawdown, and crash detection before allowing new buys.
- PerformanceAnalyst nudges the grid center on a timer.
- HealthMonitor watches for stale data/error streaks.
- ProfitSweeper tracks realised profit into a cosmetics fund (sim/sandbox bookkeeping only).
- RiskGuard can cancel open orders on pause (`risk.cancel_open_orders_on_pause`).
- On start, the grid centers on live price and seeds a sell ladder from existing holdings (base balance).
- Persistence: SQLite at `persistence.db_path` records runs/snapshots and restores last grid on restart (configurable).

## Secrets (.env)
- Copy `.env.example` to `.env` and fill in your keys:
  - `BINANCE_SANDBOX_API_KEY=...`
  - `BINANCE_SANDBOX_API_SECRET=...`
- Load in the shell before running:
  - `set -a && source .env && set +a`
- `.gitignore` already excludes `.env`.

## Persistence
- Default SQLite path: `data/state.db`. Toggle via `persistence.enabled`.
- Restores the last grid for the mode/symbol if `persistence.restore_last_grid` is true.
- Records price/equity/balance snapshots per tick for history/QA.
