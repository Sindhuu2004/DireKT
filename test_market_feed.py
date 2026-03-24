#!/usr/bin/env python3
"""
Test new Angel One Market Feed API credentials
"""

import asyncio
import aiohttp
import pyotp
import json
import ssl
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# New Market Feed API credentials
MARKET_FEED_API_KEY = os.getenv("MARKET_FEED_API_KEY", "")
MARKET_FEED_SECRET_KEY = os.getenv("MARKET_FEED_SECRET_KEY", "")
ANGEL_CLIENT_ID = os.getenv("ANGEL_ONE_CLIENT_ID", "")
ANGEL_PASSWORD = os.getenv("ANGEL_ONE_PASSWORD", "")
ANGEL_TOTP_SECRET = os.getenv("ANGEL_ONE_TOTP_SECRET", "")

ANGEL_REST = "https://apiconnect.angelone.in"

def _market_feed_headers(jwt_token: str = "") -> dict:
    h = {
        "Content-Type":"application/json","Accept":"application/json",
        "X-UserType":"USER","X-SourceID":"WEB",
        "X-ClientLocalIP":"127.0.0.1","X-ClientPublicIP":"127.0.0.1",
        "X-MACAddress":"00:00:00:00:00:00","X-PrivateKey":MARKET_FEED_API_KEY,
    }
    if jwt_token:
        h["Authorization"] = f"Bearer {jwt_token}"
    return h

async def test_market_feed_api():
    print("=== Testing Angel One Market Feed API ===")
    print(f"Market Feed API Key: {MARKET_FEED_API_KEY}")
    print(f"Market Feed Secret: {'SET' if MARKET_FEED_SECRET_KEY else 'NOT_SET'}")
    print(f"Client ID: {ANGEL_CLIENT_ID}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not MARKET_FEED_API_KEY:
        print("❌ Market Feed API Key not set!")
        return
    
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("\n1. Testing Market Feed Login...")
        try:
            payload = {
                "clientcode": ANGEL_CLIENT_ID,
                "password": ANGEL_PASSWORD,
                "totp": pyotp.TOTP(ANGEL_TOTP_SECRET).now()
            }
            url = f"{ANGEL_REST}/rest/auth/angelbroking/user/v1/loginByPassword"
            
            async with session.post(url, json=payload, headers=_market_feed_headers(), 
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
                print(f"Market Feed Login Status: {r.status}")
                
                if r.status == 200:
                    d = await r.json()
                    if d.get("status") and d.get("data"):
                        jwt_token = d["data"].get("jwtToken")
                        print(f"✅ Market Feed Login successful!")
                        print(f"JWT Token: {jwt_token[:20]}...")
                        
                        # Test market data with new credentials
                        await test_market_data_with_feed(session, jwt_token)
                        
                    else:
                        print(f"❌ Market Feed Login failed: {d}")
                else:
                    text = await r.text()
                    print(f"❌ Market Feed Login HTTP {r.status}: {text}")
                    
        except Exception as e:
            print(f"❌ Market Feed Login error: {e}")

async def test_market_data_with_feed(session, jwt_token):
    print("\n2. Testing Market Data with Feed API...")
    try:
        # Test with known silver token
        url = f"{ANGEL_REST}/rest/secure/angelbroking/market/v1/quote/"
        payload = {"mode": "LTP", "exchangeTokens": {"MCX": ["234230"]}}
        
        async with session.post(url, json=payload, headers=_market_feed_headers(jwt_token),
                           timeout=aiohttp.ClientTimeout(total=10)) as r:
            print(f"Market Feed Data Status: {r.status}")
            
            if r.status == 200:
                d = await r.json()
                if d.get("status"):
                    fetched = d.get("data", {}).get("fetched", [])
                    if fetched and len(fetched) > 0:
                        ltp = fetched[0].get("ltp", 0)
                        symbol = fetched[0].get("tradingsymbol", "Unknown")
                        print(f"✅ Market Feed Data SUCCESS: {symbol} LTP = ₹{ltp}")
                        return True
                    else:
                        unfetched = d.get("data", {}).get("unfetched", [])
                        if unfetched:
                            error = unfetched[0].get("message", "Unknown error")
                            print(f"❌ Market Feed Data Error: {error}")
                else:
                    print(f"❌ Market Feed Data Error: {d.get('message', 'Unknown')}")
            else:
                text = await r.text()
                print(f"❌ Market Feed Data HTTP {r.status}: {text[:200]}...")
                
    except Exception as e:
        print(f"❌ Market Feed Data error: {e}")
    
    return False

if __name__ == "__main__":
    asyncio.run(test_market_feed_api())
