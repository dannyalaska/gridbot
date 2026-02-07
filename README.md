# CryptoCosmo Grid Bot

Conservative grid trading bot with simulation and sandbox support.

## Setup
- Install deps: `python3 -m pip install -r requirements.txt`
- Copy `config.example.yaml` to `config.yaml` and tweak values as needed.

## Modes
- **simulation**: uses an in-memory exchange with a random walk price feed.
- **paper**: uses live public prices (ccxt ticker) but fills orders locally (no keys, no real orders).
- **sandbox**: uses `ccxt` against Binance spot testnet (`testnet.binance.vision`). Set env vars:
  - `BINANCE_SANDBOX_API_KEY`
  - `BINANCE_SANDBOX_API_SECRET`
  - flip `exchange.dry_run` to `false` in `config.yaml` to place real sandbox orders.
- **live**: uses `ccxt` against Binance spot. Requirements:
  - `exchange.dry_run: false`
  - `GRIDBOT_LIVE_TRADING=true` in the shell/session
  - set `exchange.api_key_env` / `exchange.api_secret_env` to live key envs

## Run
- Simulation: `python3 main.py --mode simulation`
- Paper: `python3 main.py --mode paper`
- Sandbox: `python3 main.py --mode sandbox`
- Live: `python3 main.py --mode live`

## High/Low Bounds
`grid.lower_bound` and `grid.upper_bound` clamp trading to a desired range; new buys pause outside the band.

## Web UI Dashboard
- Run: `python3 dashboard.py`
- UI lives at `http://localhost:8787` with:
  - Start/stop controls
  - Symbol picker
  - Grid window adjustments (center/spacing/lower/upper/max exposure)
  - Live agent status (GridTrader, RiskGuard, PerformanceAnalyst, Sentiment, Health, ProfitSweeper) and logs
  - Metrics endpoint at `/metrics` (Prometheus format)
  - Optional API key protection with `DASHBOARD_API_KEY`
  - Localhost-only access enforced by middleware
  - Optional auto-start by setting `GRIDBOT_AUTOSTART=true`

## Components
- GridTrader maintains staggered buy levels and pairs sells after fills.
- RiskCouncil aggregates RiskGuard + LLMRiskAgent + ManagerAgent decisions (LLM veto optional).
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
  - `BINANCE_API_KEY=...` (live)
  - `BINANCE_API_SECRET=...` (live)
- Load in the shell before running:
  - `set -a && source .env && set +a`
- `.gitignore` already excludes `.env`.
 - Set `DASHBOARD_API_KEY` to require a header for control endpoints.

## Security
See `SECURITY.md` for secret handling and dashboard protection.

## Logs
Trading and system logs are written to `logs/gridbot.log`.

## Persistence
- Default SQLite path: `data/state.db`. Toggle via `persistence.enabled`.
- Restores the last grid for the mode/symbol if `persistence.restore_last_grid` is true.
- Records price/equity/balance snapshots per tick for history/QA.

## Requirements
See `docs/requirements.md` for the mapping of the requirements doc to repo items.

## Production Checklist
See `docs/production_checklist.md`.
