#!/usr/bin/env python3
"""
Test script for the standalone Smart Allocator API
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_health():
    print("=== Testing Health ===")
    try:
        resp = requests.get(f"{BASE_URL}/health")
        print(f"Health: {resp.json()}")
        return resp.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_best_contract():
    print("\n=== Testing Best Contract ===")
    try:
        resp = requests.get(f"{BASE_URL}/api/best-contract?symbol=SILVER")
        print(f"Best Contract: {json.dumps(resp.json(), indent=2)}")
        return resp.status_code == 200
    except Exception as e:
        print(f"Best contract failed: {e}")
        return False

def test_smart_allocate():
    print("\n=== Testing Smart Allocate ===")
    try:
        payload = {"available_amount": 100000, "product_type": "CARRYFORWARD"}
        resp = requests.post(f"{BASE_URL}/api/smart-allocate", json=payload)
        print(f"Smart Allocate: {json.dumps(resp.json(), indent=2)}")
        return resp.status_code == 200
    except Exception as e:
        print(f"Smart allocate failed: {e}")
        return False

def main():
    print("Testing MCX Silver Smart Allocator API...")
    print(f"Base URL: {BASE_URL}")
    
    # Wait a moment for service to start
    time.sleep(2)
    
    success = True
    success &= test_health()
    success &= test_best_contract()
    success &= test_smart_allocate()
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")

if __name__ == "__main__":
    main()
