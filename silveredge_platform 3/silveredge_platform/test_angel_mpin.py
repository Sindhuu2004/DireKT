#!/usr/bin/env python3
"""
Test Angel One API with MPIN
"""

import asyncio
import aiohttp
import pyotp
import json
import ssl
from datetime import datetime

# Angel One credentials
API_KEY = "HqcIRfnD"
CLIENT_ID = "AACE648379"
CLIENT_SECRET = "31fdbd6a-289e-436c-9efe-dcc54ba6808c"
MPIN = "5689"
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

async def test_mpin_login():
    print("=== Testing Angel One MPIN Login ===")
    print(f"API Key: {API_KEY}")
    print(f"Client ID: {CLIENT_ID}")
    print(f"MPIN: {MPIN}")
    
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("\n1. Testing MPIN Login...")
        try:
            # Try MPIN login method
            payload = {
                "clientcode": CLIENT_ID,
                "mpin": MPIN,
                "totp": pyotp.TOTP(TOTP_SECRET).now()
            }
            url = f"{ANGEL_REST}/rest/auth/angelbroking/user/v1/loginByMpin"
            
            async with session.post(url, json=payload, headers=_angel_headers(), 
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
                print(f"MPIN Login Status: {r.status}")
                
                if r.status == 200:
                    d = await r.json()
                    print(f"MPIN Response: {json.dumps(d, indent=2)}")
                    
                    if d.get("status") and d.get("data"):
                        jwt_token = d["data"].get("jwtToken")
                        print(f"✅ MPIN Login successful!")
                        return jwt_token
                    else:
                        print(f"❌ MPIN Login failed: {d}")
                else:
                    text = await r.text()
                    print(f"❌ MPIN Login HTTP {r.status}: {text}")
                    
        except Exception as e:
            print(f"❌ MPIN Login error: {e}")

        # Try regular password with MPIN
        print("\n2. Testing Password + MPIN...")
        try:
            payload = {
                "clientcode": CLIENT_ID,
                "password": MPIN,  # Try MPIN as password
                "totp": pyotp.TOTP(TOTP_SECRET).now()
            }
            url = f"{ANGEL_REST}/rest/auth/angelbroking/user/v1/loginByPassword"
            
            async with session.post(url, json=payload, headers=_angel_headers(), 
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
                print(f"Password+MPIN Status: {r.status}")
                
                if r.status == 200:
                    d = await r.json()
                    print(f"Password+MPIN Response: {json.dumps(d, indent=2)}")
                    
                    if d.get("status") and d.get("data"):
                        jwt_token = d["data"].get("jwtToken")
                        print(f"✅ Password+MPIN Login successful!")
                        return jwt_token
                    else:
                        print(f"❌ Password+MPIN Login failed: {d}")
                else:
                    text = await r.text()
                    print(f"❌ Password+MPIN HTTP {r.status}: {text}")
                    
        except Exception as e:
            print(f"❌ Password+MPIN error: {e}")
    
    return None

async def test_session_creation():
    print("\n3. Testing Session Creation...")
    try:
        # Try to create session with MPIN
        payload = {
            "clientcode": CLIENT_ID,
            "mpin": MPIN
        }
        url = f"{ANGEL_REST}/rest/auth/angelbroking/user/v1/createSession"
        
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload, headers=_angel_headers(), 
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
                print(f"Session Creation Status: {r.status}")
                
                if r.status == 200:
                    d = await r.json()
                    print(f"Session Response: {json.dumps(d, indent=2)}")
                else:
                    text = await r.text()
                    print(f"❌ Session Creation HTTP {r.status}: {text}")
                    
    except Exception as e:
        print(f"❌ Session Creation error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mpin_login())
    asyncio.run(test_session_creation())
