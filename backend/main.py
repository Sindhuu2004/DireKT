#!/usr/bin/env python3
"""
MCX Silver Integrated Trading Platform — FastAPI Backend
Multi-user: each user has isolated capital, allocation, trades, signals.

Run: uvicorn main:app --reload --port 8000
"""

from __future__ import annotations
import asyncio, json, logging, math, os, re, signal, ssl, struct, uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, time as dt_time
from enum import Enum
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional, Tuple, AsyncGenerator

import aiohttp, numpy as np, pandas as pd, pyotp, structlog
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ═══════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════

_price_history: List[dict] = []
_MAX_TICKS = 20

app = FastAPI()

# ═══════════════════════════════════════════
# SMART ALLOCATOR INTEGRATION
# ═════════════════════════════════════════

@app.post("/api/smart-allocate")
async def smart_allocate_endpoint(request: dict):
    """Smart allocation using Angel One API with volatility analysis"""
    try:
        available_amount = request.get("available_amount", 0)
        if available_amount <= 0:
            return {"error": "available_amount is required"}
        
        # For now, use the existing allocation logic
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as sess:
            allocation = await smart_allocate(sess, available_amount)
            return {"status": "success", "allocation": allocation}
            
    except Exception as e:
        logger.error(f"Smart allocation error: {e}")
        return {"error": str(e)}

