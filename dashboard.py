import asyncio
from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from cryptocosmo.bot_runner import BotRunner
from cryptocosmo.config import load_config


app = FastAPI(title="CryptoCosmo Control Room")
config = load_config("config.yaml")
runner = BotRunner(config)
runner.start()


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html = """
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>CryptoCosmo Control Room</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #0b1021;
                --panel: #11172d;
                --accent: #5ee7df;
                --accent-2: #b490ff;
                --text: #e6ecf5;
                --muted: #7c86a5;
                --danger: #ff6b6b;
                --success: #4ade80;
            }
            * { box-sizing: border-box; }
            body {
                margin: 0;
                font-family: 'Space Grotesk', system-ui, -apple-system, sans-serif;
                background: radial-gradient(circle at 20% 20%, rgba(94,231,223,0.08), transparent 35%), radial-gradient(circle at 80% 0%, rgba(180,144,255,0.12), transparent 25%), var(--bg);
                color: var(--text);
                min-height: 100vh;
            }
            .shell {
                max-width: 1200px;
                margin: 0 auto;
                padding: 32px 18px 64px;
            }
            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
            }
            .title {
                display: flex;
                gap: 10px;
                align-items: baseline;
            }
            h1 { margin: 0; font-size: 28px; letter-spacing: -0.01em; }
            .pill { padding: 6px 10px; border-radius: 999px; background: rgba(255,255,255,0.08); color: var(--muted); font-size: 12px; }
            .panel {
                background: var(--panel);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 14px;
                padding: 16px;
                box-shadow: 0 20px 45px rgba(0,0,0,0.4);
            }
            .controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-top: 18px; }
            .field { display: flex; flex-direction: column; gap: 6px; }
            label { font-size: 13px; color: var(--muted); }
            input, select {
                padding: 10px 12px;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.04);
                color: var(--text);
                font-size: 14px;
            }
            .actions { display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
            button {
                border: none;
                border-radius: 12px;
                padding: 10px 14px;
                font-weight: 600;
                cursor: pointer;
                color: #0b1021;
                transition: transform 0.08s ease, box-shadow 0.08s ease;
            }
            button:hover { transform: translateY(-1px); }
            .primary { background: linear-gradient(135deg, var(--accent), var(--accent-2)); box-shadow: 0 10px 25px rgba(94,231,223,0.28); }
            .secondary { background: rgba(255,255,255,0.12); color: var(--text); }
            .danger { background: var(--danger); color: #fff; }
            .grid {
                margin-top: 18px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 14px;
            }
            .stat {
                display: flex;
                flex-direction: column;
                gap: 6px;
            }
            .stat h3 { margin: 0; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
            .stat .value { font-size: 24px; font-weight: 600; }
            .stack { display: flex; flex-direction: column; gap: 10px; }
            .log {
                max-height: 260px;
                overflow: auto;
                padding: 10px;
                background: rgba(0,0,0,0.25);
                border-radius: 10px;
                font-family: 'SFMono-Regular', ui-monospace, Menlo, monospace;
                font-size: 12px;
            }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; }
            th { color: var(--muted); font-weight: 600; }
            .badge { padding: 4px 8px; border-radius: 999px; font-size: 12px; }
            .ok { background: rgba(74,222,128,0.18); color: var(--success); }
            .warn { background: rgba(255,107,107,0.18); color: var(--danger); }
            @media (max-width: 640px) {
                header { flex-direction: column; align-items: flex-start; }
                h1 { font-size: 22px; }
            }
        </style>
    </head>
    <body>
        <div class="shell">
            <header>
                <div class="title">
                    <h1>CryptoCosmo Control Room</h1>
                    <span class="pill">Grid · Risk · Sentiment · Health</span>
                </div>
                <div class="actions">
                    <button class="secondary" onclick="refreshState()">Refresh</button>
                    <button class="danger" onclick="stopBot()">Stop</button>
                    <button class="primary" onclick="startBot()">Start / Restart</button>
                </div>
            </header>

            <div class="panel" style="margin-top:18px;">
                <div class="controls">
                    <div class="field">
                        <label for="mode">Mode</label>
                        <select id="mode">
                            <option value="simulation">Simulation</option>
                            <option value="sandbox">Sandbox (Binance testnet)</option>
                        </select>
                    </div>
                    <div class="field">
                        <label for="symbol">Symbol</label>
                        <select id="symbol">
                            <option>BTC/USDT</option>
                            <option>ETH/USDT</option>
                            <option>SOL/USDT</option>
                            <option>ADA/USDT</option>
                            <option>DOT/USDT</option>
                        </select>
                    </div>
                    <div class="field">
                        <label for="center">Grid Center</label>
                        <input id="center" type="number" step="0.01" />
                    </div>
                    <div class="field">
                        <label for="spacing">Spacing</label>
                        <input id="spacing" type="number" step="0.01" />
                    </div>
                    <div class="field">
                        <label for="lower">Lower Bound</label>
                        <input id="lower" type="number" step="0.01" />
                    </div>
                    <div class="field">
                        <label for="upper">Upper Bound</label>
                        <input id="upper" type="number" step="0.01" />
                    </div>
                    <div class="field">
                        <label for="maxExp">Max Exposure (quote)</label>
                        <input id="maxExp" type="number" step="0.01" />
                    </div>
                </div>
            </div>

            <div class="grid">
                <div class="panel stat">
                    <h3>Price</h3>
                    <div class="value" id="price">-</div>
                    <div id="symbolLabel" style="color:var(--muted);">Pair</div>
                </div>
                <div class="panel stat">
                    <h3>Equity</h3>
                    <div class="value" id="equity">-</div>
                    <div id="balances" style="color:var(--muted);">-</div>
                    <div id="sweeper" style="color:var(--muted);">-</div>
                </div>
                <div class="panel stat">
                    <h3>RiskGuard</h3>
                    <div class="value" id="risk">-</div>
                    <div id="drawdown" style="color:var(--muted);">-</div>
                </div>
                <div class="panel stat">
                    <h3>Grid Window</h3>
                    <div class="value" id="grid">-</div>
                    <div id="gridMeta" style="color:var(--muted);">-</div>
                </div>
                <div class="panel stat">
                    <h3>Sentiment</h3>
                    <div class="value" id="sentiment">-</div>
                    <div id="sentimentDetail" style="color:var(--muted);">-</div>
                </div>
                <div class="panel stat">
                    <h3>Health</h3>
                    <div class="value" id="health">-</div>
                    <div id="healthDetail" style="color:var(--muted);">-</div>
                </div>
            </div>

            <div class="grid" style="grid-template-columns: 2fr 1fr;">
                <div class="panel stack">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <h3 style="margin:0;color:var(--muted);text-transform:uppercase;letter-spacing:0.04em;">Open Orders</h3>
                        <span class="badge ok" id="runningFlag">-</span>
                    </div>
                    <table id="ordersTable">
                        <thead>
                            <tr><th>ID</th><th>Side</th><th>Price</th><th>Amount</th></tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
                <div class="panel stack">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <h3 style="margin:0;color:var(--muted);text-transform:uppercase;letter-spacing:0.04em;">Activity</h3>
                        <button class="secondary" style="padding:6px 10px;font-size:12px;" onclick="applyGrid()">Apply Grid Change</button>
                    </div>
                    <div class="log" id="logFeed"></div>
                </div>
            </div>
        </div>

        <script>
            async function fetchState() {
                const res = await fetch('/api/state');
                const data = await res.json();
                document.getElementById('price').innerText = data.price ? data.price.toFixed(2) : '-';
                document.getElementById('equity').innerText = data.equity ? data.equity.toFixed(2) : '-';
                document.getElementById('balances').innerText = `Base: ${Number(data.balances?.base || 0).toFixed(4)} · Quote: ${Number(data.balances?.quote || 0).toFixed(2)}`;
                document.getElementById('sweeper').innerText = `Cosmetics fund: ${Number(data.sweeper?.fund_balance || 0).toFixed(2)}`;
                document.getElementById('risk').innerText = data.risk?.paused ? 'Paused' : 'Active';
                document.getElementById('risk').className = data.risk?.paused ? 'value warn' : 'value';
                const reason = data.risk?.reason ? ` · ${data.risk.reason}` : '';
                document.getElementById('drawdown').innerText = `Drawdown: ${Number(data.risk?.drawdown_pct || 0).toFixed(2)}%${reason}`;
                document.getElementById('grid').innerText = `${Number(data.grid?.lower || 0).toFixed(2)} – ${Number(data.grid?.upper || 0).toFixed(2)}`;
                document.getElementById('gridMeta').innerText = `Center ${Number(data.grid?.center || 0).toFixed(2)} · Spacing ${Number(data.grid?.spacing || 0).toFixed(2)} · MaxExp ${Number(data.grid?.max_exposure || 0).toFixed(2)}`;
                document.getElementById('sentiment').innerText = `${data.sentiment?.label || '-'}`;
                document.getElementById('sentimentDetail').innerText = `Score ${Number(data.sentiment?.score || 0).toFixed(2)} · News ${data.sentiment?.news_risk || '-'}`;
                document.getElementById('health').innerText = data.health?.healthy ? 'Healthy' : 'Attention';
                document.getElementById('health').className = data.health?.healthy ? 'value ok' : 'value warn';
                document.getElementById('healthDetail').innerText = `Errors: ${data.health?.error_streak || 0}`;
                document.getElementById('symbolLabel').innerText = `${data.symbol} · Tick ${data.tick}`;

                const runningFlag = document.getElementById('runningFlag');
                runningFlag.innerText = data.running ? 'Running' : 'Stopped';
                runningFlag.className = data.running ? 'badge ok' : 'badge warn';

                const tbody = document.querySelector('#ordersTable tbody');
                tbody.innerHTML = '';
                (data.open_orders || []).slice(0, 30).forEach(o => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td>${o.id || '-'}</td><td>${o.side || '-'}</td><td>${Number(o.price || 0).toFixed(2)}</td><td>${Number(o.amount || 0).toFixed(6)}</td>`;
                    tbody.appendChild(tr);
                });

                const logFeed = document.getElementById('logFeed');
                logFeed.innerHTML = (data.logs || []).slice(-50).map(line => `<div>${line}</div>`).join('');

                // Seed control values
                document.getElementById('mode').value = data.mode || 'simulation';
                document.getElementById('symbol').value = data.symbol || 'BTC/USDT';
                if (data.grid) {
                    document.getElementById('center').value = data.grid.center ?? '';
                    document.getElementById('spacing').value = data.grid.spacing ?? '';
                    document.getElementById('lower').value = data.grid.lower ?? '';
                    document.getElementById('upper').value = data.grid.upper ?? '';
                    document.getElementById('maxExp').value = data.grid.max_exposure ?? '';
                }
            }

            async function startBot() {
                const payload = {
                    mode: document.getElementById('mode').value,
                    symbol: document.getElementById('symbol').value,
                    center: parseFloat(document.getElementById('center').value),
                    spacing: parseFloat(document.getElementById('spacing').value),
                    lower: parseFloat(document.getElementById('lower').value),
                    upper: parseFloat(document.getElementById('upper').value),
                    max_exposure: parseFloat(document.getElementById('maxExp').value),
                };
                await fetch('/api/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                await fetchState();
            }

            async function stopBot() {
                await fetch('/api/stop', { method: 'POST' });
                await fetchState();
            }

            async function applyGrid() {
                const payload = {
                    center: parseFloat(document.getElementById('center').value),
                    spacing: parseFloat(document.getElementById('spacing').value),
                    lower: parseFloat(document.getElementById('lower').value),
                    upper: parseFloat(document.getElementById('upper').value),
                    max_exposure: parseFloat(document.getElementById('maxExp').value),
                };
                await fetch('/api/grid', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                await fetchState();
            }

            async function refreshState() { await fetchState(); }
            fetchState();
            setInterval(fetchState, 2000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/api/state")
async def state() -> dict:
    status = runner.get_status()
    return asdict(status)


@app.post("/api/stop")
async def stop_bot() -> dict:
    runner.stop()
    return {"status": "stopped"}


def _to_float(value: Optional[object]) -> Optional[float]:
    try:
        if value is None:
            return None
        val = float(value)
        if val != val:  # NaN check
            return None
        return val
    except (TypeError, ValueError):
        return None


@app.post("/api/start")
async def start_bot(request: Request) -> dict:
    payload = await request.json()
    runner.configure_and_start(
        mode=payload.get("mode"),
        symbol=payload.get("symbol"),
        center=_to_float(payload.get("center")),
        spacing=_to_float(payload.get("spacing")),
        lower=_to_float(payload.get("lower")),
        upper=_to_float(payload.get("upper")),
        max_exposure=_to_float(payload.get("max_exposure")),
    )
    return {"status": "started"}


@app.post("/api/grid")
async def grid_update(request: Request) -> dict:
    payload = await request.json()
    runner.update_grid(
        center=_to_float(payload.get("center")),
        spacing=_to_float(payload.get("spacing")),
        lower=_to_float(payload.get("lower")),
        upper=_to_float(payload.get("upper")),
        max_exposure=_to_float(payload.get("max_exposure")),
    )
    return {"status": "updated"}


if __name__ == "__main__":
    import uvicorn

    # Default to 8787 to avoid conflicts with other local services.
    uvicorn.run("dashboard:app", host="0.0.0.0", port=8787, reload=False)
