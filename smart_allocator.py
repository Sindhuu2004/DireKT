"""
MCX Silver Smart Allocator - Pure Backend REST API (FastAPI)
Run:  python smart_allocator.py
Base: http://localhost:5000
Docs: http://localhost:5000/docs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from SmartApi import SmartConnect
import pyotp
import requests
import threading
import time
import re
import math
import uvicorn
from datetime import datetime, timedelta

app = FastAPI(
    title="MCX Silver Smart Allocator",
    description="Finds best silver futures contracts and allocates lots based on volatility",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY   = "ZztbYWQr"
CLIENT_ID = "AACE648379"
PASSWORD  = "2607"
TOTP_KEY  = "YPNWTO32HOA7IZ5KFNSMBZUQCE"

LOT_SIZES = {"SILVER": 30, "SILVERM": 5, "SILVERMIC": 1}

VOLATILITY_THRESHOLDS = {"HIGH": 2.0, "NORMAL": 1.0}

RISK_PCT = {
    "HIGH":   (0.30, 0.40),   # High volatility   → risk only 30-40% of capital
    "NORMAL": (0.40, 0.50),   # Medium volatility  → risk 40-50% of capital
    "LOW":    (0.60, 0.70),   # Low volatility     → risk 60-70% of capital
}

_session        = {}
_poll_active    = False
_poll_thread    = None
_current_token  = None
_current_symbol = None
_price_history  = []
_MAX_TICKS      = 200

# --- Pydantic Models ---
class SubscribeRequest(BaseModel):
    token: str
    symbol: str = "SILVER"

class ContractItem(BaseModel):
    symbol_type: str
    token: str
    trading_symbol: str

class AllocateRequest(BaseModel):
    available_amount: float
    risk_amount: float
    ltp: float
    product_type: str = "CARRYFORWARD"
    contracts: List[ContractItem]

class SmartAllocateRequest(BaseModel):
    available_amount: float
    product_type: str = "CARRYFORWARD"

# --- Session ---
def get_session():
    if _session.get("obj") and _session.get("auth_token"):
        return _session["obj"], _session["auth_token"]
    print("Logging in...")
    obj  = SmartConnect(api_key=API_KEY)
    totp = pyotp.TOTP(TOTP_KEY).now()
    data = obj.generateSession(CLIENT_ID, PASSWORD, totp)
    if not data["status"]:
        raise Exception(data.get("message", "Login failed"))
    _session["obj"]        = obj
    _session["auth_token"] = data["data"]["jwtToken"]
    print("Login OK")
    return _session["obj"], _session["auth_token"]

def parse_expiry_date(it):
    exp = (it.get("expiry") or "").strip()
    for fmt in ["%d%b%Y", "%d%B%Y", "%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y"]:
        try:
            return datetime.strptime(exp, fmt)
        except:
            pass
    ts = (it.get("tradingsymbol") or "").upper()
    m  = re.search(r"(\d{2})([A-Z]{3})(\d{2,4})FUT", ts)
    if m:
        day, mon, yr = m.group(1), m.group(2), m.group(3)
        yr = "20" + yr if len(yr) == 2 else yr
        try:
            return datetime.strptime(f"{day}{mon}{yr}", "%d%b%Y")
        except:
            pass
    return None

def fetch_ltp(token_str):
    try:
        obj, auth_token = get_session()
        try:
            resp = obj.ltpData("MCX", "", token_str)
            if resp and resp.get("status"):
                ltp = float(resp["data"].get("ltp", 0))
                if ltp > 0:
                    return ltp, None
        except Exception as e:
            print(f"ltpData error: {e}")
        url = "https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote/"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json", "Accept": "application/json",
            "X-UserType": "USER", "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00", "X-PrivateKey": API_KEY,
        }
        r = requests.post(url, json={"mode": "LTP", "exchangeTokens": {"MCX": [str(token_str)]}},
                          headers=headers, timeout=8)
        result = r.json()
        print(f"LTP response: {result}")
        if result.get("status"):
            fetched = result.get("data", {}).get("fetched", [])
            if fetched:
                ltp = float(fetched[0].get("ltp", 0))
                if ltp > 0:
                    return ltp, None
            return None, "Market closed or no data"
        msg = result.get("message", "API error")
        if any(x in msg.lower() for x in ["token", "invalid", "unauth", "expired"]):
            _session.clear()
        return None, msg
    except Exception as e:
        _session.clear()
        return None, str(e)

def fetch_full_quote(tokens):
    try:
        obj, auth_token = get_session()
        url = "https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote/"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json", "Accept": "application/json",
            "X-UserType": "USER", "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00", "X-PrivateKey": API_KEY,
        }
        r = requests.post(url, json={"mode": "FULL", "exchangeTokens": {"MCX": tokens}},
                          headers=headers, timeout=10)
        result = r.json()
        print(f"FULL quote: {result}")
        if result.get("status"):
            fetched = result.get("data", {}).get("fetched", [])
            return {str(item["symbolToken"]): item for item in fetched if "symbolToken" in item}
        return {}
    except Exception as e:
        print(f"fetch_full_quote error: {e}")
        return {}

def fetch_candle_atr(token_str, auth_token):
    """
    Fetch last 5 daily candles from AngelOne historical API and compute ATR.
    Used as fallback when intraday OHLC is zero (outside market hours).
    """
    try:
        from datetime import date
        today    = date.today().strftime("%Y-%m-%d")
        from_dt  = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d 09:00")
        to_dt    = datetime.now().strftime("%Y-%m-%d 15:30")
        url      = "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData"
        headers  = {
            "Authorization":    f"Bearer {auth_token}",
            "Content-Type":     "application/json",
            "Accept":           "application/json",
            "X-UserType":       "USER",
            "X-SourceID":       "WEB",
            "X-ClientLocalIP":  "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress":     "00:00:00:00:00:00",
            "X-PrivateKey":     API_KEY,
        }
        payload = {
            "exchange":    "MCX",
            "symboltoken": str(token_str),
            "interval":    "ONE_DAY",
            "fromdate":    from_dt,
            "todate":      to_dt,
        }
        r      = requests.post(url, json=payload, headers=headers, timeout=10)
        result = r.json()
        print(f"Candle data: {result}")
        if result.get("status") and result.get("data"):
            candles = result["data"]  # [ [timestamp, o, h, l, c, vol], ... ]
            if len(candles) >= 2:
                # True Range for each candle: max(H-L, |H-PrevC|, |L-PrevC|)
                trs = []
                for i in range(1, len(candles)):
                    h     = float(candles[i][2])
                    l     = float(candles[i][3])
                    pc    = float(candles[i-1][4])
                    tr    = max(h - l, abs(h - pc), abs(l - pc))
                    trs.append(tr)
                atr   = sum(trs) / len(trs)
                close = float(candles[-1][4])
                if close > 0:
                    return round((atr / close) * 100, 3), float(candles[-1][2]), float(candles[-1][3]), close, float(candles[-1][1])
    except Exception as e:
        print(f"fetch_candle_atr error: {e}")
    return None, 0, 0, 0, 0

def calculate_volatility(token_str):
    try:
        obj, auth_token = get_session()

        # Method 1: Intraday OHLC from FULL quote
        quotes = fetch_full_quote([str(token_str)])
        q      = quotes.get(str(token_str), {})
        high   = float(q.get("high",  0) or 0)
        low    = float(q.get("low",   0) or 0)
        close  = float(q.get("close", 0) or q.get("ltp", 0) or 0)
        open_  = float(q.get("open",  0) or 0)
        atr_pct = ((high - low) / close * 100) if high > 0 and low > 0 and close > 0 else 0.0

        # Method 2: Historical candle ATR (fallback when intraday OHLC is zero)
        candle_atr_pct = 0.0
        if atr_pct == 0.0:
            candle_atr_pct, c_high, c_low, c_close, c_open = fetch_candle_atr(token_str, auth_token)
            if candle_atr_pct:
                # Use candle data for OHLC display too
                if high == 0:   high  = c_high
                if low  == 0:   low   = c_low
                if close == 0:  close = c_close
                if open_ == 0:  open_ = c_open
                atr_pct = candle_atr_pct
                print(f"Using historical candle ATR: {atr_pct:.3f}%")

        # Method 3: Tick volatility from live price history
        tick_vol = 0.0
        if len(_price_history) >= 5:
            prices  = list(_price_history)
            returns = [(prices[i] - prices[i-1]) / prices[i-1] * 100
                       for i in range(1, len(prices)) if prices[i-1] > 0]
            if returns:
                mean     = sum(returns) / len(returns)
                tick_vol = math.sqrt(sum((r - mean) ** 2 for r in returns) / len(returns))

        # Combine: prefer OHLC ATR, else tick vol
        primary = atr_pct if atr_pct > 0 else tick_vol * 3
        level   = ("HIGH" if primary >= VOLATILITY_THRESHOLDS["HIGH"]
                   else "NORMAL" if primary >= VOLATILITY_THRESHOLDS["NORMAL"] else "LOW")

        print(f"Volatility: ATR%={atr_pct:.3f} candle_atr%={candle_atr_pct} tick_vol%={tick_vol:.3f} level={level}")
        return {
            "level":           level,
            "atr_pct":         round(atr_pct, 3),
            "atr_source":      "historical_candles" if candle_atr_pct else "intraday_ohlc",
            "tick_vol":        round(tick_vol, 3),
            "high":            high,
            "low":             low,
            "close":           close,
            "open":            open_,
            "ticks_used":      len(_price_history),
        }
    except Exception as e:
        print(f"calculate_volatility error: {e}")
        return {"level": "NORMAL", "atr_pct": 0, "atr_source": "none", "tick_vol": 0,
                "high": 0, "low": 0, "close": 0, "open": 0, "ticks_used": 0}

def suggest_risk_amount(available_amount, vol_data):
    level   = vol_data.get("level", "NORMAL")
    rng     = RISK_PCT[level]
    pct_mid = (rng[0] + rng[1]) / 2
    return {
        "risk_amount":  round(available_amount * pct_mid, 2),
        "risk_pct_min": rng[0] * 100,
        "risk_pct_max": rng[1] * 100,
        "risk_pct_mid": pct_mid * 100,
        "level":        level,
        "reasoning": {
            "HIGH":   f"Volatility HIGH (ATR={vol_data['atr_pct']:.2f}%) — Using 30-40% risk range (midpoint 35%)",
            "NORMAL": f"Volatility MEDIUM (ATR={vol_data['atr_pct']:.2f}%) — Using 40-50% risk range (midpoint 45%)",
            "LOW":    f"Volatility LOW (ATR={vol_data['atr_pct']:.2f}%) — Using 60-70% risk range (midpoint 65%)",
        }[level],
    }

def pick_best_contract(symbol):
    try:
        obj, _    = get_session()
        all_items = obj.searchScrip("MCX", symbol).get("data", []) or []
        today     = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        futs = []
        for it in all_items:
            s = (it.get("tradingsymbol") or "").upper()
            if not s.endswith("FUT"):
                continue
            if symbol == "SILVERMIC" and s.startswith("SILVERMIC"):
                futs.append(it)
            elif symbol == "SILVERM" and s.startswith("SILVERM") and not s.startswith("SILVERMIC"):
                futs.append(it)
            elif symbol == "SILVER" and s.startswith("SILVER") and not s.startswith("SILVERM"):
                futs.append(it)
        if not futs:
            return None, "No futures contracts found"
        valid = []
        for it in futs:
            exp_dt = parse_expiry_date(it)
            if exp_dt is None:
                continue
            days = (exp_dt - today).days
            if days >= 10:
                it["_expiry_dt"] = exp_dt
                it["_days_to_expiry"] = days
                valid.append(it)
        if not valid:
            return None, f"No contracts with expiry > 10 days for {symbol}"
        valid.sort(key=lambda x: x["_expiry_dt"])
        print(f"{symbol}: {len(valid)} valid contracts")
        candidates = valid[:5]
        tokens     = [str(f["symboltoken"]) for f in candidates if f.get("symboltoken")]
        quotes     = fetch_full_quote(tokens) if tokens else {}
        best, best_vol = None, -1
        for fut in candidates:
            token = str(fut.get("symboltoken", ""))
            q     = quotes.get(token, {})
            vol   = int(q.get("tradeVolume", 0) or q.get("volume", 0) or 0)
            print(f"  {fut.get('tradingsymbol')}: vol={vol} days={fut['_days_to_expiry']}")
            if vol > best_vol:
                best_vol = vol
                best = {
                    "symboltoken":    fut.get("symboltoken"),
                    "tradingsymbol":  fut.get("tradingsymbol"),
                    "expiry":         fut.get("expiry", ""),
                    "days_to_expiry": fut["_days_to_expiry"],
                    "volume":         vol,
                    "ltp":   float(q.get("ltp",  0) or 0),
                    "open":  float(q.get("open", 0) or 0),
                    "high":  float(q.get("high", 0) or 0),
                    "low":   float(q.get("low", 0) or 0),
                    "close": float(q.get("close",0) or 0),
                    "openInterest": int(q.get("openInterest", 0) or 0),
                }
        if best is None or best_vol == 0:
            fut  = valid[0]
            best = {"symboltoken": fut.get("symboltoken"), "tradingsymbol": fut.get("tradingsymbol"),
                    "expiry": fut.get("expiry", ""), "days_to_expiry": fut["_days_to_expiry"],
                    "volume": 0, "ltp": 0, "open": 0, "high": 0, "low": 0, "close": 0, "openInterest": 0}
        print(f"Best {symbol}: {best['tradingsymbol']} vol={best['volume']}")
        return best, None
    except Exception as e:
        print(f"pick_best_contract error: {e}")
        _session.clear()
        return None, str(e)

def fetch_margin(token, trading_symbol, symbol_type, lots, price, product_type):
    try:
        obj, auth_token = get_session()
        total_units = lots * LOT_SIZES.get(symbol_type, 30)
        params = {"positions": [{
            "exchange": "MCX", "qty": str(total_units), "price": str(price),
            "productType": product_type, "token": token, "tradeType": "BUY",
            "symbolName": trading_symbol, "instrumentType": "FUTSTK",
            "strikePrice": "0", "optionType": "XX", "expiryDate": "",
        }]}
        try:
            resp = obj.getMarginApi(params)
            if resp and resp.get("status"):
                d = resp.get("data", {})
                return {k: float(d.get(k, 0)) for k in
                        ["totalMarginRequired", "spanMargin", "exposureMargin", "availableBalance"]}
        except AttributeError:
            pass
        url = "https://apiconnect.angelone.in/rest/secure/angelbroking/margin/v1/batch"
        headers = {
            "Authorization": f"Bearer {auth_token}", "Content-Type": "application/json",
            "Accept": "application/json", "X-UserType": "USER", "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00", "X-PrivateKey": API_KEY,
        }
        r = requests.post(url, json=params, headers=headers, timeout=10)
        result = r.json()
        if result.get("status"):
            d = result.get("data", {})
            return {k: float(d.get(k, 0)) for k in
                    ["totalMarginRequired", "spanMargin", "exposureMargin", "availableBalance"]}
        return None
    except Exception as e:
        print(f"fetch_margin error: {e}")
        return None

def greedy_allocate(budget, ltp, contracts, product_type):
    LABELS = {"SILVER": "Silver Standard", "SILVERM": "Silver Mini", "SILVERMIC": "Silver Micro"}
    cms = []
    for c in contracts:
        stype  = c["symbol_type"]
        margin = fetch_margin(c["token"], c["trading_symbol"], stype, 1, ltp, product_type)
        mpl    = (margin["totalMarginRequired"]
                  if margin and margin["totalMarginRequired"] > 0
                  else LOT_SIZES[stype] * ltp * 0.15)
        if not (margin and margin["totalMarginRequired"] > 0):
            print(f"Estimated margin for {stype}: Rs.{mpl:.2f}")
        cms.append({"symbol_type": stype, "token": c["token"],
                    "trading_symbol": c["trading_symbol"], "lot_size": LOT_SIZES[stype],
                    "margin_per_lot": mpl, "label": LABELS[stype]})
    cms.sort(key=lambda x: x["lot_size"], reverse=True)
    remaining, allocation, total_lots, total_margin, total_kg = budget, [], 0, 0, 0
    for cm in cms:
        if remaining < cm["margin_per_lot"]:
            continue
        lots = int(remaining // cm["margin_per_lot"])
        if lots <= 0:
            continue
        cost = lots * cm["margin_per_lot"]
        kg   = lots * cm["lot_size"]
        allocation.append({
            "symbol_type": cm["symbol_type"], "label": cm["label"],
            "trading_symbol": cm["trading_symbol"], "token": cm["token"],
            "lots": lots, "lot_size": cm["lot_size"],
            "margin_per_lot": round(cm["margin_per_lot"], 2),
            "total_margin": round(cost, 2), "total_kg": kg,
            "exposure_value": round(kg * ltp, 2),
        })
        remaining -= cost; total_lots += lots; total_margin += cost; total_kg += kg
    return {
        "allocation": allocation, "total_lots": total_lots,
        "total_margin": round(total_margin, 2), "total_kg": total_kg,
        "total_exposure": round(total_kg * ltp, 2),
        "remaining_cash": round(remaining, 2),
        "utilization": round((total_margin / budget * 100) if budget > 0 else 0, 1),
    }

def poll_loop():
    global _poll_active, _price_history
    while _poll_active:
        if _current_token:
            ltp, err = fetch_ltp(_current_token)
            if ltp and ltp > 0:
                _price_history.append(ltp)
                if len(_price_history) > _MAX_TICKS:
                    _price_history.pop(0)
                print(f"[poll] {_current_symbol} LTP={ltp}")
            else:
                print(f"[poll] error: {err}")
        time.sleep(3)

# ═══════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════

@app.get("/health")
def health():
    return {"status": True, "message": "MCX Silver API is running"}

@app.get("/api/best-contract")
def best_contract(symbol: str = Query(default="SILVER", description="SILVER | SILVERM | SILVERMIC")):
    symbol = symbol.upper()
    if symbol not in LOT_SIZES:
        raise HTTPException(status_code=400, detail="symbol must be SILVER, SILVERM, or SILVERMIC")
    best, err = pick_best_contract(symbol)
    if best:
        return {"status": True, "symbol": symbol, "data": best}
    raise HTTPException(status_code=500, detail=err or "Could not find contract")

@app.get("/api/ltp")
def get_ltp(token: str = Query(..., description="Instrument token from /api/best-contract")):
    ltp, err = fetch_ltp(token)
    if ltp:
        return {"status": True, "ltp": ltp}
    raise HTTPException(status_code=500, detail=str(err))

@app.get("/api/volatility")
def get_volatility(
    token: str     = Query(..., description="Instrument token"),
    available: float = Query(default=0, description="Available capital in Rs"),
):
    vol_data  = calculate_volatility(token)
    risk_data = suggest_risk_amount(available, vol_data) if available > 0 else {}
    return {"status": True, "volatility": vol_data, "risk": risk_data}

@app.post("/api/subscribe")
def subscribe(body: SubscribeRequest):
    global _poll_thread, _poll_active, _current_token, _current_symbol, _price_history
    if body.token != _current_token:
        _price_history = []
    _current_token  = body.token
    _current_symbol = body.symbol
    if not _poll_active or (_poll_thread and not _poll_thread.is_alive()):
        _poll_active = True
        _poll_thread = threading.Thread(target=poll_loop, daemon=True)
        _poll_thread.start()
    ltp, err = fetch_ltp(body.token)
    if ltp:
        _price_history.append(ltp)
    return {"status": True, "ltp": ltp, "symbol": body.symbol, "message": err}

@app.post("/api/allocate")
def allocate(body: AllocateRequest):
    if body.available_amount <= 0:
        raise HTTPException(status_code=400, detail="available_amount is required")
    if body.risk_amount <= 0:
        raise HTTPException(status_code=400, detail="risk_amount is required")
    if body.ltp <= 0:
        raise HTTPException(status_code=400, detail="ltp must be greater than 0")
    if not body.contracts:
        raise HTTPException(status_code=400, detail="contracts list is required")
    contracts = [{"symbol_type": c.symbol_type, "token": c.token, "trading_symbol": c.trading_symbol}
                 for c in body.contracts]
    budget = min(body.available_amount, body.risk_amount)
    result = greedy_allocate(budget, body.ltp, contracts, body.product_type)
    result.update({"budget": round(budget, 2), "available": round(body.available_amount, 2),
                   "risk": round(body.risk_amount, 2), "ltp": body.ltp})
    return {"status": True, "data": result}

@app.post("/api/smart-allocate")
def smart_allocate(body: SmartAllocateRequest):
    if body.available_amount <= 0:
        raise HTTPException(status_code=400, detail="available_amount is required")

    contracts_found, contracts_list, errors = {}, [], []
    for sym in ["SILVER", "SILVERM", "SILVERMIC"]:
        best, err = pick_best_contract(sym)
        if best:
            contracts_found[sym] = best
            contracts_list.append({"symbol_type": sym, "token": best["symboltoken"],
                                   "trading_symbol": best["tradingsymbol"]})
        else:
            errors.append(f"{sym}: {err}")

    if not contracts_found:
        raise HTTPException(status_code=500, detail={"message": "Could not find any contracts", "errors": errors})

    ltp, ltp_token = 0.0, None
    for sym in ["SILVER", "SILVERM", "SILVERMIC"]:
        if sym in contracts_found:
            token = contracts_found[sym]["symboltoken"]
            fetched_ltp, _ = fetch_ltp(str(token))
            if fetched_ltp and fetched_ltp > 0:
                ltp, ltp_token = fetched_ltp, token
                _price_history.append(ltp)
                if len(_price_history) > _MAX_TICKS:
                    _price_history.pop(0)
                break
            elif contracts_found[sym].get("ltp", 0) > 0:
                ltp, ltp_token = contracts_found[sym]["ltp"], token
                break

    if ltp <= 0:
        raise HTTPException(status_code=500,
                            detail={"message": "Could not fetch live price — market may be closed", "errors": errors})

    vol_data  = calculate_volatility(str(ltp_token)) if ltp_token else \
                {"level": "NORMAL", "atr_pct": 0, "tick_vol": 0,
                 "high": 0, "low": 0, "close": 0, "open": 0, "ticks_used": 0}
    risk_data = suggest_risk_amount(body.available_amount, vol_data)
    budget    = min(body.available_amount, risk_data["risk_amount"])
    alloc     = greedy_allocate(budget, ltp, contracts_list, body.product_type)

    buy_orders = [{
        "action":         "BUY",
        "contract":       item["trading_symbol"],
        "lots":           item["lots"],
        "lot_size_kg":    item["lot_size"],
        "total_kg":       item["total_kg"],
        "ltp":            ltp,
        "margin_per_lot": item["margin_per_lot"],
        "total_margin":   item["total_margin"],
        "exposure_value": item["exposure_value"],
    } for item in alloc["allocation"]]

    return {
        "status": True,
        "summary": {
            "available_capital":   round(body.available_amount, 2),
            "volatility_level":    vol_data["level"],
            "risk_pct_used":       f"{risk_data['risk_pct_mid']}%",
            "risk_amount":         risk_data["risk_amount"],
            "budget_deployed":     round(budget, 2),
            "live_price_Rs":       ltp,
            "total_lots":          alloc["total_lots"],
            "total_silver_kg":     alloc["total_kg"],
            "total_margin_used":   alloc["total_margin"],
            "remaining_cash":      alloc["remaining_cash"],
            "capital_utilization": f"{alloc['utilization']}%",
            "reasoning":           risk_data["reasoning"],
        },
        "buy_orders": buy_orders,
        "errors":     errors,
    }

if __name__ == "__main__":
    print("=" * 57)
    print("  MCX Silver Smart Allocator  ->  http://localhost:5000")
    print("  Interactive Docs            ->  http://localhost:5000/docs")
    print("=" * 57)
    uvicorn.run(app, host="0.0.0.0", port=5000)
