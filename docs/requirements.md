# CryptoCosmo Requirements Mapping

This document maps the requirements in `requirements.pdf` to concrete, trackable items in this repo.

## 1. Problem framing and success metrics
- Business objective: conservative grid trading with bounded exposure and risk.
- Constraints: `grid.max_exposure_quote`, `risk.daily_loss_limit_pct`, `risk.max_drawdown_pct`,
  `risk.crash_drop_pct`, `health.max_stale_price_secs`.
- Success metrics:
  - User-facing: net profit, drawdown %, target-profit hit rate.
  - Technical: dashboard latency, order fill rate, exceptions per tick.
  - System: uptime, API cost, CPU/memory.

## 2. Configuration and tracking
- Configs stay in `config.yaml` and `.env` with `config.example.yaml` for safe edits.
- Record config changes in commit history and a short changelog when tuning parameters.
- Tests cover `GridTrader.sync`, `RiskGuard.evaluate`, `HealthMonitor.healthy`, and
  `PerformanceAnalyst.maybe_adjust` on varied market scenarios.

## 3. Model selection (future)
- Replace `SentimentScout` stub with a real sentiment source and compare cost/accuracy.
- Optional volatility/price models (EMA/ARIMA/LSTM) with performance vs cost tradeoffs.
- Document model choice in `docs/model_selection.md`.

## 4. Data retrieval and storage (future)
- Use `ccxt` for candles/order book with retry + caching and optional fallback data sources.
- Store retrieved data in SQLite (separate tables from trading state) for analysis.
- If using LLM summarization, evaluate retrieval precision/recall.

## 5. Agent system alignment
- Expose clear tool methods (fetch price, place/cancel, update grid, sentiment).
- Categorize errors (network, funds, rate limit) and add safe retries.
- Add API key protection on control endpoints and document secret handling.

## 6. Deployment and UI
- Keep REST endpoints documented via FastAPI/OpenAPI.
- Move CSS to a static file and consider SSE/WebSockets for streaming updates.
- Provide deployment docs (Docker/Procfile/K8s) when needed.

## 7. Monitoring and error analysis
- Persist logs to `logs/gridbot.log` with context fields.
- Expose Prometheus metrics at `/metrics` for latency, orders, risk, sentiment, and errors.
- Add post-run reports for PnL and risk events.

## 8. Optional fine-tuning (future)
- Fine-tune only after prompt baselines are stable and datasets are ready.
- Automate parameter optimization in simulation before applying to sandbox/live.