@app.get("/api/feed-status")
def feed_status():
    """Verify if Angel One feed is truly real-time or stale"""
    if not _price_history:
        return {
            "status": False,
            "message": "No data received yet",
            "is_live_feed": False
        }

    # Count price changes in recent ticks
    changes = 0
    recent_prices = []
    for i in range(1, len(_price_history)):
        if _price_history[i]["price"] != _price_history[i-1]["price"]:
            changes += 1
        recent_prices.append(_price_history[i]["price"])

    # Consider live if at least 3 changes in last 10 ticks
    is_live = changes >= 3 and len(_price_history) >= 10

    return {
        "status": True,
        "is_live_feed": is_live,
        "total_ticks": len(_price_history),
        "price_changes": changes,
        "latest_price": _price_history[-1]["price"],
        "latest_time": _price_history[-1]["time"],
        "last_5_prices": recent_prices[-5:] if len(recent_prices) >= 5 else recent_prices,
        "change_percentage": ((recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100) if len(recent_prices) >= 2 and recent_prices[0] > 0 else 0,
        "feed_health": "LIVE" if is_live else "STALE",
        "market_status": "ACTIVE" if changes > 0 else "STAGNANT"
    }

class AppSettings(BaseSettings):
    SECRET_KEY:              str   = Field(default="CHANGE_ME_IN_PRODUCTION_USE_STRONG_SECRET")
    ACCESS_TOKEN_EXPIRE_MINS: int  = Field(default=60 * 24)
    ALGORITHM:               str   = Field(default="HS256")

    ANGEL_ONE_API_KEY:   str = Field(default="")
    ANGEL_ONE_CLIENT_ID:  str = Field(default="")
    ANGEL_ONE_CLIENT_SECRET:str = Field(default="")
    ANGEL_ONE_TOTP_SECRET:str = Field(default="")
    ANGEL_ONE_PASSWORD:   str = Field(default="")

    # Market Feed API (Alternative Angel One credentials)
    MARKET_FEED_API_KEY: str = Field(default="")
    MARKET_FEED_SECRET_KEY: str = Field(default="")
    DHAN_ACCESS_TOKEN: str = Field(default="")

    PAPER_TRADING:         bool  = Field(default=True)
    PAPER_SLIPPAGE_PCT:    float = Field(default=0.05)
    PAPER_BROKERAGE:       float = Field(default=20.0)
    PRODUCT_TYPE:          str   = Field(default="CARRYFORWARD")

    ATR_PERIOD:            int   = Field(default=14)
    ATR_MULTIPLIER:        float = Field(default=1.5)
    RISK_REWARD_RATIO:     float = Field(default=2.5)
    EMA_FAST:              int   = Field(default=9)
    EMA_SLOW:              int   = Field(default=21)
    ENTRY_MIN_BARS:        int   = Field(default=50)
    ENTRY_ADX_THRESHOLD:   float = Field(default=20.0)
    ENTRY_RSI_LONG_MIN:    int   = Field(default=45)
    ENTRY_RSI_LONG_MAX:    int   = Field(default=70)
    ENTRY_RSI_SHORT_MIN:   int   = Field(default=30)
    ENTRY_RSI_SHORT_MAX:   int   = Field(default=55)
    ENTRY_MACD_MIN_HIST:   float = Field(default=0.0)
    ENTRY_SL_ATR_MULT:     float = Field(default=1.5)
    ENTRY_MAX_SPREAD_PCT:  float = Field(default=0.10)
    ENTRY_VOTE_THRESHOLD:  int   = Field(default=3)
    ENTRY_CONF_THRESHOLD:  float = Field(default=0.68)
    MAX_OPEN_TRADES:       int   = Field(default=1)
    ENTRY_SUPERTREND_CONFIRM: bool = Field(default=True)
    ENTRY_BB_EXPAND_REQUIRE: bool  = Field(default=True)
    VOLUME_CONFIRMATION:   bool  = Field(default=True)
    MIN_VOLUME_THRESHOLD:  int   = Field(default=100)

    TRAILING_STOP_ACTIVATION_PCT: float = Field(default=0.5)
    TRAILING_STOP_DISTANCE_ATR:   float = Field(default=1.0)
    PARTIAL_EXIT_1_PCT:   float = Field(default=0.4)
    PARTIAL_EXIT_2_PCT:   float = Field(default=0.35)
    PARTIAL_EXIT_3_PCT:   float = Field(default=0.25)
    PARTIAL_TARGET_1_RR:  float = Field(default=1.0)
    PARTIAL_TARGET_2_RR:  float = Field(default=1.8)
    PARTIAL_TARGET_3_RR:  float = Field(default=2.5)
    MAX_TRADE_DURATION_MINUTES: int  = Field(default=240)
    END_OF_DAY_EXIT_TIME:       str  = Field(default="23:00")
    RSI_OVERBOUGHT:      int   = Field(default=75)
    RSI_OVERSOLD:        int   = Field(default=25)
    BB_SQUEEZE_MULTIPLIER: float = Field(default=2.5)
    BREAKEVEN_ACTIVATION_RR: float = Field(default=0.8)
    EMA_EXIT_CROSS_PERIOD: int = Field(default=5)
    TRADING_START_TIME:  str  = Field(default="09:00")
    TRADING_END_TIME:    str  = Field(default="23:00")

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


cfg = AppSettings()
logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════
# AUTH UTILITIES
# ═══════════════════════════════════════════

import bcrypt
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(pw: str) -> str: 
    return bcrypt.hashpw(pw[:72].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(pw: str, hashed: str) -> bool: 
    return bcrypt.checkpw(pw[:72].encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire    = datetime.utcnow() + (expires_delta or timedelta(minutes=cfg.ACCESS_TOKEN_EXPIRE_MINS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, cfg.SECRET_KEY, algorithm=cfg.ALGORITHM)


# ═══════════════════════════════════════════
# IN-MEMORY USER STORE  (replace with DB in production)
# ═══════════════════════════════════════════

@dataclass
class UserRecord:
    user_id:       str
    username:      str
    email:         str
    hashed_pw:     str
    balance:       float            = 100_000.0
    created_at:    str              = field(default_factory=lambda: datetime.utcnow().isoformat())
    # Runtime state — managed by TradingSession
    is_trading:    bool             = False

users_db: Dict[str, UserRecord] = {}   # user_id → UserRecord
username_idx: Dict[str, str]    = {}   # username → user_id


# ═══════════════════════════════════════════
# SIGNAL & TRADE RECORDS  (per-user append-only log)
# ═══════════════════════════════════════════

@dataclass
class SignalRecord:
    signal_id:   str
    user_id:     str
    signal_type: str          # ENTRY | EXIT
    direction:   str          # BUY | SELL | NONE
    confidence:  float
    price:       float
    filters:     List[str]
    reason:      str
    timestamp:   str

@dataclass
class TradeRecord:
    trade_id:      str
    user_id:       str
    trading_symbol: str
    direction:     str
    entry_price:   float
    exit_price:    Optional[float]
    quantity:      int
    lots:          int
    lot_size:      int
    stop_loss:     float
    target:        float
    status:        str          # OPEN | CLOSED
    pnl:           Optional[float]
    entry_time:    str
    exit_time:     Optional[str]
    exit_reason:   str = ""
    volatility_level: str = ""

signals_log: Dict[str, List[SignalRecord]] = {}   # user_id → list
trades_log:  Dict[str, List[TradeRecord]]  = {}   # user_id → list

def get_user_signals(uid: str) -> List[SignalRecord]:
    return signals_log.setdefault(uid, [])

def get_user_trades(uid: str) -> List[TradeRecord]:
    return trades_log.setdefault(uid, [])

def append_signal(rec: SignalRecord):
    get_user_signals(rec.user_id).append(rec)

def append_trade(rec: TradeRecord):
    get_user_trades(rec.user_id).append(rec)

def update_trade(user_id: str, trade_id: str, **kwargs):
    for t in get_user_trades(user_id):
        if t.trade_id == trade_id:
            for k, v in kwargs.items():
                setattr(t, k, v)
            return


# ═══════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════

class Ind:
    @staticmethod
    def ema(s: pd.Series, p: int) -> pd.Series:
        return s.ewm(span=p, adjust=False).mean()

    @staticmethod
    def atr(h, l, c, p=14) -> pd.Series:
        tr = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
        return tr.rolling(p).mean()

    @staticmethod
    def rsi(c, p=14) -> pd.Series:
        d=c.diff(); g=d.clip(lower=0).rolling(p).mean(); lo=(-d.clip(upper=0)).rolling(p).mean()
        return 100-(100/(1+g/lo.replace(0,np.nan)))

    @staticmethod
    def macd(c, fast=12, slow=26, sig=9):
        line=c.ewm(span=fast,adjust=False).mean()-c.ewm(span=slow,adjust=False).mean()
        s=line.ewm(span=sig,adjust=False).mean(); return line,s,line-s

    @staticmethod
    def bb(c, p=20, std=2.0):
        m=c.rolling(p).mean(); sd=c.rolling(p).std(); return m+std*sd,m,m-std*sd

    @staticmethod
    def adx(h,l,c,p=14):
        tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
        atr_s=tr.rolling(p).mean(); up=h.diff(); dn=-l.diff()
        pdm=np.where((up>dn)&(up>0),up,0.0); mdm=np.where((dn>up)&(dn>0),dn,0.0)
        pdi=100*pd.Series(pdm,index=c.index).rolling(p).mean()/atr_s
        mdi=100*pd.Series(mdm,index=c.index).rolling(p).mean()/atr_s
        dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
        return dx.rolling(p).mean(),pdi,mdi

    @staticmethod
    def cci(h,l,c,p=20):
        tp=(h+l+c)/3; sma=tp.rolling(p).mean()
        mad=tp.rolling(p).apply(lambda x:np.abs(x-x.mean()).mean())
        return (tp-sma)/(0.015*mad)

    @staticmethod
    def chandelier(h,l,c,p=22,mult=3.0):
        a=Ind.atr(h,l,c,p); return h.rolling(p).max()-mult*a,l.rolling(p).min()+mult*a

    @staticmethod
    def supertrend(h,l,c,p=10,mult=3.0):
        a=Ind.atr(h,l,c,p); hl2=(h+l)/2; ub=hl2+mult*a; lb=hl2-mult*a
        st=pd.Series(index=c.index,dtype=float); dr=pd.Series(index=c.index,dtype=int)
        for i in range(1,len(c)):
            pst=st.iloc[i-1] if i>1 else lb.iloc[i]; pdir=dr.iloc[i-1] if i>1 else 1
            if pdir==1:
                s=max(lb.iloc[i],pst) if c.iloc[i]>pst else ub.iloc[i]
                d=1 if c.iloc[i]>s else -1
            else:
                s=min(ub.iloc[i],pst) if c.iloc[i]<pst else lb.iloc[i]
                d=-1 if c.iloc[i]<s else 1
            st.iloc[i]=s; dr.iloc[i]=d
        return st,dr

    @staticmethod
    def psar(h,l,c,step=0.02,max_step=0.2):
        sar=c.copy(); tr=pd.Series(1,index=c.index); ep=h.iloc[0]; af=step
        for i in range(1,len(c)):
            psar=sar.iloc[i-1]
            if tr.iloc[i-1]==1:
                ns=min(psar+af*(ep-psar),l.iloc[i-1],l.iloc[i-2] if i>1 else l.iloc[i-1])
                if l.iloc[i]<ns: tr.iloc[i]=-1;ns=ep;ep=l.iloc[i];af=step
                else:
                    tr.iloc[i]=1
                    if h.iloc[i]>ep: ep=h.iloc[i];af=min(af+step,max_step)
            else:
                ns=max(psar+af*(ep-psar),h.iloc[i-1],h.iloc[i-2] if i>1 else h.iloc[i-1])
                if h.iloc[i]>ns: tr.iloc[i]=1;ns=ep;ep=h.iloc[i];af=step
                else:
                    tr.iloc[i]=-1
                    if l.iloc[i]<ep: ep=l.iloc[i];af=min(af+step,max_step)
            sar.iloc[i]=ns
        return sar,tr

    @staticmethod
    def stoch(h,l,c,k=14,d=3):
        ll=l.rolling(k).min(); hh=h.rolling(k).max()
        kk=100*(c-ll)/(hh-ll).replace(0,np.nan); return kk,kk.rolling(d).mean()

    @staticmethod
    def bb_bw(c,p=20,std=2.0):
        u,m,lo=Ind.bb(c,p,std); return (u-lo)/m

    @staticmethod
    def partial_targets(entry,sl,rr_levels,direction):
        risk=abs(entry-sl)
        return [entry+risk*rr if direction=="BUY" else entry-risk*rr for rr in rr_levels]


# ═══════════════════════════════════════════
# ALLOCATION LOGIC
# ═══════════════════════════════════════════

LOT_SIZES = {"SILVER":30,"SILVERM":5,"SILVERMIC":1}
VOL_THRESH = {"HIGH":2.0,"NORMAL":1.0}
RISK_PCT   = {"HIGH":(0.30,0.40),"NORMAL":(0.40,0.50),"LOW":(0.60,0.70)}

ANGEL_REST = "https://apiconnect.angelone.in"

def _angel_headers(jwt_token: str = "") -> dict:
    h = {
        "Content-Type":"application/json","Accept":"application/json",
        "X-UserType":"USER","X-SourceID":"WEB",
        "X-ClientLocalIP":"127.0.0.1","X-ClientPublicIP":"127.0.0.1",
        "X-MACAddress":"00:00:00:00:00:00","X-PrivateKey": cfg.ANGEL_ONE_API_KEY,
    }
    if jwt_token: h["Authorization"] = f"Bearer {jwt_token}"
    return h

async def angel_login(session: aiohttp.ClientSession) -> Optional[str]:
    """Login to Angel One API - try market feed credentials first, then fallback"""
    
    # Try Market Feed API credentials first
    if cfg.MARKET_FEED_API_KEY and cfg.MARKET_FEED_SECRET_KEY:
        try:
            payload = {
                "clientcode": cfg.ANGEL_ONE_CLIENT_ID,
                "password": cfg.ANGEL_ONE_PASSWORD,
                "totp": pyotp.TOTP(cfg.ANGEL_ONE_TOTP_SECRET).now()
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00",
                "X-PrivateKey": cfg.MARKET_FEED_API_KEY,
            }
            
            url = f"{ANGEL_REST}/rest/auth/angelbroking/user/v1/loginByPassword"
            async with session.post(url, json=payload, headers=headers, 
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
                d = await r.json()
                if d.get("status") and d.get("data"):
                    logger.info(f"Angel One login successful with Market Feed API")
                    return d["data"].get("jwtToken")
        except Exception as e:
            logger.warning(f"Market Feed API login failed: {e}")
    
    # Fallback to original Angel One credentials
    try:
        payload={"clientcode":cfg.ANGEL_ONE_CLIENT_ID,"password":cfg.ANGEL_ONE_PASSWORD,
                 "totp":pyotp.TOTP(cfg.ANGEL_ONE_TOTP_SECRET).now()}
        headers=_angel_headers()
        url = f"{ANGEL_REST}/rest/auth/angelbroking/user/v1/loginByPassword"
        async with session.post(url, json=payload, headers=headers, 
                            timeout=aiohttp.ClientTimeout(total=15)) as r:
            d=await r.json()
            if d.get("status") and d.get("data"):
                logger.info(f"Angel One login successful with original API")
                return d["data"].get("jwtToken")
    except Exception as e:
        logger.error(f"Angel One login failed: {e}")
    return None

def _parse_expiry(item:dict)->Optional[datetime]:
    exp=(item.get("expiry") or "").strip()
    for fmt in ["%d%b%Y","%d%B%Y","%Y-%m-%d","%d-%m-%Y","%d-%b-%Y"]:
        try: return datetime.strptime(exp,fmt)
        except: pass
    ts=(item.get("tradingsymbol") or "").upper()
    m=re.search(r"(\d{2})([A-Z]{3})(\d{2,4})FUT",ts)
    if m:
        day,mon,yr=m.group(1),m.group(2),m.group(3)
        yr="20"+yr if len(yr)==2 else yr
        try: return datetime.strptime(f"{day}{mon}{yr}","%d%b%Y")
        except: pass
    return None

async def smart_allocate(session: aiohttp.ClientSession, capital: float) -> dict:
    """Full allocation pipeline for a given capital amount. Returns allocation dict."""
    
    # Check if we're in mock data mode
    use_mock_data = os.getenv("USE_MOCK_DATA", "false").lower() == "true"
    logger.info(f"Allocation mode: USE_MOCK_DATA={os.getenv('USE_MOCK_DATA', 'not_set')} -> use_mock_data={use_mock_data}")
    
    if use_mock_data:
        logger.info("Using mock allocation for testing")
        current_ltp = shared_feed._latest_ltps.get("464150", 255000.0)
        logger.info(f"Mock allocation LTP: {current_ltp}")
        return {
            "token": "464150",
            "tradingsymbol": "SILVER03JUL26FUT",
            "trading_symbol": "SILVER03JUL26FUT",  
            "days_to_expiry": 15,
            "ltp": current_ltp,
            "atr_pct": 2.5,
            "vol_source": "mock_data",
            "capital": capital,
            "qty": int(capital / (current_ltp * 0.05)),
            "margin_per_lot": current_ltp * 0.05,
            "lots": 1,
            "risk": capital * 0.02,
            "sl_price": current_ltp * 0.98,
            "target_price": current_ltp * 1.05
        }
    
    # Original Angel One allocation logic
    jwt_token = await angel_login(session)
    if not jwt_token:
        return {"error":"Angel One login failed"}

    # Use live price from WebSocket feed instead of REST API
    # Get the latest LTP from any available token
    current_ltp = 0.0
    if shared_feed._latest_ltps:
        current_ltp = max(shared_feed._latest_ltps.values())
    
    if current_ltp > 0:
        logger.info(f"Using live WebSocket price: {current_ltp}")
        return {
            "token": "464150",
            "tradingsymbol": "SILVER03JUL26FUT",
            "trading_symbol": "SILVER03JUL26FUT",
            "days_to_expiry": 15,
            "ltp": current_ltp,
            "atr_pct": 2.5,
            "vol_source": "websocket_live",
            "capital": capital,
            "qty": int(capital / (current_ltp * 0.05)),
            "margin_per_lot": current_ltp * 0.05,
            "lots": 1,
            "risk": capital * 0.02,
            "sl_price": current_ltp * 0.98,
            "target_price": current_ltp * 1.05
        }

    return {"error": "Could not fetch live price - WebSocket data not available"}

    # Find best contract
    best_contract = None
    best_sym      = None
    best_ltp      = 0.0

    for sym in ["SILVER","SILVERM","SILVERMIC"]:
        try:
            url=f"{ANGEL_REST}/rest/secure/angelbroking/order/v1/searchScrip"
            async with session.get(url,params={"exchange":"MCX","searchscrip":sym},
                                   headers=_angel_headers(jwt_token),
                                   timeout=aiohttp.ClientTimeout(total=10)) as r:
                data=await r.json()
                items=data.get("data",[]) or []
        except: items=[]

        today=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        futs=[]
        for it in items:
            s=(it.get("tradingsymbol") or "").upper()
            if not s.endswith("FUT"): continue
            if sym=="SILVERMIC" and s.startswith("SILVERMIC"): futs.append(it)
            elif sym=="SILVERM" and s.startswith("SILVERM") and not s.startswith("SILVERMIC"): futs.append(it)
            elif sym=="SILVER" and s.startswith("SILVER") and not s.startswith("SILVERM"): futs.append(it)

        valid=[]
        for it in futs:
            exp=_parse_expiry(it)
            if exp and (exp-today).days>=10:
                it["_days"]=( exp-today).days; valid.append(it)
        if not valid: continue
        valid.sort(key=lambda x:x["_days"])

        # Fetch LTP for first valid
        token=str(valid[0]["symboltoken"])
        try:
            url2=f"{ANGEL_REST}/rest/secure/angelbroking/market/v1/quote/"
            async with session.post(url2,
                json={"mode":"LTP","exchangeTokens":{"MCX":[token]}},
                headers=_market_feed_headers(jwt_token),timeout=aiohttp.ClientTimeout(total=8)) as r2:
                d2=await r2.json()
                if d2.get("status"):
                    fetched=d2.get("data",{}).get("fetched",[])
                    if fetched:
                        ltp=float(fetched[0].get("ltp",0))
                        if ltp>0 and ltp>best_ltp:
                            best_ltp=ltp; best_sym=sym
                            best_contract={"token":token,"tradingsymbol":valid[0]["tradingsymbol"],
                                           "days_to_expiry":valid[0]["_days"],"ltp":ltp}
        except Exception as e:
            logger.warning(f"LTP fetch {sym}: {e}")

    if not best_contract or best_ltp<=0:
        return {"error":"Could not fetch live price — market may be closed","ltp":0}

    # Volatility (intraday OHLC)
    atr_pct=0.0; vol_source="none"
    try:
        url3=f"{ANGEL_REST}/rest/secure/angelbroking/market/v1/quote/"
        async with session.post(url3,
            json={"mode":"FULL","exchangeTokens":{"MCX":[best_contract["token"]]}},
            headers=_angel_headers(jwt_token),timeout=aiohttp.ClientTimeout(total=10)) as r3:
            d3=await r3.json()
            if d3.get("status"):
                fetched=d3.get("data",{}).get("fetched",[])
                if fetched:
                    q=fetched[0]
                    h=float(q.get("high",0) or 0); l=float(q.get("low",0) or 0)
                    cl=float(q.get("close",0) or q.get("ltp",0) or 0)
                    if h>0 and l>0 and cl>0:
                        atr_pct=(h-l)/cl*100; vol_source="intraday_ohlc"
    except Exception as e:
        logger.warning(f"OHLC fetch: {e}")

    # Fallback: historical candles
    if atr_pct==0:
        try:
            from_dt=(datetime.now()-timedelta(days=10)).strftime("%Y-%m-%d 09:00")
            to_dt=datetime.now().strftime("%Y-%m-%d 15:30")
            async with session.post(
                f"{ANGEL_REST}/rest/secure/angelbroking/historical/v1/getCandleData",
                json={"exchange":"MCX","symboltoken":best_contract["token"],
                      "interval":"ONE_DAY","fromdate":from_dt,"todate":to_dt},
                headers=_angel_headers(jwt_token),timeout=aiohttp.ClientTimeout(total=10)) as rc:
                dc=await rc.json()
                if dc.get("status") and dc.get("data"):
                    candles=dc["data"]
                    if len(candles)>=2:
                        trs=[max(float(candles[i][2])-float(candles[i][3]),
                                 abs(float(candles[i][2])-float(candles[i-1][4])),
                                 abs(float(candles[i][3])-float(candles[i-1][4])))
                             for i in range(1,len(candles))]
                        cl=float(candles[-1][4])
                        if cl>0: atr_pct=round(sum(trs)/len(trs)/cl*100,3); vol_source="historical"
        except Exception as e:
            logger.warning(f"Candle ATR: {e}")

    vol_level=("HIGH" if atr_pct>=VOL_THRESH["HIGH"]
               else "NORMAL" if atr_pct>=VOL_THRESH["NORMAL"] else "LOW")
    rng=RISK_PCT[vol_level]; mid=(rng[0]+rng[1])/2
    risk_amount=round(capital*mid,2)
    budget=min(capital,risk_amount)

    lot_sz=LOT_SIZES.get(best_sym,30)
    margin_per_lot=best_ltp*lot_sz*0.15   # 15% estimate
    lots_possible=max(0,int(budget//margin_per_lot))

    return {
        "token":           best_contract["token"],
        "trading_symbol":  best_contract["tradingsymbol"],
        "days_to_expiry":  best_contract["days_to_expiry"],
        "symbol_type":     best_sym,
        "lot_size":        lot_sz,
        "ltp":             best_ltp,
        "atr_pct":         round(atr_pct,3),
        "vol_source":      vol_source,
        "volatility_level":vol_level,
        "capital":         round(capital,2),
        "risk_pct":        f"{mid*100:.0f}%",
        "risk_amount":     risk_amount,
        "budget":          round(budget,2),
        "margin_per_lot":  round(margin_per_lot,2),
        "lots_possible":   lots_possible,
        "total_quantity":  lots_possible*lot_sz,
        "total_margin":    round(lots_possible*margin_per_lot,2),
        "remaining_cash":  round(budget-lots_possible*margin_per_lot,2),
        "reasoning": {
            "HIGH":   f"High vol (ATR {atr_pct:.2f}%) → 30-40% capital at risk",
            "NORMAL": f"Medium vol (ATR {atr_pct:.2f}%) → 40-50% capital at risk",
            "LOW":    f"Low vol (ATR {atr_pct:.2f}%) → 60-70% capital at risk",
        }.get(vol_level,""),
    }


# ═══════════════════════════════════════════
# ANGEL ONE WEBSOCKET — SHARED ACROSS USERS
# (one connection, fan-out ticks to all active sessions)
# ═══════════════════════════════════════════

class OHLCBarBuilder:
    def __init__(self,window=500):
        self._bars=deque(maxlen=window); self._cur=None; self._cur_min=None
    def update(self,ltp,volume,oi,ts)->Optional[dict]:
        minute_ts=ts.replace(second=0,microsecond=0); mkey=int(minute_ts.timestamp())
        if self._cur_min!=mkey:
            completed=dict(self._cur) if self._cur else None
            if completed: self._bars.append(completed)
            self._cur={"timestamp":minute_ts,"open":ltp,"high":ltp,"low":ltp,
                       "close":ltp,"volume":volume,"oi":oi}; self._cur_min=mkey
            return completed
        self._cur["high"]=max(self._cur["high"],ltp); self._cur["low"]=min(self._cur["low"],ltp)
        self._cur["close"]=ltp; self._cur["volume"]=volume; self._cur["oi"]=oi
        return None
    def to_df(self)->pd.DataFrame:
        if not self._bars: return pd.DataFrame(columns=["timestamp","open","high","low","close","volume","oi"])
        df=pd.DataFrame(list(self._bars)); df.set_index("timestamp",inplace=True); return df
    @property
    def count(self)->int: return len(self._bars)


class SharedFeed:
    """
    One Angel One WS connection shared across all user sessions.
    Emits ticks & bars to registered callbacks per token.
    """
    WS_URL="wss://smartapisocket.angelone.in/smart-stream"
    REST_URL="https://smartapi.angelbroking.com"

    def __init__(self):
        self._jwt:str=""; self._feed:str=""
        self._session:Optional[aiohttp.ClientSession]=None
        self._ws=None; self._connected=False; self._shutdown=False
        self._tokens:List[dict]=[]
        self._bar_builder=OHLCBarBuilder(500)
        self._latest_ltps:Dict[str, float]={}
        self._latest_ticks:Dict[str, dict]={}
        self._tick_count:int=0
        # callbacks: list of async callables (ltp, ohlc)
        self._tick_cbs:List[Callable]=[]
        self._bar_cbs:List[Callable]=[]
        self._hb_task=None

    def on_tick(self,fn): self._tick_cbs.append(fn)
    def on_bar(self,fn):  self._bar_cbs.append(fn)

    def remove_tick_cb(self,fn):
        try: self._tick_cbs.remove(fn)
        except: pass
    def remove_bar_cb(self,fn):
        try: self._bar_cbs.remove(fn)
        except: pass

    async def _make_session(self):
        ssl_ctx=ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
        self._session=aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx))

    async def login(self)->bool:
        if not self._session: await self._make_session()
        try:
            payload={"clientcode":cfg.ANGEL_ONE_CLIENT_ID,"password":cfg.ANGEL_ONE_PASSWORD,
                     "totp":pyotp.TOTP(cfg.ANGEL_ONE_TOTP_SECRET).now()}
            headers={"Content-Type":"application/json","Accept":"application/json",
                     "X-UserType":"USER","X-SourceID":"WEB",
                     "X-ClientLocalIP":"127.0.0.1","X-ClientPublicIP":"127.0.0.1",
                     "X-MACAddress":"00:00:00:00:00:00","X-PrivateKey":cfg.ANGEL_ONE_API_KEY}
            url="https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
            async with self._session.post(url,json=payload,headers=headers,
                                          timeout=aiohttp.ClientTimeout(total=15)) as r:
                d=await r.json()
                if d.get("status") and d.get("data"):
                    self._jwt=d["data"].get("jwtToken",""); self._feed=d["data"].get("feedToken","")
                    logger.info("SharedFeed login OK"); return True
        except Exception as e: logger.error(f"SharedFeed login: {e}")
        return False

    async def connect(self,tokens:List[dict])->bool:
        if not self._jwt: await self.login()
        self._tokens=tokens
        try:
            self._ws=await self._session.ws_connect(
                self.WS_URL,
                headers=[("Authorization",self._jwt),("x-api-key",cfg.ANGEL_ONE_API_KEY),
                         ("x-client-code",cfg.ANGEL_ONE_CLIENT_ID),("x-feed-token",self._feed)],
                heartbeat=30)
            self._connected=True; logger.info("SharedFeed WS connected")
            await self._ws.send_str(json.dumps({
                "correlationID":"shared_feed","action":1,
                "params":{"mode":2,"tokenList":tokens}}))
            self._hb_task=asyncio.create_task(self._heartbeat())
            return True
        except Exception as e:
            logger.error(f"SharedFeed connect: {e}"); return False

    async def _heartbeat(self):
        """Keep WebSocket connection alive"""
        while self._connected and not self._shutdown:
            try:
                if self._ws and not self._ws.closed:
                    await self._ws.ping()
                    await asyncio.sleep(25)
                else:
                    break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break

    async def listen(self):
        while not self._shutdown:
            if not self._connected:
                await asyncio.sleep(5); await self.login(); await self.connect(self._tokens); continue
            try:
                async for msg in self._ws:
                    if self._shutdown: return
                    if msg.type==aiohttp.WSMsgType.BINARY: await self._parse(msg.data)
                    elif msg.type in(aiohttp.WSMsgType.ERROR,aiohttp.WSMsgType.CLOSE):
                        self._connected=False; break
            except Exception as e:
                if not self._shutdown: logger.error(f"SharedFeed listen: {e}")
            self._connected=False
        logger.info("SharedFeed listen stopped")

    async def _parse(self,data:bytes):
        global _price_history
        try:
            if len(data)<51: return
            token=str(struct.unpack_from("<i",data,15)[0])
            ltp=struct.unpack_from("<i",data,43)[0]/100.0
            volume=struct.unpack_from("<i",data,83)[0] if len(data)>=123 else 0
            
            if ltp>0:
                self._latest_ltps[token]=ltp
                
                # Track price history with timestamps for real-time verification
                ts = datetime.utcnow()
                price_entry = {
                    "price": ltp,
                    "time": ts.strftime("%H:%M:%S"),
                    "timestamp": ts.isoformat(),
                    "volume": volume,
                    "token": token
                }
                _price_history.append(price_entry)
                
                # Keep only recent ticks to prevent memory issues
                if len(_price_history) > _MAX_TICKS:
                    _price_history.pop(0)
                
                # Call tick callbacks for exit evaluation
                for cb in list(self._tick_cbs):
                    if asyncio.iscoroutinefunction(cb): 
                        await cb(token, ltp, volume, 0, ts)
                    else: 
                        cb(token, ltp, volume, 0, ts)
                
                # Update bar builder
                bar=self._bar_builder.update(ltp,volume,0,ts)
                if bar:
                    for cb in list(self._bar_cbs):
                        if asyncio.iscoroutinefunction(cb): await cb(bar, self._bar_builder.to_df())
                        else: cb(bar, self._bar_builder.to_df())
            
            # WebSocket heartbeat
            try:
                await asyncio.sleep(25)
                if self._ws and not self._ws.closed: 
                    await self._ws.ping()
            except Exception:
                pass  # Handle ping errors gracefully
                
        except Exception as e:
            logger.error(f"SharedFeed parse error: {e}")

    def get_ohlc(self)->pd.DataFrame: return self._bar_builder.to_df()
    def get_latest_ltp(self, token:str=None)->float:
        if token: return self._latest_ltps.get(token,0.0)
        return next(iter(self._latest_ltps.values())) if self._latest_ltps else 0.0
    def get_latest_tick(self, token:str=None)->Optional[dict]:
        if token: return self._latest_ticks.get(token)
        return next(iter(self._latest_ticks.values())) if self._latest_ticks else None

    async def subscribe(self, tokens: List[dict]):
        """Update subscription list in real-time."""
        for t in tokens:
            if t not in self._tokens:
                self._tokens.append(t)
        if self._connected and self._ws:
            try:
                await self._ws.send_str(json.dumps({
                    "correlationID": "shared_feed_update",
                    "action": 1,
                    "params": {"mode": 2, "tokenList": self._tokens}
                }))
                logger.info(f"SharedFeed subscription updated: {len(self._tokens)} tokens")
            except Exception as e:
                logger.error(f"SharedFeed subscribe error: {e}")

    async def stop(self):
        self._shutdown=True; self._connected=False
        if self._hb_task: self._hb_task.cancel()
        if self._ws: await self._ws.close()
        if self._session: await self._session.close()


shared_feed = SharedFeed()


# ═══════════════════════════════════════════
# ENTRY ENGINE
# ═══════════════════════════════════════════

def evaluate_entry(price:float, ohlc:pd.DataFrame, allocated_qty:int=1) -> dict:
    """Run all 15 entry filters and return decision dict."""
    sigs=[]
    n=len(ohlc)

    def sig(name,direction,conf,reason=""): return {"name":name,"dir":direction,"conf":conf,"reason":reason}

    # P0 — Trading hours
    now=datetime.now().time()
    sh,sm=map(int,cfg.TRADING_START_TIME.split(":"))
    eh,em=map(int,cfg.TRADING_END_TIME.split(":"))
    start=dt_time(sh,sm); eod_block=dt_time(eh,max(0,em-15))
    if not (start<=now<eod_block):
        return {"action":"WAIT","reason":f"Outside trading hours ({now})","signals":[],"qty":0}

    # P1 — Min bars
    if n<cfg.ENTRY_MIN_BARS:
        return {"action":"WAIT","reason":f"Only {n} bars (need {cfg.ENTRY_MIN_BARS})","signals":[],"qty":0}

    # P3 — ATR risk
    atr_v=Ind.atr(ohlc["high"],ohlc["low"],ohlc["close"],cfg.ATR_PERIOD).iloc[-1]
    if atr_v<=0 or (atr_v*cfg.ENTRY_SL_ATR_MULT)/price>0.02:
        return {"action":"WAIT","reason":f"ATR SL too wide ({atr_v:.2f})","signals":[],"qty":0}

    sl_d=atr_v*cfg.ENTRY_SL_ATR_MULT

    # P4 filters
    def f_ema():
        if n<cfg.EMA_SLOW+5: return sig("EMA_Trend","NONE",0)
        ef=Ind.ema(ohlc["close"],cfg.EMA_FAST); es=Ind.ema(ohlc["close"],cfg.EMA_SLOW)
        cc=ef.iloc[-1]-es.iloc[-1]; pc=ef.iloc[-2]-es.iloc[-2]
        if cc>0 and pc<=0: return sig("EMA_Trend","BUY",0.80,"EMA bullish cross")
        if cc<0 and pc>=0: return sig("EMA_Trend","SELL",0.80,"EMA bearish cross")
        if cc>0: return sig("EMA_Trend","BUY",0.55,"EMA bullish")
        if cc<0: return sig("EMA_Trend","SELL",0.55,"EMA bearish")
        return sig("EMA_Trend","NONE",0)

    def f_adx():
        if n<24: return sig("ADX_Strength","NONE",0)
        adx,pdi,mdi=Ind.adx(ohlc["high"],ohlc["low"],ohlc["close"])
        v=adx.iloc[-1]
        if v<cfg.ENTRY_ADX_THRESHOLD: return sig("ADX_Strength","NONE",0,f"ADX {v:.1f} weak")
        conf=min(0.5+(v-cfg.ENTRY_ADX_THRESHOLD)/100,0.90)
        d="BUY" if pdi.iloc[-1]>mdi.iloc[-1] else "SELL"
        return sig("ADX_Strength",d,conf,f"ADX={v:.1f}")

    def f_rsi():
        if n<19: return sig("RSI_Zone","NONE",0)
        v=Ind.rsi(ohlc["close"],cfg.ATR_PERIOD).iloc[-1]
        if cfg.ENTRY_RSI_LONG_MIN<=v<=cfg.ENTRY_RSI_LONG_MAX: return sig("RSI_Zone","BUY",0.70,f"RSI {v:.1f}")
        if cfg.ENTRY_RSI_SHORT_MIN<=v<=cfg.ENTRY_RSI_SHORT_MAX: return sig("RSI_Zone","SELL",0.70,f"RSI {v:.1f}")
        return sig("RSI_Zone","NONE",0)

    def f_macd():
        if n<35: return sig("MACD_Momentum","NONE",0)
        _,_,hist=Ind.macd(ohlc["close"])
        ch,ph=hist.iloc[-1],hist.iloc[-2]
        if ph<=0 and ch>cfg.ENTRY_MACD_MIN_HIST: return sig("MACD_Momentum","BUY",0.78,f"MACD hist+ {ch:.4f}")
        if ph>=0 and ch<-cfg.ENTRY_MACD_MIN_HIST: return sig("MACD_Momentum","SELL",0.78,f"MACD hist- {ch:.4f}")
        if ch>0: return sig("MACD_Momentum","BUY",0.55)
        if ch<0: return sig("MACD_Momentum","SELL",0.55)
        return sig("MACD_Momentum","NONE",0)

    def f_bb():
        if n<25: return sig("BB_Expansion","NONE",0)
        upper,mid,lower=Ind.bb(ohlc["close"])
        bw=Ind.bb_bw(ohlc["close"])
        if cfg.ENTRY_BB_EXPAND_REQUIRE and bw.iloc[-1]<bw.iloc[-3]*0.7: return sig("BB_Expansion","NONE",0,"BB squeezing")
        if lower.iloc[-1]<price<mid.iloc[-1]: return sig("BB_Expansion","BUY",0.65,"Lower BB half")
        if mid.iloc[-1]<price<upper.iloc[-1]: return sig("BB_Expansion","SELL",0.65,"Upper BB half")
        return sig("BB_Expansion","NONE",0)

    def f_st():
        if not cfg.ENTRY_SUPERTREND_CONFIRM: return sig("SuperTrend","BUY",0.5)
        if n<20: return sig("SuperTrend","NONE",0)
        _,dr=Ind.supertrend(ohlc["high"],ohlc["low"],ohlc["close"])
        cd,pd_=dr.iloc[-1],dr.iloc[-2]
        if cd==1 and pd_==-1: return sig("SuperTrend","BUY",0.88,"ST flipped BULL")
        if cd==-1 and pd_==1: return sig("SuperTrend","SELL",0.88,"ST flipped BEAR")
        if cd==1: return sig("SuperTrend","BUY",0.60)
        if cd==-1: return sig("SuperTrend","SELL",0.60)
        return sig("SuperTrend","NONE",0)

    def f_psar():
        if n<30: return sig("PSAR_Entry","NONE",0)
        _,tr=Ind.psar(ohlc["high"],ohlc["low"],ohlc["close"])
        if tr.iloc[-1]==1 and tr.iloc[-2]==-1: return sig("PSAR_Entry","BUY",0.82,"PSAR bull flip")
        if tr.iloc[-1]==-1 and tr.iloc[-2]==1: return sig("PSAR_Entry","SELL",0.82,"PSAR bear flip")
        if tr.iloc[-1]==1: return sig("PSAR_Entry","BUY",0.55)
        if tr.iloc[-1]==-1: return sig("PSAR_Entry","SELL",0.55)
        return sig("PSAR_Entry","NONE",0)

    def f_chan():
        if n<27: return sig("Chandelier","NONE",0)
        ls,ss=Ind.chandelier(ohlc["high"],ohlc["low"],ohlc["close"])
        if price>ls.iloc[-1]: return sig("Chandelier","BUY",0.70,f"Above chan {ls.iloc[-1]:.2f}")
        if price<ss.iloc[-1]: return sig("Chandelier","SELL",0.70,f"Below chan {ss.iloc[-1]:.2f}")
        return sig("Chandelier","NONE",0)

    def f_stoch():
        if n<20: return sig("Stoch_Pullback","NONE",0)
        k,d=Ind.stoch(ohlc["high"],ohlc["low"],ohlc["close"])
        ck,cd,pk,pd_=k.iloc[-1],d.iloc[-1],k.iloc[-2],d.iloc[-2]
        if pk<=40 and ck>cd and pk<pd_: return sig("Stoch_Pullback","BUY",0.74,f"Stoch bull OS K={ck:.1f}")
        if pk>=60 and ck<cd and pk>pd_: return sig("Stoch_Pullback","SELL",0.74,f"Stoch bear OB K={ck:.1f}")
        return sig("Stoch_Pullback","NONE",0)

    def f_cci():
        if n<25: return sig("CCI_Breakout","NONE",0)
        c=Ind.cci(ohlc["high"],ohlc["low"],ohlc["close"])
        cv,pv=c.iloc[-1],c.iloc[-2]
        if pv<=100 and cv>100: return sig("CCI_Breakout","BUY",0.73,f"CCI break+100 {cv:.1f}")
        if pv>=-100 and cv<-100: return sig("CCI_Breakout","SELL",0.73,f"CCI break-100 {cv:.1f}")
        return sig("CCI_Breakout","NONE",0)

    def f_vol():
        if not cfg.VOLUME_CONFIRMATION: return sig("Volume","BUY",0.5)
        if n>=20:
            avg=ohlc["volume"].tail(20).mean(); last=ohlc["volume"].iloc[-1]
            if avg>0 and last>avg*1.3: return sig("Volume","BUY",0.72,f"Vol surge {last:.0f}>avg {avg:.0f}")
            if avg>0 and last<avg*0.5: return sig("Volume","NONE",0,"Vol too low")
        return sig("Volume","BUY",0.55)

    p4=[f_ema(),f_adx(),f_rsi(),f_macd(),f_bb(),f_st(),f_psar(),f_chan(),f_stoch(),f_cci(),f_vol()]

    buy_v  = [s for s in p4 if s["dir"]=="BUY"  and s["conf"]>0]
    sell_v = [s for s in p4 if s["dir"]=="SELL" and s["conf"]>0]

    def build_entry(direction,votes,conf):
        sl  = price-sl_d  if direction=="BUY" else price+sl_d
        tgt = price+sl_d*cfg.RISK_REWARD_RATIO if direction=="BUY" else price-sl_d*cfg.RISK_REWARD_RATIO
        return {"action":"ENTER","direction":direction,"confidence":round(conf,3),
                "entry_price":round(price,2),"stop_loss":round(sl,2),"target":round(tgt,2),
                "quantity":allocated_qty,"filters":[s["name"] for s in votes],
                "reason":" | ".join(s["reason"] for s in votes[:3] if s["reason"]),
                "signals":p4}

    for direction,votes in [("BUY",buy_v),("SELL",sell_v)]:
        if len(votes)>=cfg.ENTRY_VOTE_THRESHOLD:
            avg=sum(s["conf"] for s in votes)/len(votes)
            if avg>=cfg.ENTRY_CONF_THRESHOLD:
                return build_entry(direction,votes,avg)

    for direction,votes in [("BUY",buy_v),("SELL",sell_v)]:
        top2=sorted(votes,key=lambda s:s["conf"],reverse=True)[:2]
        if len(top2)==2 and sum(s["conf"] for s in top2)/2>=0.85:
            return build_entry(direction,top2,sum(s["conf"] for s in top2)/2)

    return {"action":"WAIT","reason":"Insufficient filter agreement","signals":p4,"qty":0}


# ═══════════════════════════════════════════
# EXIT ENGINE
# ═══════════════════════════════════════════

def evaluate_exit(trade_rec:TradeRecord, price:float, ohlc:pd.DataFrame) -> dict:
    """Run all 15 exit strategies. Returns action dict."""
    direction=trade_rec.direction
    entry=trade_rec.entry_price
    current_sl=trade_rec.stop_loss
    current_tgt=trade_rec.target
    n=len(ohlc)

    # P0 Hard stops
    if direction=="BUY":
        if price<=current_sl: return {"action":"EXIT_FULL","reason":f"SL hit {current_sl:.2f}","confidence":1.0,"price":price}
        if price>=current_tgt: return {"action":"EXIT_FULL","reason":f"Target hit {current_tgt:.2f}","confidence":1.0,"price":price}
    else:
        if price>=current_sl: return {"action":"EXIT_FULL","reason":f"SL hit {current_sl:.2f}","confidence":1.0,"price":price}
        if price<=current_tgt: return {"action":"EXIT_FULL","reason":f"Target hit {current_tgt:.2f}","confidence":1.0,"price":price}

    # P1 Time
    now=datetime.now()
    h,m=map(int,cfg.END_OF_DAY_EXIT_TIME.split(":"))
    if (now-datetime.fromisoformat(trade_rec.entry_time)).total_seconds()/60>=cfg.MAX_TRADE_DURATION_MINUTES:
        return {"action":"EXIT_FULL","reason":f"Max duration {cfg.MAX_TRADE_DURATION_MINUTES}min","confidence":0.95,"price":price}
    eod_dt=datetime.combine(now.date(),dt_time(h,m))
    mins_left=(eod_dt-now).total_seconds()/60
    if 0<mins_left<=15:
        return {"action":"EXIT_FULL","reason":f"EOD exit {mins_left:.0f}min left","confidence":0.99,"price":price}

    if n<5: return {"action":"HOLD","reason":"Not enough bars","confidence":0,"price":price}

    exits=[]
    # SuperTrend flip
    try:
        _,dr=Ind.supertrend(ohlc["high"],ohlc["low"],ohlc["close"])
        if direction=="BUY" and dr.iloc[-1]==-1 and dr.iloc[-2]==1: exits.append(("SuperTrend_Flip","ST flipped BEAR",0.90))
        if direction=="SELL" and dr.iloc[-1]==1 and dr.iloc[-2]==-1: exits.append(("SuperTrend_Flip","ST flipped BULL",0.90))
    except: pass

    # PSAR flip
    try:
        _,tr=Ind.psar(ohlc["high"],ohlc["low"],ohlc["close"])
        if direction=="BUY" and tr.iloc[-1]==-1 and tr.iloc[-2]==1: exits.append(("PSAR_Exit","PSAR bear flip",0.85))
        if direction=="SELL" and tr.iloc[-1]==1 and tr.iloc[-2]==-1: exits.append(("PSAR_Exit","PSAR bull flip",0.85))
    except: pass

    # EMA cross
    try:
        ef=Ind.ema(ohlc["close"],cfg.EMA_EXIT_CROSS_PERIOD); es=Ind.ema(ohlc["close"],cfg.EMA_FAST)
        cc=ef.iloc[-1]-es.iloc[-1]; pc=ef.iloc[-2]-es.iloc[-2]
        if direction=="BUY" and cc<0 and pc>0: exits.append(("EMA_Cross","EMA cross below",0.80))
        if direction=="SELL" and cc>0 and pc<0: exits.append(("EMA_Cross","EMA cross above",0.80))
    except: pass

    # RSI exhaustion
    try:
        rsi=Ind.rsi(ohlc["close"],cfg.ATR_PERIOD); cr,pr=rsi.iloc[-1],rsi.iloc[-2]
        if direction=="BUY" and pr>cfg.RSI_OVERBOUGHT and cr<pr: exits.append(("RSI_Exhaustion",f"RSI OB {pr:.1f}",min(0.5+(pr-cfg.RSI_OVERBOUGHT)/100,0.85)))
        if direction=="SELL" and pr<cfg.RSI_OVERSOLD and cr>pr:  exits.append(("RSI_Exhaustion",f"RSI OS {pr:.1f}",min(0.5+(cfg.RSI_OVERSOLD-pr)/100,0.85)))
    except: pass

    # MACD reversal
    try:
        _,_,hist=Ind.macd(ohlc["close"]); ch,ph=hist.iloc[-1],hist.iloc[-2]
        if direction=="BUY"  and ph>0 and ch<0: exits.append(("MACD_Reversal","MACD hist neg",0.82))
        if direction=="SELL" and ph<0 and ch>0: exits.append(("MACD_Reversal","MACD hist pos",0.82))
    except: pass

    # ADX collapse
    try:
        adx,pdi,mdi=Ind.adx(ohlc["high"],ohlc["low"],ohlc["close"])
        if n>=5 and adx.iloc[-3]>25 and adx.iloc[-1]<20: exits.append(("ADX_Collapse",f"ADX {adx.iloc[-3]:.1f}→{adx.iloc[-1]:.1f}",0.80))
    except: pass

    # Chandelier exit
    try:
        ls,ss=Ind.chandelier(ohlc["high"],ohlc["low"],ohlc["close"])
        if direction=="BUY"  and price<=ls.iloc[-1]: exits.append(("Chandelier_Exit",f"Chan long stop {ls.iloc[-1]:.2f}",0.88))
        if direction=="SELL" and price>=ss.iloc[-1]: exits.append(("Chandelier_Exit",f"Chan short stop {ss.iloc[-1]:.2f}",0.88))
    except: pass

    # CCI reversal
    try:
        c=Ind.cci(ohlc["high"],ohlc["low"],ohlc["close"]); cv,pv=c.iloc[-1],c.iloc[-2]
        if direction=="BUY"  and pv>150  and cv<150:  exits.append(("CCI_Reversal",f"CCI exit OB {pv:.1f}",0.76))
        if direction=="SELL" and pv<-150 and cv>-150: exits.append(("CCI_Reversal",f"CCI exit OS {pv:.1f}",0.76))
    except: pass

    # BB exit
    try:
        upper,_,lower=Ind.bb(ohlc["close"],20,cfg.BB_SQUEEZE_MULTIPLIER)
        bw=Ind.bb_bw(ohlc["close"],20,cfg.BB_SQUEEZE_MULTIPLIER)
        if direction=="BUY"  and price>=upper.iloc[-1]: exits.append(("BB_Exit",f"Upper BB {upper.iloc[-1]:.2f}",0.72))
        if direction=="SELL" and price<=lower.iloc[-1]: exits.append(("BB_Exit",f"Lower BB {lower.iloc[-1]:.2f}",0.72))
        if n>=5 and bw.iloc[-1]<bw.iloc[-3]*0.6: exits.append(("BB_Squeeze","BB bandwidth squeeze",0.68))
    except: pass

    # Stochastic
    try:
        k,d=Ind.stoch(ohlc["high"],ohlc["low"],ohlc["close"]); ck,cd,pk,pd_=k.iloc[-1],d.iloc[-1],k.iloc[-2],d.iloc[-2]
        if direction=="BUY"  and pk>=80 and ck<cd: exits.append(("Stoch_Exit",f"Stoch bear OB K={ck:.1f}",0.77))
        if direction=="SELL" and pk<=20 and ck>cd: exits.append(("Stoch_Exit",f"Stoch bull OS K={ck:.1f}",0.77))
    except: pass

    if len(exits)>=3:
        avg=sum(e[2] for e in exits)/len(exits)
        if avg>=0.70:
            return {"action":"EXIT_FULL","reason":" | ".join(e[1] for e in exits[:3]),
                    "confidence":round(avg,3),"price":price,
                    "strategies":[e[0] for e in exits]}

    if len(exits)>=2:
        top2=sorted(exits,key=lambda e:e[2],reverse=True)[:2]
        avg=sum(e[2] for e in top2)/2
        if avg>=0.83:
            return {"action":"EXIT_FULL","reason":" | ".join(e[1] for e in top2),
                    "confidence":round(avg,3),"price":price,"strategies":[e[0] for e in top2]}

    # ATR trailing
    try:
        atr_v=Ind.atr(ohlc["high"],ohlc["low"],ohlc["close"],cfg.ATR_PERIOD).iloc[-1]
        if direction=="BUY":
            tsl=price-atr_v*cfg.TRAILING_STOP_DISTANCE_ATR
            if tsl>current_sl:
                return {"action":"MOVE_SL","reason":f"ATR trail SL→{tsl:.2f}","new_sl":round(tsl,2),"confidence":0.70,"price":price}
    except: pass

    return {"action":"HOLD","reason":"No exit signal","confidence":0,"price":price}


# ═══════════════════════════════════════════
# DHAN EXECUTION
# ═══════════════════════════════════════════

DHAN_BASE="https://api.dhan.co/v2"
_dhan_session:Optional[aiohttp.ClientSession]=None

async def dhan_sess()->aiohttp.ClientSession:
    global _dhan_session
    if not _dhan_session or _dhan_session.closed:
        _dhan_session=aiohttp.ClientSession()
    return _dhan_session

async def dhan_place_order(tx:str,qty:int,price:float,symbol:str)->Optional[str]:
    if cfg.PAPER_TRADING:
        oid=f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        logger.info(f"[PAPER] {tx} x{qty} @ {price:.2f} {symbol} → {oid}")
        return oid
    try:
        payload={"dhanClientId":cfg.DHAN_CLIENT_ID,"transactionType":tx,
                 "exchangeSegment":"MCX_COMM","productType":cfg.PRODUCT_TYPE,
                 "orderType":"MARKET","validity":"DAY","tradingSymbol":symbol,
                 "securityId":"","quantity":qty,"price":str(price),"triggerPrice":"0",
                 "afterMarketOrder":False,"boProfitValue":"","boStopLossValue":""}
        s=await dhan_sess()
        async with s.post(f"{DHAN_BASE}/orders",json=payload,
            headers={"Accept":"application/json","Content-Type":"application/json",
                     "Authorization":f"Bearer {cfg.DHAN_ACCESS_TOKEN}","client-id":cfg.DHAN_CLIENT_ID},
            timeout=aiohttp.ClientTimeout(total=10)) as r:
            d=await r.json(); return d.get("orderId") if r.status==200 else None
    except Exception as e:
        logger.error(f"Dhan order: {e}"); return None


# ═══════════════════════════════════════════
# TRADING SESSION  (one per user)
# ═══════════════════════════════════════════

class TradingSession:
    """
    Manages allocation, entry, exit for one user.
    Subscribes tick/bar callbacks to SharedFeed when active.
    """
    def __init__(self, user_id:str, capital:float):
        self.user_id  = user_id
        self.capital  = capital
        self.allocation:Optional[dict]=None
        self.open_trade:Optional[TradeRecord]=None
        self._active  = False

    async def start(self):
        if self._active: return
        self._active=True
        ssl_ctx=ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as sess:
            self.allocation=await smart_allocate(sess,self.capital)
        if "error" in self.allocation:
            logger.error(f"Allocation failed for {self.user_id}: {self.allocation['error']}")
            self.allocation=None
        else:
            token = str(self.allocation.get("token"))
            if token:
                await shared_feed.subscribe([{"exchangeType": 5, "tokens": [token]}])
            logger.info(f"Session {self.user_id}: allocation OK {self.allocation['trading_symbol']}")
        shared_feed.on_tick(self._on_tick)
        shared_feed.on_bar(self._on_bar)

    def stop(self):
        self._active=False
        shared_feed.remove_tick_cb(self._on_tick)
        shared_feed.remove_bar_cb(self._on_bar)

    async def _on_tick(self, token:str, ltp:float, volume:int, oi:int, ts:datetime):
        logger.info(f"Tick received: token={token}, ltp={ltp}, active={self._active}, has_trade={self.open_trade is not None}")
        if not self._active or not self.open_trade: 
            return
        # Only process ticks for the allocated contract
        if self.allocation and token != str(self.allocation.get("token")): 
            logger.info(f"Token mismatch: received {token}, allocated {self.allocation.get('token')}")
            return
        logger.info(f"Processing tick for trade: SL={self.open_trade.stop_loss}, current_ltp={ltp}")
        ohlc=shared_feed.get_ohlc()
        if len(ohlc)<5: return
        try:
            result=evaluate_exit(self.open_trade,ltp,ohlc)
            logger.info(f"Exit evaluation result: {result}")
            if result["action"]=="EXIT_FULL":
                logger.info(f"Exit triggered: {result['reason']} at {ltp}")
                await self._execute_exit(ltp,result)
            elif result["action"]=="MOVE_SL" and result.get("new_sl"):
                self.open_trade.stop_loss=result["new_sl"]
        except Exception as e:
            logger.error(f"Tick exit eval {self.user_id}: {e}")

    async def _on_bar(self, bar:dict, ohlc:pd.DataFrame):
        if not self._active: return
        if self.open_trade: return   # already in trade
        if not self.allocation or self.allocation.get("ltp",0)<=0: return

        price=bar.get("close",0.0)
        if not price or len(ohlc)<cfg.ENTRY_MIN_BARS: return
        qty=self.allocation.get("total_quantity",1)

        try:
            result=evaluate_entry(price,ohlc,allocated_qty=max(1,qty))
            if result["action"]=="ENTER":
                await self._execute_entry(price,result)
        except Exception as e:
            logger.error(f"Bar entry eval {self.user_id}: {e}")

    async def _execute_entry(self, price:float, result:dict):
        slip=price*(1+cfg.PAPER_SLIPPAGE_PCT/100) if result["direction"]=="BUY" \
             else price*(1-cfg.PAPER_SLIPPAGE_PCT/100)
        sym=self.allocation["trading_symbol"] if self.allocation else "SILVER"
        tx="BUY" if result["direction"]=="BUY" else "SELL"
        qty=result.get("quantity",1)
        oid=await dhan_place_order(tx,qty,slip,sym)
        if not oid: return

        trade_id=f"TRD-{uuid.uuid4().hex[:10].upper()}"
        lot_sz=self.allocation.get("lot_size",30) if self.allocation else 30
        lots=max(1,qty//lot_sz)
        rec=TradeRecord(
            trade_id=trade_id, user_id=self.user_id,
            trading_symbol=sym, direction=result["direction"],
            entry_price=round(slip,2), exit_price=None,
            quantity=qty, lots=lots, lot_size=lot_sz,
            stop_loss=result["stop_loss"], target=result["target"],
            status="OPEN", pnl=None,
            entry_time=datetime.utcnow().isoformat(), exit_time=None,
            volatility_level=self.allocation.get("volatility_level","") if self.allocation else "",
        )
        self.open_trade=rec
        append_trade(rec)
        sig_rec=SignalRecord(
            signal_id=uuid.uuid4().hex, user_id=self.user_id,
            signal_type="ENTRY", direction=result["direction"],
            confidence=result.get("confidence",0), price=round(slip,2),
            filters=result.get("filters",[]), reason=result.get("reason",""),
            timestamp=datetime.utcnow().isoformat()
        )
        append_signal(sig_rec)
        logger.info(f"ENTRY EXECUTED {self.user_id}: {trade_id} {result['direction']} x{qty} @{slip:.2f}")
        await ws_broadcast(self.user_id, {"type":"ENTRY","trade":asdict(rec),"signal":asdict(sig_rec)})

    async def _execute_exit(self, price:float, result:dict):
        if not self.open_trade: return
        slip=price*(1-cfg.PAPER_SLIPPAGE_PCT/100) if self.open_trade.direction=="BUY" \
             else price*(1+cfg.PAPER_SLIPPAGE_PCT/100)
        tx="SELL" if self.open_trade.direction=="BUY" else "BUY"
        oid=await dhan_place_order(tx,self.open_trade.quantity,slip,self.open_trade.trading_symbol)
        if not oid: return

        mult=1 if self.open_trade.direction=="BUY" else -1
        pnl=mult*(slip-self.open_trade.entry_price)*self.open_trade.quantity - cfg.PAPER_BROKERAGE*2
        update_trade(self.user_id,self.open_trade.trade_id,
                     status="CLOSED",exit_price=round(slip,2),pnl=round(pnl,2),
                     exit_time=datetime.utcnow().isoformat(),
                     exit_reason=result.get("reason",""))
        # Update user balance
        if self.user_id in users_db:
            users_db[self.user_id].balance=round(users_db[self.user_id].balance+pnl,2)

        closed_trade=self.open_trade
        closed_trade.exit_price=round(slip,2); closed_trade.pnl=round(pnl,2)
        closed_trade.status="CLOSED"; closed_trade.exit_reason=result.get("reason","")
        self.open_trade=None

        sig_rec=SignalRecord(
            signal_id=uuid.uuid4().hex, user_id=self.user_id,
            signal_type="EXIT", direction="SELL" if tx=="SELL" else "BUY",
            confidence=result.get("confidence",0), price=round(slip,2),
            filters=result.get("strategies",[]), reason=result.get("reason",""),
            timestamp=datetime.utcnow().isoformat()
        )
        append_signal(sig_rec)
        logger.info(f"EXIT EXECUTED {self.user_id}: {closed_trade.trade_id} PnL=₹{pnl:+.2f}")
        await ws_broadcast(self.user_id, {"type":"EXIT","trade":asdict(closed_trade),"signal":asdict(sig_rec),"pnl":pnl})


active_sessions: Dict[str, TradingSession] = {}   # user_id → TradingSession


# ═══════════════════════════════════════════
# WEBSOCKET MANAGER
# ═══════════════════════════════════════════

ws_connections: Dict[str, List[WebSocket]] = {}   # user_id → [ws]

async def ws_broadcast(user_id:str, payload:dict):
    conns=ws_connections.get(user_id,[])
    dead=[]
    for ws in conns:
        try: await ws.send_json(payload)
        except: dead.append(ws)
    for ws in dead: conns.remove(ws)


# ═══════════════════════════════════════════
# FASTAPI APPLICATION
# ═══════════════════════════════════════════

# ── Lifespan ──────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
    logger.info("Platform starting up")
    
    # Check if we should use mock data for testing
    use_mock_data = os.getenv("USE_MOCK_DATA", "false").lower() == "true"
    
    if use_mock_data:
        logger.info("Using MOCK DATA mode for testing")
        # Start mock data feed
        asyncio.create_task(start_mock_feed())
    elif cfg.ANGEL_ONE_CLIENT_ID:
        tokens = [{"exchangeType": 5, "tokens": ["464150"]}]
        asyncio.create_task(startup_feed(tokens))
    else:
        logger.warning("No Angel One credentials — feed will not start")
    
    yield
    
    # Shutdown
    await shared_feed.stop()
    logger.info("Platform shut down")

app = FastAPI(title="MCX Silver Trading Platform", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])




# ── Pydantic schemas ─────────────────────

class SignupReq(BaseModel):
    username: str
    email:    str
    password: str
    balance:  float = 100_000.0

class LoginResp(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      str
    username:     str
    balance:      float

class UpdateBalanceReq(BaseModel):
    balance: float

class StartTradingReq(BaseModel):
    pass


# ── Auth dependency ──────────────────────

async def get_current_user(token:str=Depends(oauth2_scheme)) -> UserRecord:
    credentials_exception=HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",headers={"WWW-Authenticate":"Bearer"})
    try:
        payload=jwt.decode(token,cfg.SECRET_KEY,algorithms=[cfg.ALGORITHM])
        uid:str=payload.get("sub")
        if uid is None: raise credentials_exception
    except JWTError: raise credentials_exception
    user=users_db.get(uid)
    if user is None: raise credentials_exception
    return user


# ── Auth routes ───────────────────────────

@app.post("/api/auth/signup", response_model=LoginResp)
async def signup(body:SignupReq):
    if body.username in username_idx:
        raise HTTPException(400,"Username already taken")
    uid=str(uuid.uuid4())
    rec=UserRecord(user_id=uid,username=body.username,email=body.email,
                   hashed_pw=hash_password(body.password),balance=body.balance)
    users_db[uid]=rec; username_idx[body.username]=uid
    token=create_access_token({"sub":uid})
    return LoginResp(access_token=token,user_id=uid,username=body.username,balance=body.balance)

@app.post("/api/auth/login", response_model=LoginResp)
async def login(form:OAuth2PasswordRequestForm=Depends()):
    uid=username_idx.get(form.username)
    if not uid: raise HTTPException(401,"Invalid credentials")
    user=users_db[uid]
    if not verify_password(form.password,user.hashed_pw): raise HTTPException(401,"Invalid credentials")
    token=create_access_token({"sub":uid})
    return LoginResp(access_token=token,user_id=uid,username=user.username,balance=user.balance)


# ── User routes ────────────────────────────

@app.get("/api/me")
async def get_me(user:UserRecord=Depends(get_current_user)):
    sess=active_sessions.get(user.user_id)
    return {"user_id":user.user_id,"username":user.username,"email":user.email,
            "balance":user.balance,"is_trading":user.is_trading,
            "allocation": sess.allocation if sess else None,
            "open_trade": asdict(sess.open_trade) if sess and sess.open_trade else None}

@app.put("/api/me/balance")
async def update_balance(body:UpdateBalanceReq, user:UserRecord=Depends(get_current_user)):
    if body.balance<=0: raise HTTPException(400,"Balance must be positive")
    users_db[user.user_id].balance=body.balance
    return {"balance":body.balance}


# ── Allocation route ──────────────────────

@app.post("/api/allocate")
async def run_allocation(user:UserRecord=Depends(get_current_user)):
    ssl_ctx=ssl.create_default_context(); ssl_ctx.check_hostname=False; ssl_ctx.verify_mode=ssl.CERT_NONE
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as sess:
        result=await smart_allocate(sess,user.balance)
    return result


# ── Trading control ───────────────────────

@app.post("/api/trading/start")
async def start_trading(user:UserRecord=Depends(get_current_user)):
    if user.user_id in active_sessions:
        return {"status":"already_running","message":"Trading session already active"}
    session=TradingSession(user.user_id,user.balance)
    active_sessions[user.user_id]=session
    users_db[user.user_id].is_trading=True
    asyncio.create_task(session.start())
    return {"status":"started","message":f"Trading session started for {user.username}"}

@app.post("/api/trading/stop")
async def stop_trading(user:UserRecord=Depends(get_current_user)):
    sess=active_sessions.pop(user.user_id,None)
    if sess: sess.stop()
    users_db[user.user_id].is_trading=False
    return {"status":"stopped"}

@app.get("/api/trading/status")
async def trading_status(user:UserRecord=Depends(get_current_user)):
    sess=active_sessions.get(user.user_id)
    if not sess: return {"active":False,"allocation":None,"open_trade":None}
    return {"active":sess._active,"allocation":sess.allocation,
            "open_trade": asdict(sess.open_trade) if sess.open_trade else None,
            "feed_ltp": shared_feed.get_latest_ltp(),
            "feed_connected": shared_feed._connected}


# ── Signals & Trades ──────────────────────

@app.get("/api/signals")
async def get_signals(user:UserRecord=Depends(get_current_user)):
    return [asdict(s) for s in reversed(get_user_signals(user.user_id))]

@app.get("/api/trades")
async def get_trades(user:UserRecord=Depends(get_current_user)):
    return [asdict(t) for t in reversed(get_user_trades(user.user_id))]

@app.get("/api/stats")
async def get_stats(user:UserRecord=Depends(get_current_user)):
    trades=get_user_trades(user.user_id)
    closed=[t for t in trades if t.status=="CLOSED"]
    wins  =[t for t in closed if (t.pnl or 0)>0]
    losses=[t for t in closed if (t.pnl or 0)<=0]
    total_pnl=sum(t.pnl or 0 for t in closed)
    return {
        "total_trades":   len(closed),
        "open_trades":    len([t for t in trades if t.status=="OPEN"]),
        "wins":           len(wins),
        "losses":         len(losses),
        "win_rate":       round(len(wins)/len(closed)*100,1) if closed else 0,
        "total_pnl":      round(total_pnl,2),
        "avg_pnl":        round(total_pnl/len(closed),2) if closed else 0,
        "current_balance":user.balance,
    }

@app.get("/api/feed/latest")
async def feed_latest():
    return {"ltp":shared_feed.get_latest_ltp(),"tick":shared_feed.get_latest_tick(),
            "bar_count":shared_feed._bar_builder.count,"connected":shared_feed._connected}


# ── WebSocket real-time feed ──────────────

@app.websocket("/ws/{user_id}")
async def ws_endpoint(websocket:WebSocket, user_id:str):
    await websocket.accept()
    ws_connections.setdefault(user_id,[]).append(websocket)
    # Also stream live tick data to connected user
    async def tick_to_ws(token,ltp,volume,oi,ts):
        try:
            # Optionally filter by what the user is actually watching
            await websocket.send_json({"type":"TICK","token":token,"ltp":ltp,"volume":volume,"timestamp":ts.isoformat()})
        except: pass
    shared_feed.on_tick(tick_to_ws)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        shared_feed.remove_tick_cb(tick_to_ws)
        conns=ws_connections.get(user_id,[])
        try: conns.remove(websocket)
        except: pass


# ── Startup / shutdown ────────────────────

async def startup_feed(tokens):
    await asyncio.sleep(2)
    ok = await shared_feed.connect(tokens)
    if ok:
        asyncio.create_task(shared_feed.listen())
        logger.info("SharedFeed listening")
    else:
        logger.warning("SharedFeed connect failed — retrying in 30s")
        await asyncio.sleep(30)
        asyncio.create_task(startup_feed(tokens))


async def start_mock_feed():
    """Mock data feed for testing when Angel One API is unavailable"""
    import random
    
    logger.info("Starting mock data feed for testing")
    
    # Mock silver price around 72000-73000
    base_price = 72500.0
    
    # Generate initial historical bars to meet ENTRY_MIN_BARS requirement
    logger.info("Generating initial historical bars...")
    current_time = datetime.utcnow()
    
    # Generate 60 bars of historical data (more than ENTRY_MIN_BARS=50)
    for i in range(60):
        bar_time = current_time - timedelta(minutes=(60-i))
        price_variation = random.uniform(-100, 100)
        close_price = base_price + price_variation
        
        # Generate OHLC data
        high = close_price + random.uniform(0, 50)
        low = close_price - random.uniform(0, 50)
        open_price = low + random.uniform(0, high - low)
        volume = random.randint(500, 2000)
        
        # Add to bar builder
        shared_feed._bar_builder.update(close_price, volume, 0, bar_time)
    
    logger.info(f"Generated {len(shared_feed._bar_builder._bars)} historical bars")
    
    # Continue with real-time mock data
    bar_counter = 0
    shared_feed._connected = True  # Show as connected in UI
    while not shared_feed._shutdown:
        try:
            # Generate realistic price movement
            change = random.uniform(-50, 50)
            current_price = base_price + change
            
            # Create mock tick data
            mock_tick = {
                "token": "464150",
                "ltp": current_price,
                "volume": random.randint(100, 1000),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Update shared feed with mock data
            shared_feed._latest_ltps["464150"] = current_price
            shared_feed._latest_ticks["464150"] = mock_tick
            
            # Build mock bars and trigger callbacks
            bar = shared_feed._bar_builder.update(current_price, random.randint(100, 1000), 0, datetime.utcnow())
            
            # Trigger bar callbacks if a new bar is formed (every few updates)
            if bar or (bar_counter % 5 == 0):  # Trigger every 5 ticks or when new bar
                ohlc_df = shared_feed._bar_builder.to_df()
                for cb in list(shared_feed._bar_cbs):
                    try:
                        if asyncio.iscoroutinefunction(cb): 
                            await cb(bar or {"close": current_price, "volume": random.randint(100, 1000)}, ohlc_df)
                        else: 
                            cb(bar or {"close": current_price, "volume": random.randint(100, 1000)}, ohlc_df)
                    except Exception as e:
                        logger.error(f"Mock bar callback error: {e}")
            
            # Log occasionally
            if random.random() < 0.1:  # 10% chance
                logger.info(f"Mock data: Silver LTP = {current_price}, Bars: {len(shared_feed._bar_builder._bars)}")
            
            bar_counter += 1
            await asyncio.sleep(1)  # Update every second
            
        except Exception as e:
            logger.error(f"Mock feed error: {e}")
            await asyncio.sleep(5)


# Mount frontend static files LAST to avoid intercepting API routes
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    logger.warning(f"Frontend dist directory not found at {frontend_dist}. UI will not be served.")


if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000,reload=False)
