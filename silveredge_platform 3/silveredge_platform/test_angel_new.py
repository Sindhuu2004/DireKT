#!/usr/bin/env python3
"""
Test new Angel One API credentials
"""

import asyncio
import aiohttp
import pyotp
import json
import ssl
from datetime import datetime

# New Angel One credentials
API_KEY = "HqcIRfnD"
CLIENT_ID = "AACE648379"
CLIENT_SECRET = "31fdbd6a-289e-436c-9efe-dcc54ba6808c"
PASSWORD = "5689"
TOTP_SECRET = "YPNWTO32HOA7IZ5KFNSMBZUQCE"

ANGEL_REST = "https://apiconnect.angelone.in"

def _angel_headers(jwt_token: str = "") -> dict:
    h = {
        "Content-Type":"application/json","Accept":"application/json",
        "X-UserType":"USER","X-SourceID":"WEB",
        "X-ClientLocalIP":"127.0.0.1","X-ClientPublicIP":"127.0.0.1",
        "X-MACAddress":"00:00:00:00:00:00","X-PrivateKey":API_KEY,
    }
    if jwt_token:
        h["Authorization"] = f"Bearer {jwt_token}"
    return h

async def test_new_angel_credentials():
    print("=== Testing New Angel One Credentials ===")
    print(f"API Key: {API_KEY}")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Password: {PASSWORD}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("\n1. Testing Login...")
        try:
            payload = {
                "clientcode": CLIENT_ID,
                "password": PASSWORD,
                "totp": pyotp.TOTP(TOTP_SECRET).now()
            }
            url = f"{ANGEL_REST}/rest/auth/angelbroking/user/v1/loginByPassword"
            
            async with session.post(url, json=payload, headers=_angel_headers(), 
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
                print(f"Login Status: {r.status}")
                
                if r.status == 200:
                    d = await r.json()
                    if d.get("status") and d.get("data"):
                        jwt_token = d["data"].get("jwtToken")
                        print(f"✅ Login successful!")
                        print(f"JWT Token: {jwt_token[:20]}...")
                        
                        # Test market data
                        await test_market_data(session, jwt_token)
                        
                        # Test search functionality
                        await test_search_api(session, jwt_token)
                        
                    else:
                        print(f"❌ Login failed: {d}")
                else:
                    text = await r.text()
                    print(f"❌ Login HTTP {r.status}: {text}")
                    
        except Exception as e:
            print(f"❌ Login error: {e}")

async def test_market_data(session, jwt_token):
    print("\n2. Testing Market Data...")
    try:
        # Test with known silver token
        url = f"{ANGEL_REST}/rest/secure/angelbroking/market/v1/quote/"
        payload = {"mode": "LTP", "exchangeTokens": {"MCX": ["234230"]}}
        
        async with session.post(url, json=payload, headers=_angel_headers(jwt_token),
                           timeout=aiohttp.ClientTimeout(total=10)) as r:
            print(f"Market Data Status: {r.status}")
            
            if r.status == 200:
                d = await r.json()
                if d.get("status"):
                    fetched = d.get("data", {}).get("fetched", [])
                    if fetched:
                        ltp = fetched[0].get("ltp", 0)
                        symbol = fetched[0].get("tradingsymbol", "Unknown")
                        print(f"✅ Market Data SUCCESS: {symbol} LTP = ₹{ltp}")
                        return True
                    else:
                        print(f"❌ No market data in response")
                else:
                    print(f"❌ Market Data Error: {d.get('message', 'Unknown')}")
            else:
                text = await r.text()
                print(f"❌ Market Data HTTP {r.status}: {text[:200]}...")
                
    except Exception as e:
        print(f"❌ Market Data error: {e}")
    
    return False

async def test_search_api(session, jwt_token):
    print("\n3. Testing Search API...")
    try:
        url = f"{ANGEL_REST}/rest/secure/angelbroking/order/v1/searchScrip"
        payload = {"exchange": "MCX", "searchtext": "SILVER"}
        
        async with session.post(url, json=payload, headers=_angel_headers(jwt_token),
                           timeout=aiohttp.ClientTimeout(total=10)) as r:
            print(f"Search Status: {r.status}")
            
            if r.status == 200:
                d = await r.json()
                if d.get("status"):
                    results = d.get("data", [])
                    if results:
                        print(f"✅ Search SUCCESS: Found {len(results)} results")
                        for i, result in enumerate(results[:3]):
                            symbol = result.get("symbol", "Unknown")
                            token = result.get("token", "Unknown")
                            print(f"   {i+1}. {symbol} (Token: {token})")
                        return True
                    else:
                        print(f"❌ No search results")
                else:
                    print(f"❌ Search Error: {d.get('message', 'Unknown')}")
            else:
                text = await r.text()
                print(f"❌ Search HTTP {r.status}: {text[:200]}...")
                
    except Exception as e:
        print(f"❌ Search error: {e}")
    
    return False

if __name__ == "__main__":
    asyncio.run(test_new_angel_credentials())
