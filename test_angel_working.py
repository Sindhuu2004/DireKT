#!/usr/bin/env python3
"""
Test Angel One API with new working credentials
"""

from SmartApi import SmartConnect
import pyotp
import time

# Working credentials
API_KEY   = "Q07jqkk1"
CLIENT_ID = "AACE648379"
PASSWORD  = "2607"
TOTP_KEY  = "YPNWTO32HOA7IZ5KFNSMBZUQCE"

def test_angel_api():
    print("=== Testing Angel One API ===")
    
    # Login
    obj = SmartConnect(api_key=API_KEY)
    totp = pyotp.TOTP(TOTP_KEY).now()
    data = obj.generateSession(CLIENT_ID, PASSWORD, totp)

    if not data["status"]:
        print("❌ Login Failed:", data)
        return None

    print("✅ Login Successful")

    # Get current silver futures
    silver_data = obj.searchScrip("MCX", "SILVER")
    
    # Find the nearest expiry futures contract
    current_fut = None
    for item in silver_data["data"]:
        symbol = item.get("tradingsymbol", "")
        if symbol.endswith("FUT") and "SILVERM" in symbol:
            current_fut = item
            break
    
    if not current_fut:
        print("❌ No Silver Futures found")
        return None

    token = current_fut["symboltoken"]
    symbol = current_fut["tradingsymbol"]
    
    print(f"✅ Found: {symbol} (Token: {token})")

    # Test LTP
    ltp_data = obj.ltpData("MCX", "", token)
    
    if ltp_data["status"]:
        ltp = float(ltp_data["data"]["ltp"])
        print(f"✅ Current LTP: ₹{ltp}")
        return token, symbol, ltp
    else:
        print("❌ LTP fetch failed:", ltp_data)
        return None

if __name__ == "__main__":
    result = test_angel_api()
    if result:
        token, symbol, ltp = result
        print(f"\n🎯 Ready for Integration:")
        print(f"   Token: {token}")
        print(f"   Symbol: {symbol}")
        print(f"   Price: ₹{ltp}")
    else:
        print("❌ Angel One API test failed")
