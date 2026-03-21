# SilverEdge — Complete Workflow & System Guide

---

## System Overview

```
User Browser
    │
    │  HTTP / WebSocket
    ▼
FastAPI Backend (port 8000)
    │
    ├─── SmartAllocator ──────► Angel One REST API
    │       (capital sizing)         (contract search,
    │                                 LTP, OHLC, margin)
    │
    ├─── SharedFeed ──────────► Angel One WebSocket
    │       (live ticks/bars)        (real-time price stream)
    │
    ├─── TradingSession ──────► Entry Engine (15 filters)
    │    (per user)           └► Exit Engine (15 strategies)
    │
    └─── Dhan Execution ──────► Dhan v2 REST API
            (orders)                (paper or live orders)
```

---

## Step-by-Step Setup

### Prerequisites

| Tool | Min Version | Check |
|------|-------------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Angel One account | — | SmartAPI access enabled |
| Dhan account | — | API access enabled |

---

### Step 1 — Credentials

Copy the env template and fill in your keys:

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` in any editor:

```env
# Angel One SmartAPI (https://smartapi.angelbroking.com)
ANGEL_ONE_API_KEY=your_api_key
ANGEL_ONE_CLIENT_ID=your_client_id        # e.g. A12345
ANGEL_ONE_PASSWORD=your_login_password
ANGEL_ONE_TOTP_SECRET=your_totp_secret    # Base32 secret from authenticator app

# Dhan (https://api.dhan.co)
DHAN_CLIENT_ID=your_dhan_client_id
DHAN_ACCESS_TOKEN=your_dhan_token

# Security — generate this once:
# python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=paste_generated_secret_here

# Trading Mode
PAPER_TRADING=true    # Change to false for live orders
```

---

### Step 2 — Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Mac/Linux
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

✅ Backend running at: `http://localhost:8000`  
✅ Interactive API docs: `http://localhost:8000/docs`

---

### Step 3 — Frontend

```bash
cd frontend

npm install
npm run dev
```

✅ Dashboard at: `http://localhost:3000`

---

### One-Command Start (after first setup)

**Mac / Linux:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```
Double-click start.bat
```

---

## User Workflow (Dashboard)

### 1. Create Account

- Open `http://localhost:3000`
- Click **Create account**
- Enter username, email, password
- Enter your **starting capital** in ₹ (e.g. ₹1,00,000)
- Each user has completely isolated capital, trades, and signals

---

### 2. Smart Allocation

After logging in, go to **Dashboard** → click **Recalculate**

The allocator will:

```
1. Login to Angel One
2. Search SILVER, SILVERM, SILVERMIC futures
3. Filter contracts with > 10 days to expiry
4. Pick highest-volume contract per type
5. Fetch live LTP
6. Calculate volatility:
   a. Try intraday OHLC (high-low range / close × 100)
   b. Fallback → historical daily candles → average true range
7. Assign risk tier:
   HIGH   (ATR ≥ 2%)  → risk 30-40% of capital
   NORMAL (ATR ≥ 1%)  → risk 40-50% of capital
   LOW    (ATR < 1%)  → risk 60-70% of capital
8. Compute margin per lot (from Angel One margin API, fallback 15% estimate)
9. Greedy allocation: max lots within risk budget
```

**Example output for ₹1,00,000 at NORMAL volatility:**
```
Contract:       SILVER05MAY26FUT
LTP:            ₹92,450
Volatility:     NORMAL (ATR 1.42%)
Risk Amount:    ₹45,000 (45%)
Margin/Lot:     ₹41,602
Lots:           1
Total Qty:      30 units (1 lot × 30 kg)
Total Margin:   ₹41,602
Remaining Cash: ₹3,398
```

---

### 3. Start the Engine

Click **▶ Start Engine** in the top bar.

This:
- Runs SmartAllocator for your current balance
- Subscribes your session to the live price feed
- Entry Engine begins watching each completed 1-minute bar
- Exit Engine begins watching each live tick for open trades

---

### 4. Entry Signal Generation

On every completed **1-minute bar**:

```
PRIORITY GATES (all must pass — any failure = WAIT):
  P0 — Trading Hours Gate   →  09:00 to 22:45 IST only
  P1 — Minimum Bars Guard   →  Need ≥ 50 bars of history
  P2 — Spread Guard         →  Bid-ask spread < 0.10%
  P3 — ATR Risk-Reward      →  SL distance < 2% of price

VOTED FILTERS (11 total):
  EMA Trend Alignment       →  EMA(9) vs EMA(21)
  ADX Trend Strength        →  ADX > 20 + DI direction
  RSI Zone Filter           →  Long: RSI 45-70 / Short: 30-55
  MACD Momentum             →  Histogram direction
  BB Expansion              →  Bands expanding + price zone
  SuperTrend Confirm        →  ST direction / flip
  Parabolic SAR Entry       →  PSAR flip / continuation
  Chandelier Setup          →  Price vs chan stops
  Stochastic Pullback       →  K/D cross from OS/OB
  CCI Breakout              →  CCI crossing ±100
  Volume Confirmation       →  Volume > 130% of 20-bar avg

ENTRY TRIGGERED when:
  ≥ 3 filters agree in same direction
  AND average confidence ≥ 68%
  (OR 2 filters with avg confidence ≥ 85%)
```

**When triggered:**
- Signal logged with direction, price, confidence, filter list
- BUY or SELL order placed on Dhan (paper or live)
- Stop-loss = entry ± (ATR × 1.5)
- Target = entry ± (SL distance × 2.5)
- Trade record created, visible on dashboard immediately

---

### 5. Exit Signal Generation

