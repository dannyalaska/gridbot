# CryptoCosmo Requirements and Project Plan

## 1. Project Overview

**Name:** CryptoCosmo  
**Purpose:**  
A conservative, small scale grid trading bot that:

- Starts in a sandbox environment  
- Buys when price dips into preset grid levels  
- Sells when price rises into higher levels  
- Uses simple agents for safety, tuning, sentiment, and ops health  
- Long term goal: fund small cosmetic purchases in games  

**Design principles:**

- Safety first  
- Simple logic  
- No babysitting  
- Simulation → Sandbox → Live  

---

## 2. Scope and Non Goals

### In Scope

- Integrate with one exchange that has:
  - Sandbox/testnet  
  - API keys with trading permission only  
- Components:
  - GridTrader  
  - RiskGuard  
  - PerformanceAnalyst  
  - SentimentScout  
  - HealthMonitor  
  - ProfitSweeper  
- Modes:
  - `simulation`  
  - `sandbox`  
  - `live` (later)  

### Out of Scope

- Leverage, margin  
- Futures, options  
- Multi exchange arbitrage  
- Social media posting  
- Allowing other people to fund the bot  

---

## 3. High Level Architecture

### Layers

1. **Execution layer:** GridTrader, RiskGuard  
2. **Analysis layer:** PerformanceAnalyst, SentimentScout  
3. **Operations:** HealthMonitor, ProfitSweeper  
4. **Integration:** ExchangeConnector, config, env vars  
5. **Interface:** CLI, logging, eventual dashboard  

### Process Model

Single long running loop:

- GridTrader + RiskGuard every tick  
- Analyst, Sentiment, Health, Sweeper on timers  
- Single process simple scheduling  

---

## 4. Functional Requirements by Component

### 4.1 ExchangeConnector

**Responsibilities:**

- Load API keys from env and use sandbox endpoints  
- Provide:
  - `get_current_price`  
  - `get_balances`  
  - `place_limit_buy`  
  - `place_limit_sell`  
  - `get_open_orders`  
  - `cancel_order`  
- Support `dry_run` flag  
- Graceful error handling  

---

### 4.2 GridTrader

**Inputs:**

- Grid config (center, spacing, levels, size, exposure)  
- Mode (`normal`, `cautious`, `paused`)  
- Prices, open orders  

**Actions:**

- Build grid on start  
- Buy when price hits lower levels  
- Sell when price hits upper levels  
- Respect exposure limits and RiskGuard flags  

---

### 4.3 RiskGuard

**Inputs:**

- Equity vs start  
- Profit/loss  
- Drawdown  
- Short term crash detection  

**Rules:**

- Pause trading on:
  - Daily loss threshold  
  - Excess drawdown  
  - Fast price crashes  
- Outputs:
  - `allow_new_buys`  
  - `mode = paused`  

---

### 4.4 PerformanceAnalyst

**Inputs:**

- Stats over window (PnL, volatility, drawdown, trades)  
- SentimentScout summary  

**Behavior:**

- Every N hours:
  - Adjust grid center  
  - Adjust spacing  
  - Adjust order size  
  - Adjust exposure  
- Very conservative, clamp all values inside allowed ranges  

---

### 4.5 SentimentScout

**Behavior:**

- Runs infrequently (30–60 mins)  
- Pulls fear/greed index or simple sentiment feed  
- Outputs:
  - `sentiment` label  
  - `sentiment_score`  
  - `news_risk`  

Used only as bias, not a signal.

---

### 4.6 HealthMonitor

**Behavior:**

- Periodically check:
  - Time since last price update  
  - Time since last trade  
  - API error spikes  
- On failure:
  - Set bot to `paused`  
  - Log alert  

---

### 4.7 ProfitSweeper

**Behavior:**

- Once per week/month:
  - If realised profit above threshold:
    - Move difference to a “cosmetics fund”  
- In simulation and sandbox: just track internally  
- In live: optionally transfer to stablecoin  

---

## 5. Non Functional Requirements

- **Security:**  
  - API keys in local env only  
  - Trading only, no withdrawal rights  
  - Optional IP whitelist  

- **Reliability:**  
  - Retry logic, backoff  
  - Never silently fail  

- **Observability:**  
  - Log trades, config changes, errors, mode swaps  

- **Config Driven:**  
  - Use `config.yaml` for all core parameters  

- **Testability:**  
  - Simulation mode requires no API keys  

---

## 6. Modes and Environments

### Simulation
- No real API  
- Random walk or historical playback  
- Validates logic before sandbox  

### Sandbox
- Real order book  
- Fake funds  
- Same code path as live except endpoint  

### Live (future)
- Real funds  
- Strict safety rules  
- Tiny initial capital  

---

## 7. Security and Risk Constraints

- Never hard code keys  
- Keys should never have withdrawal permission  
- Local kill switch  
- Very small real money trades in early live mode  

---

## 8. Project Plan

### Phase 1 — Core Simulation
- Create project structure and config  
- Implement GridTrader (sim mode)  
- Implement RiskGuard  
- Implement PerformanceAnalyst  
- Implement HealthMonitor  
- Implement ProfitSweeper  
- CLI to run simulation  

**Deliverable:** Simulated bot prints trades and PnL.

---

### Phase 2 — Sandbox Integration
- Choose sandbox exchange  
- Generate sandbox API keys  
- Implement ExchangeConnector  
- Add sandbox mode  
- Run small grid in sandbox  

**Deliverable:** Realistic fake trading with logs.

---

### Phase 3 — Sentiment + Analyst Enhancements
- Implement SentimentScout  
- Integrate into PerformanceAnalyst  
- Improve parameter tuning logic  

---

### Phase 4 — Optional LLM Supervisor
- JSON schema for decisions  
- LLM guided tuning  
- Hard clamping for safe ranges  

---

### Phase 5 — Live Small Deployment (Later)
- Live keys with trading only  
- Tiny trade sizes  
- Confirm before starting live mode  

**Deliverable:** Safe, small scale live version.

