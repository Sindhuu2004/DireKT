#!/usr/bin/env python3
"""
Test direct LTP fetch with known silver contract token
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

async def test_direct_ltp():
    print("=== Direct LTP Test ===")
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("\n1. Logging in...")
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
                
                if d.get("status") and d.get("data"):
                    jwt_token = d["data"].get("jwtToken")
                    print(f"✅ Login successful!")
                    
                    # Test LTP with a known silver futures token
                    # This is a sample token - would need to get current one from search
                    silver_tokens = [
                        "744961",  # Example SILVER token
                        "744962",  # Example SILVERM token  
                        "744963",  # Example SILVERMIC token
                    ]
                    
                    for token in silver_tokens:
                        await test_ltp_for_token(session, jwt_token, token)
                        
                else:
                    print(f"❌ Login failed: {d}")
                    
        except Exception as e:
            print(f"❌ Error: {e}")

async def test_ltp_for_token(session, jwt_token, token):
    print(f"\nTesting LTP for token: {token}")
    try:
        url = f"{ANGEL_REST}/rest/secure/angelbroking/market/v1/quote/"
        payload = {"mode": "LTP", "exchangeTokens": {"MCX": [str(token)]}}
        
        async with session.post(url, json=payload, headers=_angel_headers(jwt_token),
                           timeout=aiohttp.ClientTimeout(total=8)) as r:
            print(f"Response status: {r.status}")
            
            if r.status == 200:
                d = await r.json()
                print(f"LTP response: {json.dumps(d, indent=2)}")
                
                if d.get("status"):
                    fetched = d.get("data", {}).get("fetched", [])
                    if fetched and len(fetched) > 0:
                        ltp = fetched[0].get("ltp", 0)
                        symbol = fetched[0].get("tradingsymbol", "Unknown")
                        if ltp and ltp > 0:
                            print(f"✅ LTP for {symbol}: ₹{ltp}")
                            return True
                        else:
                            print(f"❌ LTP is 0 for {symbol}")
                    else:
                        print(f"❌ No data in response")
                else:
                    print(f"❌ API returned error: {d.get('message', 'Unknown')}")
            else:
                text = await r.text()
                print(f"❌ HTTP {r.status}: {text[:200]}...")
                
    except Exception as e:
        print(f"❌ LTP error: {e}")
    
    return False

if __name__ == "__main__":
    asyncio.run(test_direct_ltp())
