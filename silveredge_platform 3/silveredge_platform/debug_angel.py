#!/usr/bin/env python3
"""
Debug Angel One API connection
"""

import asyncio
import aiohttp
import pyotp
import json
from datetime import datetime
import ssl

# Create SSL context that doesn't verify certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Angel One credentials
API_KEY = "ZztbYWQr"
CLIENT_ID = "AACE648379"
PASSWORD = "2607"
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

async def test_angel_connection():
    print("=== Angel One API Debug ===")
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("\n1. Testing login...")
        try:
            payload = {
                "clientcode": CLIENT_ID,
                "password": PASSWORD,
                "totp": pyotp.TOTP(TOTP_SECRET).now()
            }
            url = f"{ANGEL_REST}/rest/auth/angelbroking/user/v1/loginByPassword"
            
            async with session.post(url, json=payload, headers=_angel_headers(), 
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
                d = await r.json()
                print(f"Login response status: {r.status}")
                print(f"Login response: {json.dumps(d, indent=2)}")
                
                if d.get("status") and d.get("data"):
                    jwt_token = d["data"].get("jwtToken")
                    print(f"✅ Login successful! JWT token received: {jwt_token[:50]}...")
                    
                    await test_search_scripts(session, jwt_token)
                    await test_ltp_fetch(session, jwt_token)
                else:
                    print(f"❌ Login failed: {d}")
                    
        except Exception as e:
            print(f"❌ Login error: {e}")

async def test_search_scripts(session, jwt_token):
    print("\n2. Testing script search...")
    try:
        # Try the old endpoint first
        url = f"{ANGEL_REST}/rest/secure/angelbroking/order/v1/searchScrip"
        params = {"exchange": "MCX", "searchscrip": "SILVER"}
        
        async with session.get(url, params=params, headers=_angel_headers(jwt_token),
                           timeout=aiohttp.ClientTimeout(total=10)) as r:
            print(f"Search response status: {r.status}")
            print(f"Search content-type: {r.headers.get('Content-Type')}")
            
            if r.headers.get('Content-Type', '').startswith('application/json'):
                data = await r.json()
                print(f"Search response: {json.dumps(data, indent=2)}")
            else:
                text = await r.text()
                print(f"Search response (HTML): {text[:500]}...")
                
                # Try alternative endpoint
                print("\nTrying alternative search endpoint...")
                await test_alternative_search(session, jwt_token)
                
    except Exception as e:
        print(f"❌ Search error: {e}")

async def test_alternative_search(session, jwt_token):
    try:
        # Try the smart API search method
        url = f"{ANGEL_REST}/rest/secure/angelbroking/market/v1/search/scrip"
        params = {"exchange": "MCX", "searchscrip": "SILVER"}
        
        async with session.get(url, params=params, headers=_angel_headers(jwt_token),
                           timeout=aiohttp.ClientTimeout(total=10)) as r:
            print(f"Alternative search status: {r.status}")
            print(f"Alternative search content-type: {r.headers.get('Content-Type')}")
            
            if r.headers.get('Content-Type', '').startswith('application/json'):
                data = await r.json()
                print(f"Alternative search response: {json.dumps(data, indent=2)}")
            else:
                text = await r.text()
                print(f"Alternative search response: {text[:500]}...")
                
    except Exception as e:
        print(f"❌ Alternative search error: {e}")

async def test_specific_ltp(session, jwt_token, token, symbol):
    print(f"\n3. Testing LTP for {symbol} (token: {token})...")
    try:
        url = f"{ANGEL_REST}/rest/secure/angelbroking/market/v1/quote/"
        payload = {"mode": "LTP", "exchangeTokens": {"MCX": [str(token)]}}
        
        async with session.post(url, json=payload, headers=_angel_headers(jwt_token),
                           timeout=aiohttp.ClientTimeout(total=8)) as r:
            d = await r.json()
            print(f"LTP response status: {r.status}")
            print(f"LTP response: {json.dumps(d, indent=2)}")
            
            if d.get("status"):
                fetched = d.get("data", {}).get("fetched", [])
                if fetched and len(fetched) > 0:
                    ltp = fetched[0].get("ltp", 0)
                    if ltp and ltp > 0:
                        print(f"✅ LTP for {symbol}: ₹{ltp}")
                    else:
                        print(f"❌ LTP is 0 or empty for {symbol}")
                else:
                    print(f"❌ No LTP data in response for {symbol}")
            else:
                print(f"❌ LTP API failed: {d.get('message', 'Unknown error')}")
                
    except Exception as e:
        print(f"❌ LTP error: {e}")

async def test_ltp_fetch(session, jwt_token):
    print("\n4. Testing general market status...")
    try:
        # Try to get market status or any other endpoint
        print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Market hours: Mon-Fri 09:00-23:30 IST")
        
    except Exception as e:
        print(f"❌ Status error: {e}")

if __name__ == "__main__":
    asyncio.run(test_angel_connection())