On every **live tick** (while a trade is open):

```
PRIORITY EXITS (immediate, no vote needed):
  P0 — Hard SL / Target     →  Price crosses SL or target
  P1 — Time-Based Exit      →  Trade > 240 min OR < 15 min to 23:00
  P2 — Partial Scale-Out    →  1.0x RR (40%), 1.8x (35%), 2.5x (25%)
  P3 — Break-Even Manager   →  Move SL to entry at 0.8x RR

VOTED STRATEGIES (11 total):
  ATR Trailing Stop         →  Dynamic trail from peak price
  Chandelier Exit           →  Chandelier long/short stop breach
  SuperTrend Flip           →  ST direction reverses
  Parabolic SAR Flip        →  PSAR reverses direction
  EMA Cross Reversal        →  EMA(5) crosses EMA(9) against trade
  RSI Exhaustion            →  OB/OS levels + divergence
  MACD Reversal             →  Histogram flips against trade
  BB Exit                   →  Price at band extreme / BB squeeze
  ADX Trend Collapse        →  ADX drops below 20 from > 25
  CCI Reversal              →  CCI exits OB/OS extreme
  Stochastic Exit           →  K/D cross from extreme zone

EXIT TRIGGERED when:
  ≥ 3 strategies agree      AND avg confidence ≥ 70%
  (OR 2 strategies with avg confidence ≥ 83%)
```

**When triggered:**
- Exit signal logged
- SELL (or BUY for short) order placed on Dhan
- P&L calculated: (exit - entry) × qty − brokerage × 2
- User balance updated
- Trade marked CLOSED

---

### 6. Monitoring

**Dashboard:**
- Live LTP updating via WebSocket
- Open trade panel with unrealised P&L bar
- Recent signals feed with confidence scores and filter tags

**Trades page:**
- Full trade history with entry/exit prices, lots, SL, target, P&L, exit reason

**Signals page:**
- All entry/exit signals with filter breakdown
- Filter by ENTRY or EXIT

---

## Multi-User Isolation

| Resource | Isolated per user? |
|----------|--------------------|
| Balance | ✅ Yes |
| Allocation (lots/contract) | ✅ Yes — based on their balance |
| Open trades | ✅ Yes |
| Trade history | ✅ Yes |
| Signal log | ✅ Yes |
| Angel One WS feed | ❌ Shared (one connection, same price data) |
| Dhan orders | ✅ Separate orders per user session |

Multiple users can run simultaneously. User A's ₹50,000 and User B's ₹2,00,000 will get different lot allocations based on their respective capital and the same live volatility reading.

---

## Paper vs Live Trading

| Setting | Behaviour |
|---------|-----------|
| `PAPER_TRADING=true` | Orders simulated locally; 0.05% slippage applied; ₹20 brokerage per leg deducted from P&L |
| `PAPER_TRADING=false` | Real orders placed via Dhan v2 REST API |

**To switch:** edit `backend/.env` → `PAPER_TRADING=false` → restart backend.

---

## File Structure

```
silveredge_platform/
├── start.sh                    ← One-command launcher (Mac/Linux)
├── start.bat                   ← One-command launcher (Windows)
├── README.md                   ← Quick-start reference
├── WORKFLOW.md                 ← This file
│
├── backend/
│   ├── main.py                 ← FastAPI app (all logic in one file)
│   ├── requirements.txt        ← Python dependencies
│   └── .env.example            ← Credential template
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx            ← React entry point
        └── App.jsx             ← Full dashboard (all pages)
```

---

## API Reference (key endpoints)

```
POST  /api/auth/signup          Body: {username, email, password, balance}
POST  /api/auth/login           Form: username + password → JWT token

GET   /api/me                   Current user + open trade + allocation
PUT   /api/me/balance           Body: {balance: 150000}

POST  /api/allocate             Run SmartAllocator for current balance
POST  /api/trading/start        Start TradingSession for current user
POST  /api/trading/stop         Stop TradingSession
GET   /api/trading/status       {active, allocation, open_trade, feed_ltp}

GET   /api/signals              All signals for current user (newest first)
GET   /api/trades               All trades for current user (newest first)
GET   /api/stats                {total_trades, win_rate, total_pnl, ...}

WS    /ws/{user_id}             Real-time: TICK events + ENTRY/EXIT events
```

All endpoints (except auth) require: `Authorization: Bearer <token>`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Angel One login failed" | Check API key, client ID, password, TOTP secret in `.env` |
| "Could not fetch LTP — market may be closed" | Markets open Mon–Fri 09:00–23:30 IST; try during market hours |
| "Only N bars (need 50)" | Entry engine needs 50 bars; wait ~50 minutes after market open |
| WebSocket shows "Feed offline" | Angel One WS credentials issue; check backend logs |
| Frontend shows blank page | Run `npm install` in `frontend/` directory |
| Port 8000 already in use | `lsof -ti:8000 | xargs kill` then restart |
| Port 3000 already in use | `lsof -ti:3000 | xargs kill` then restart |
| Balance not updating after trade | Refresh page; balance updates after exit execution |

---

## Production Notes

- **Storage:** User data, trades, and signals are currently in-memory (reset on restart). For production, replace `users_db`, `signals_log`, `trades_log` dicts with SQLite (`aiosqlite`) or PostgreSQL (`asyncpg`).
- **Angel One token:** WS JWT expires; the backend re-logins every 3rd reconnect attempt automatically.
- **Scaling:** SharedFeed handles one token at a time. To trade multiple symbols simultaneously, instantiate multiple SharedFeed instances.
- **HTTPS:** For production deployment, put Nginx in front with SSL termination; update CORS origins in `main.py`.
