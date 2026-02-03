# CryptoCosmo Production Checklist

## Preflight
- Confirm `config.yaml` is checked in to your desired branch and backed up.
- Set `mode: live` and `exchange.dry_run: false` in `config.yaml`.
- Set `GRIDBOT_LIVE_TRADING=true` in your shell/session before start.
- Verify `exchange.api_key_env` / `exchange.api_secret_env` point at live key vars.
- Keep withdrawal permissions disabled on exchange keys.
- Set `DASHBOARD_API_KEY` if you want an extra local-only safeguard.
- Review `risk.*` limits and `risk.restore_state` for carryover behavior.

## Startup
- Start the dashboard locally: `python3 dashboard.py`.
- Load the UI at `http://127.0.0.1:8787`.
- Confirm the dashboard shows `Stopped` before pressing start.
- Check portfolio allocation, grid bounds, and max exposure before starting.

## Live Readiness
- Start with a smaller `grid.order_size` than your target size.
- Confirm open orders appear as expected and fills align with grid spacing.
- Watch `Risk & Limits` panel for loss/drawdown/crash changes.
- Verify `/metrics` is updating if you use monitoring.

## Ongoing Ops
- Keep logs in `logs/gridbot.log` and archive runs periodically.
- Review snapshots in `data/state.db` after each session.
- Adjust grid bounds slowly; avoid widening during volatility spikes.

## Shutdown
- Use the dashboard Stop button and verify open orders are cancelled.
- Unset `GRIDBOT_LIVE_TRADING` after the session.
