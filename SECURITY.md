# Security Notes

- Store exchange API keys in `.env` or shell environment variables only.
- Use keys with trading permissions only; never enable withdrawals.
- `.env` is excluded via `.gitignore` and should never be committed.
- Optional dashboard protection: set `DASHBOARD_API_KEY` and provide it as `X-API-Key`
  when calling `/api/start`, `/api/stop`, or `/api/grid`.
- Avoid logging secrets; logs include trading actions, not key material.
