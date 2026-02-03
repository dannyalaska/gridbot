# Security Notes

- Store exchange API keys in `.env` or shell environment variables only.
- Use keys with trading permissions only; never enable withdrawals.
- `.env` is excluded via `.gitignore` and should never be committed.
- Live trading requires `GRIDBOT_LIVE_TRADING=true` in the session.
- Optional dashboard protection: set `DASHBOARD_API_KEY` and provide it as `X-API-Key`
  when calling `/api/start`, `/api/stop`, or `/api/grid`.
- Dashboard enforces localhost-only access via middleware.
- Avoid logging secrets; logs include trading actions, not key material.
