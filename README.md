# 🥈 SilverEdge — MCX Silver Integrated Trading Platform

Multi-user web dashboard for algorithmic silver futures trading on MCX.  
**Pipeline:** Smart Allocator → Entry Engine (15 filters) → Exit Engine (15 strategies) → Dhan Paper/Live Orders

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser  ─── React SPA (port 3000)                              │
│    ├─ Login / Signup (JWT auth, per-user isolation)              │
│    ├─ Dashboard  (live LTP, allocation, open trade, signals)     │
│    ├─ Trades     (full history with P&L)                         │
│    ├─ Signals    (all entry/exit signals with filter breakdown)  │
│    └─ Settings   (update capital)                                │
└──────────────────────────┬───────────────────────────────────────┘
                           │ REST + WebSocket
┌──────────────────────────▼───────────────────────────────────────┐
│  FastAPI Backend  (port 8000)                                    │
│                                                                  │
│  ┌─ SmartAllocator ────────────────────────────────────────────┐ │
│  │  AngelOne REST → best contract, LTP, volatility, margin    │ │
│  │  → AllocationResult (token, symbol, lots, qty, vol_level)  │ │
│  └──────────────────────────────────────────────────────────── │ │
│                                                                  │
│  ┌─ SharedFeed ────────────────────────────────────────────────┐ │
│  │  ONE AngelOne WebSocket → fan-out ticks/bars to all users  │ │
│  └──────────────────────────────────────────────────────────── │ │
│                                                                  │
│  ┌─ TradingSession (per user) ─────────────────────────────────┐ │
│  │  On bar  → EntryEngine.evaluate() → Dhan BUY order         │ │
│  │  On tick → ExitEngine.evaluate()  → Dhan SELL order        │ │
│  │  Appends SignalRecord + TradeRecord to user's log           │ │
│  └──────────────────────────────────────────────────────────── │ │
│                                                                  │
│  ┌─ Auth ──────────────────────────────────────────────────────┐ │
│  │  JWT tokens, per-user balance, isolated trade/signal logs  │ │
│  └──────────────────────────────────────────────────────────── │ │
└──────────────────────────────────────────────────────────────────┘
           │ AngelOne WS feed           │ Dhan REST orders
     Angel One SmartAPI             Dhan v2 API
```

---

## Quick Start

### 1. Backend

```bash
cd silver_trading_platform/backend

# Create & activate venv
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env — fill in Angel One + Dhan keys

# Run
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 2. Frontend

```bash
cd silver_trading_platform/frontend

npm install
npm run dev
```

Open: http://localhost:3000

---

## Credentials Required

### Angel One SmartAPI
- API Key, Client ID, Password, TOTP Secret
- Used for: contract search, LTP, volatility (OHLC), historical candles, WebSocket feed

### Dhan API
- Client ID, Access Token
- Used for: order placement (BUY/SELL)
- Set `PAPER_TRADING=true` to simulate without real orders

---

## Per-User Flow

1. **Sign Up** → enter username, email, password, starting capital
2. **Dashboard** → click **Recalculate** to run SmartAllocator (picks best Silver contract, computes lot size from balance + volatility)
3. **Start Engine** → allocates capital, subscribes to live feed, begins watching for entry signals
4. **Auto Entry** → when ≥3 of 15 filters agree at ≥68% confidence → BUY/SELL order on Dhan (paper or live)
5. **Auto Exit** → when ≥3 of 15 strategies agree at ≥70% confidence (or hard SL/target) → close order on Dhan
6. **Trade recorded** → appears in Trades page with full P&L
7. **Signal recorded** → appears in Signals page with filter breakdown
8. **Balance updated** → P&L added/subtracted from user balance after each closed trade

Multiple users can run simultaneously — each has isolated capital, allocation, trades, signals.

---

## Entry Engine — 15 Filters

| Filter | Logic |
|--------|-------|
| Trading Hours Gate | Blocks entry outside 09:00–22:45 IST |
| Minimum Bars Guard | Requires ≥50 bars before any entry |
| Spread Guard | Rejects if bid-ask spread > 0.10% |
| ATR Risk-Reward | Rejects if SL > 2% of price |
| EMA Trend Alignment | EMA(9) vs EMA(21) cross/alignment |
| ADX Trend Strength | ADX > 20 + DI direction |
| RSI Zone Filter | Long: 45-70, Short: 30-55 |
| MACD Momentum | Histogram direction + line cross |
| BB Expansion | Bands expanding + price zone |
| SuperTrend Confirm | SuperTrend flip or continuation |
| Parabolic SAR Entry | PSAR flip + continuation |
| Chandelier Setup | Price vs long/short stops |
| Stochastic Pullback | K/D cross from OS/OB zones |
| CCI Breakout | CCI crossing ±100 |
| Volume Confirmation | 30% above avg = confirmation |

---

## Exit Engine — 15 Strategies

| Strategy | Logic |
|----------|-------|
| Hard Stop/Target | Immediate exit at SL or target |
| Time-Based Exit | Max 240 min + EOD 15-min warning |
| Partial Scale-Out | 3-level RR exits (1.0x, 1.8x, 2.5x) |
| Break-Even Manager | Move SL to entry at 0.8x RR |
| ATR Trailing Stop | Dynamic trail using ATR |
| Chandelier Exit | Chandelier stop levels |
| SuperTrend Flip | Trend direction change |
| Parabolic SAR | PSAR flip |
| EMA Cross Reversal | Fast EMA crosses slow |
| RSI Exhaustion | Overbought/oversold + divergence |
| MACD Reversal | Histogram/line reversal |
| BB Exit | Price at band extreme + squeeze |
| ADX Trend Collapse | ADX falling + DI cross |
| CCI Reversal | Exiting OB/OS extreme zones |
| Stochastic Exit | K/D cross from extreme zones |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/signup` | Create account |
| POST | `/api/auth/login` | Login → JWT token |
| GET  | `/api/me` | Current user + allocation + open trade |
| PUT  | `/api/me/balance` | Update capital |
| POST | `/api/allocate` | Run SmartAllocator for current balance |
| POST | `/api/trading/start` | Start TradingSession |
| POST | `/api/trading/stop` | Stop TradingSession |
| GET  | `/api/trading/status` | Session status, open trade, LTP |
| GET  | `/api/signals` | All signals for current user |
| GET  | `/api/trades` | All trades for current user |
| GET  | `/api/stats` | P&L stats for current user |
| GET  | `/api/feed/latest` | Latest LTP + bar count |
| WS   | `/ws/{user_id}` | Real-time ticks + trade events |

---

## Notes

- **In-memory storage** — users/trades/signals reset on restart. Replace `users_db`, `signals_log`, `trades_log` with a real DB (SQLite/Postgres) for production.
- **Single WS connection** — SharedFeed uses one Angel One WebSocket for all users. Update `SILVER_TOKEN_LIST` if the front-month token changes.
- **Paper trading** — all orders simulate locally with 0.05% slippage + ₹20 brokerage per leg.
- **Live trading** — set `PAPER_TRADING=false` and ensure Dhan API credentials are correct.
