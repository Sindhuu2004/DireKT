#!/usr/bin/env python3
"""
Test Dhan API Paper Trading functionality
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.main import dhan_place_order, cfg

async def test_dhan_paper_trading():
    print("=== Dhan API Paper Trading Test ===")
    print(f"PAPER_TRADING: {cfg.PAPER_TRADING}")
    print(f"DHAN_CLIENT_ID: {cfg.DHAN_CLIENT_ID}")
    print(f"DHAN_ACCESS_TOKEN: {'SET' if cfg.DHAN_ACCESS_TOKEN else 'NOT_SET'}")
    
    if cfg.PAPER_TRADING:
        print("\n✅ Paper Trading Mode: ENABLED")
        print("Orders will be simulated (no real trades)")
        
        # Test paper order
        print("\n🧪 Testing Paper Order...")
        try:
            order_id = await dhan_place_order("BUY", 1, 72500.0, "SILVERM24MARFUT")
            if order_id:
                print(f"✅ Paper Order SUCCESS: {order_id}")
                print(f"   - Transaction: BUY")
                print(f"   - Quantity: 1")
                print(f"   - Price: ₹72,500.00")
                print(f"   - Symbol: SILVERM24MARFUT")
            else:
                print("❌ Paper Order FAILED")
        except Exception as e:
            print(f"❌ Paper Order ERROR: {e}")
            
    else:
        print("\n⚠️  Paper Trading Mode: DISABLED")
        print("Orders will be sent to Dhan LIVE API")
        
        # Test live order (commented out for safety)
        print("\n🧪 Testing Live Order (SIMULATED)...")
        print("⚠️  LIVE TRADING - Would send real order to Dhan!")
        # order_id = await dhan_place_order("BUY", 1, 72500.0, "SILVERM24MARFUT")
        print("   - SKIPPED for safety")

if __name__ == "__main__":
    asyncio.run(test_dhan_paper_trading())
