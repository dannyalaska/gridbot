import os
from pathlib import Path
from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from cryptocosmo.bot_runner import BotRunner
from cryptocosmo.config import load_config
from cryptocosmo.metrics import render_prometheus


app = FastAPI(title="CryptoCosmo Control Room")
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
config = load_config("config.yaml")
runner = BotRunner(config)
AUTO_START = os.getenv("GRIDBOT_AUTOSTART", "").strip().lower() in {"1", "true", "yes", "on"}
if AUTO_START:
    runner.start()
API_KEY = os.getenv("DASHBOARD_API_KEY")


def _is_local_request(request: Request) -> bool:
    if not request.client:
        return False
    host = request.client.host or ""
    if host in {"127.0.0.1", "::1", "localhost"}:
        return True
    if host.startswith("127.") or host.startswith("::ffff:127."):
        return True
    return False


@app.middleware("http")
async def localhost_only(request: Request, call_next):
    if not _is_local_request(request):
        return PlainTextResponse("Localhost access only", status_code=403)
    return await call_next(request)


def _require_api_key(request: Request) -> None:
    if not API_KEY:
        return
    provided = request.headers.get("X-API-Key", "")
    auth_header = request.headers.get("Authorization", "")
    if not provided and auth_header.startswith("Bearer "):
        provided = auth_header[len("Bearer ") :].strip()
    if not provided or provided != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    key_required = "true" if API_KEY else "false"
    html = """
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>CryptoCosmo Control Room</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="/static/dashboard.css">
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
            <div class="notice" id="notice" style="display:none;"></div>

            <div class="panel" style="margin-top:18px;">
                <div class="controls">
                    <div class="field">
                        <label for="mode">Mode</label>
                        <select id="mode">
                            <option value="simulation">Simulation</option>
                            <option value="sandbox">Sandbox (Binance testnet)</option>
                            <option value="live">Live (Binance spot)</option>
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
                    <div class="field">
                        <label for="apiKey">API Key (optional)</label>
                        <input id="apiKey" type="password" placeholder="X-API-Key header" />
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
                    <h3>Risk Council</h3>
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
                <div class="panel chart">
                    <div class="panel-head">
                        <h3>Performance History</h3>
                        <span class="badge subtle" id="historySpan">-</span>
                    </div>
                    <canvas id="performanceChart"></canvas>
                    <div class="legend">
                        <span class="legend-item"><span class="dot equity"></span>Equity</span>
                        <span class="legend-item"><span class="dot price"></span>Price</span>
                    </div>
                </div>
                <div class="panel chart">
                    <div class="panel-head">
                        <h3>Portfolio Allocation</h3>
                        <span class="badge subtle" id="allocationTotal">-</span>
                    </div>
                    <div class="allocation-bar">
                        <div class="allocation-segment base" id="allocationBase"></div>
                        <div class="allocation-segment quote" id="allocationQuote"></div>
                    </div>
                    <div class="allocation-labels" id="allocationLabels">-</div>
                    <div class="mini-metrics">
                        <div>
                            <div class="metric-label">Base value</div>
                            <div class="metric-value" id="baseValue">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Quote value</div>
                            <div class="metric-value" id="quoteValue">-</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="grid" style="grid-template-columns: 1fr 1fr;">
                <div class="panel chart">
                    <div class="panel-head">
                        <h3>Grid Map</h3>
                        <span class="badge subtle" id="gridRangeLabel">-</span>
                    </div>
                    <canvas id="gridChart"></canvas>
                    <div class="legend">
                        <span class="legend-item"><span class="dot center"></span>Center</span>
                        <span class="legend-item"><span class="dot buy"></span>Buys</span>
                        <span class="legend-item"><span class="dot sell"></span>Sells</span>
                    </div>
                </div>
                <div class="panel chart">
                    <div class="panel-head">
                        <h3>Risk & Limits</h3>
                        <span class="badge subtle" id="riskStatus">-</span>
                    </div>
                    <div class="risk-grid">
                        <div>
                            <div class="metric-label">Loss</div>
                            <div class="metric-value" id="lossPct">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Drawdown</div>
                            <div class="metric-value" id="drawdownPct">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Crash</div>
                            <div class="metric-value" id="crashPct">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Exposure cap</div>
                            <div class="metric-value" id="maxExposure">-</div>
                        </div>
                    </div>
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
            const apiKeyRequired = __API_KEY_REQUIRED__;
            let historyCache = [];
            let lastState = null;

            function setNotice(message, isError = false) {
                const notice = document.getElementById('notice');
                if (!notice) return;
                if (!message) {
                    notice.style.display = 'none';
                    notice.textContent = '';
                    notice.className = 'notice';
                    return;
                }
                notice.style.display = 'block';
                notice.textContent = message;
                notice.className = isError ? 'notice error' : 'notice';
            }

            function buildHeaders(needsJson = false) {
                const headers = {};
                if (needsJson) {
                    headers['Content-Type'] = 'application/json';
                }
                const apiKey = document.getElementById('apiKey')?.value?.trim();
                if (apiKey) {
                    headers['X-API-Key'] = apiKey;
                }
                return headers;
            }

            async function request(path, options = {}) {
                const needsJson = Boolean(options.body);
                const headers = Object.assign({}, buildHeaders(needsJson), options.headers || {});
                const res = await fetch(path, Object.assign({}, options, { headers }));
                if (!res.ok) {
                    const text = await res.text();
                    const message = text || `Request failed (${res.status})`;
                    setNotice(message, true);
                } else if (!['/api/state', '/api/history'].includes(path)) {
                    setNotice('Action completed', false);
                }
                return res;
            }

            if (apiKeyRequired) {
                setNotice('API key required for start/stop/grid updates.', false);
            }

            function getPalette() {
                const styles = getComputedStyle(document.documentElement);
                return {
                    equity: styles.getPropertyValue('--accent').trim() || '#5ee7df',
                    price: styles.getPropertyValue('--accent-2').trim() || '#b490ff',
                    buy: styles.getPropertyValue('--accent').trim() || '#5ee7df',
                    sell: styles.getPropertyValue('--danger').trim() || '#ff6b6b',
                    center: styles.getPropertyValue('--accent-3').trim() || '#ffd166',
                    grid: 'rgba(255,255,255,0.08)',
                };
            }

            function prepareCanvas(canvas) {
                const rect = canvas.getBoundingClientRect();
                const dpr = window.devicePixelRatio || 1;
                canvas.width = rect.width * dpr;
                canvas.height = rect.height * dpr;
                const ctx = canvas.getContext('2d');
                ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                return { ctx, width: rect.width, height: rect.height };
            }

            function drawPerformanceChart(history) {
                const canvas = document.getElementById('performanceChart');
                if (!canvas) return;
                const { ctx, width, height } = prepareCanvas(canvas);
                ctx.clearRect(0, 0, width, height);
                if (!history.length) {
                    ctx.fillStyle = 'rgba(255,255,255,0.35)';
                    ctx.font = '12px Space Grotesk, sans-serif';
                    ctx.fillText('Waiting for history...', 12, 20);
                    return;
                }
                const baseEquity = history[0].equity || 1;
                const basePrice = history[0].price || 1;
                const equitySeries = history.map(point => (point.equity || 0) / baseEquity * 100);
                const priceSeries = history.map(point => (point.price || 0) / basePrice * 100);
                const minVal = Math.min(...equitySeries, ...priceSeries);
                const maxVal = Math.max(...equitySeries, ...priceSeries);
                const pad = (maxVal - minVal) * 0.1 || 1;
                const yMin = minVal - pad;
                const yMax = maxVal + pad;
                const palette = getPalette();

                ctx.strokeStyle = palette.grid;
                ctx.lineWidth = 1;
                for (let i = 1; i <= 3; i += 1) {
                    const y = (height / 4) * i;
                    ctx.beginPath();
                    ctx.moveTo(0, y);
                    ctx.lineTo(width, y);
                    ctx.stroke();
                }

                const baselineY = height - ((100 - yMin) / (yMax - yMin)) * height;
                ctx.strokeStyle = 'rgba(255,255,255,0.18)';
                ctx.beginPath();
                ctx.moveTo(0, baselineY);
                ctx.lineTo(width, baselineY);
                ctx.stroke();

                const xStep = history.length > 1 ? width / (history.length - 1) : width;
                function drawSeries(series, color) {
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    series.forEach((value, index) => {
                        const x = index * xStep;
                        const y = height - ((value - yMin) / (yMax - yMin)) * height;
                        if (index === 0) {
                            ctx.moveTo(x, y);
                        } else {
                            ctx.lineTo(x, y);
                        }
                    });
                    ctx.stroke();
                }

                drawSeries(priceSeries, palette.price);
                drawSeries(equitySeries, palette.equity);
            }

            function drawGridMap(state) {
                const canvas = document.getElementById('gridChart');
                if (!canvas) return;
                const { ctx, width, height } = prepareCanvas(canvas);
                ctx.clearRect(0, 0, width, height);
                if (!state) {
                    return;
                }

                const price = Number(state.price || 0);
                const lower = Number(state.grid?.lower || 0);
                const upper = Number(state.grid?.upper || 0);
                const center = Number(state.grid?.center || 0);
                let minPrice = Math.min(...[price, lower, center].filter(val => Number.isFinite(val) && val > 0));
                let maxPrice = Math.max(...[price, upper, center].filter(val => Number.isFinite(val) && val > 0));
                if (!Number.isFinite(minPrice) || !Number.isFinite(maxPrice) || minPrice === maxPrice) {
                    minPrice = price * 0.98 || 0;
                    maxPrice = price * 1.02 || 1;
                }
                const pad = (maxPrice - minPrice) * 0.08 || 1;
                minPrice -= pad;
                maxPrice += pad;

                function yFor(val) {
                    return height - ((val - minPrice) / (maxPrice - minPrice)) * height;
                }

                const palette = getPalette();
                ctx.strokeStyle = palette.grid;
                ctx.lineWidth = 1;
                for (let i = 1; i <= 4; i += 1) {
                    const y = (height / 5) * i;
                    ctx.beginPath();
                    ctx.moveTo(0, y);
                    ctx.lineTo(width, y);
                    ctx.stroke();
                }

                if (lower) {
                    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
                    ctx.beginPath();
                    ctx.moveTo(0, yFor(lower));
                    ctx.lineTo(width, yFor(lower));
                    ctx.stroke();
                }
                if (upper) {
                    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
                    ctx.beginPath();
                    ctx.moveTo(0, yFor(upper));
                    ctx.lineTo(width, yFor(upper));
                    ctx.stroke();
                }
                if (center) {
                    ctx.strokeStyle = palette.center;
                    ctx.beginPath();
                    ctx.moveTo(0, yFor(center));
                    ctx.lineTo(width, yFor(center));
                    ctx.stroke();
                }

                if (price) {
                    ctx.strokeStyle = 'rgba(94,231,223,0.6)';
                    ctx.setLineDash([6, 6]);
                    ctx.beginPath();
                    ctx.moveTo(0, yFor(price));
                    ctx.lineTo(width, yFor(price));
                    ctx.stroke();
                    ctx.setLineDash([]);
                }

                const orders = state.open_orders || [];
                orders.forEach((order, idx) => {
                    const side = (order.side || '').toLowerCase();
                    const orderPrice = Number(order.price || 0);
                    if (!orderPrice) return;
                    const x = side === 'sell' ? width * 0.72 : width * 0.28;
                    const y = yFor(orderPrice);
                    ctx.fillStyle = side === 'sell' ? palette.sell : palette.buy;
                    ctx.beginPath();
                    ctx.arc(x + (idx % 3) * 6 - 6, y, 3, 0, Math.PI * 2);
                    ctx.fill();
                });

                ctx.fillStyle = 'rgba(255,255,255,0.6)';
                ctx.font = '11px Space Grotesk, sans-serif';
                ctx.fillText(`Price ${price ? price.toFixed(2) : '-'}`, 10, 16);
            }

            function updateAllocation(data) {
                const price = Number(data.price || 0);
                const base = Number(data.balances?.base || 0);
                const quote = Number(data.balances?.quote || 0);
                const baseValue = base * price;
                const total = baseValue + quote;
                const basePct = total > 0 ? (baseValue / total) * 100 : 0;
                const quotePct = total > 0 ? 100 - basePct : 0;
                const allocationBase = document.getElementById('allocationBase');
                const allocationQuote = document.getElementById('allocationQuote');
                if (allocationBase && allocationQuote) {
                    allocationBase.style.width = `${basePct}%`;
                    allocationQuote.style.width = `${quotePct}%`;
                }
                const allocationLabels = document.getElementById('allocationLabels');
                if (allocationLabels) {
                    allocationLabels.innerText = `Base ${basePct.toFixed(1)}% · Quote ${quotePct.toFixed(1)}%`;
                }
                const allocationTotal = document.getElementById('allocationTotal');
                if (allocationTotal) {
                    allocationTotal.innerText = total ? `Total ${total.toFixed(2)}` : '-';
                }
                const baseValueEl = document.getElementById('baseValue');
                const quoteValueEl = document.getElementById('quoteValue');
                if (baseValueEl) baseValueEl.innerText = baseValue ? baseValue.toFixed(2) : '-';
                if (quoteValueEl) quoteValueEl.innerText = quote ? quote.toFixed(2) : '-';
            }

            function updateRiskPanel(data) {
                const lossPct = Number(data.risk?.loss_pct || 0).toFixed(2);
                const drawdownPct = Number(data.risk?.drawdown_pct || 0).toFixed(2);
                const crashPct = Number(data.risk?.crash_pct || 0).toFixed(2);
                const maxExposure = Number(data.grid?.max_exposure || 0).toFixed(2);
                const riskStatus = document.getElementById('riskStatus');
                if (riskStatus) {
                    riskStatus.innerText = data.risk?.paused ? 'Paused' : 'Active';
                    riskStatus.className = data.risk?.paused ? 'badge warn' : 'badge ok';
                }
                const lossEl = document.getElementById('lossPct');
                const drawdownEl = document.getElementById('drawdownPct');
                const crashEl = document.getElementById('crashPct');
                const exposureEl = document.getElementById('maxExposure');
                if (lossEl) lossEl.innerText = `${lossPct}%`;
                if (drawdownEl) drawdownEl.innerText = `${drawdownPct}%`;
                if (crashEl) crashEl.innerText = `${crashPct}%`;
                if (exposureEl) exposureEl.innerText = maxExposure;
            }

            async function fetchHistory() {
                const res = await request('/api/history?limit=240');
                if (!res.ok) {
                    return;
                }
                const payload = await res.json();
                historyCache = payload.history || [];
                drawPerformanceChart(historyCache);
                const historySpan = document.getElementById('historySpan');
                if (historySpan) {
                    historySpan.innerText = historyCache.length ? `Last ${historyCache.length} pts` : '-';
                }
            }

            async function fetchState() {
                const res = await request('/api/state');
                if (!res.ok) {
                    return;
                }
                const data = await res.json();
                lastState = data;
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

                updateAllocation(data);
                updateRiskPanel(data);
                drawGridMap(data);
                const gridRangeLabel = document.getElementById('gridRangeLabel');
                if (gridRangeLabel) {
                    gridRangeLabel.innerText = data.grid ? `${Number(data.grid.lower || 0).toFixed(2)} – ${Number(data.grid.upper || 0).toFixed(2)}` : '-';
                }

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
                if (apiKeyRequired && !document.getElementById('apiKey').value.trim()) {
                    setNotice('API key required to start the bot.', true);
                    return;
                }
                const payload = {
                    mode: document.getElementById('mode').value,
                    symbol: document.getElementById('symbol').value,
                    center: parseFloat(document.getElementById('center').value),
                    spacing: parseFloat(document.getElementById('spacing').value),
                    lower: parseFloat(document.getElementById('lower').value),
                    upper: parseFloat(document.getElementById('upper').value),
                    max_exposure: parseFloat(document.getElementById('maxExp').value),
                };
                await request('/api/start', { method: 'POST', body: JSON.stringify(payload) });
                await fetchState();
                await fetchHistory();
            }

            async function stopBot() {
                if (apiKeyRequired && !document.getElementById('apiKey').value.trim()) {
                    setNotice('API key required to stop the bot.', true);
                    return;
                }
                await request('/api/stop', { method: 'POST' });
                await fetchState();
                await fetchHistory();
            }

            async function applyGrid() {
                if (apiKeyRequired && !document.getElementById('apiKey').value.trim()) {
                    setNotice('API key required to update the grid.', true);
                    return;
                }
                const payload = {
                    center: parseFloat(document.getElementById('center').value),
                    spacing: parseFloat(document.getElementById('spacing').value),
                    lower: parseFloat(document.getElementById('lower').value),
                    upper: parseFloat(document.getElementById('upper').value),
                    max_exposure: parseFloat(document.getElementById('maxExp').value),
                };
                await request('/api/grid', { method: 'POST', body: JSON.stringify(payload) });
                await fetchState();
                await fetchHistory();
            }

            async function refreshState() { await fetchState(); }
            fetchState();
            fetchHistory();
            setInterval(fetchState, 2000);
            setInterval(fetchHistory, 10000);

            window.addEventListener('resize', () => {
                drawPerformanceChart(historyCache);
                drawGridMap(lastState);
            });
        </script>
    </body>
    </html>
    """
    html = html.replace("__API_KEY_REQUIRED__", key_required)
    return HTMLResponse(content=html)


@app.get("/api/state")
async def state() -> dict:
    status = runner.get_status()
    return asdict(status)


@app.get("/api/history")
async def history(limit: int = 300) -> dict:
    limit = max(10, min(limit, 1000))
    return {"history": runner.get_history(limit=limit)}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    status = runner.get_status()
    payload = render_prometheus(runner.get_metrics(), {"mode": status.mode, "symbol": status.symbol})
    return PlainTextResponse(content=payload)


@app.post("/api/stop")
async def stop_bot(request: Request) -> dict:
    _require_api_key(request)
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
    _require_api_key(request)
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
    _require_api_key(request)
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
    uvicorn.run("dashboard:app", host="127.0.0.1", port=8787, reload=False)
