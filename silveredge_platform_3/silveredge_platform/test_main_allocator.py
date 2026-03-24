#!/usr/bin/env python3
"""
Test the main SilverEdge platform's SmartAllocator functionality
"""

import requests
import json

def test_allocator():
    print("=== Testing SilverEdge Smart Allocator ===")
    
    # Create test user
    print("\n1. Creating test user...")
    signup_resp = requests.post("http://localhost:8000/api/auth/signup", 
                              json={"username": "testalloc", "email": "testalloc@example.com", 
                                   "password": "test123", "balance": 150000})
    
    if signup_resp.status_code == 200:
        user_data = signup_resp.json()
        token = user_data["access_token"]
        print(f"✅ User created: {user_data['username']}, Balance: ₹{user_data['balance']}")
    else:
        print("❌ Failed to create user")
        return
    
    # Test allocation
    print("\n2. Testing smart allocation...")
    alloc_resp = requests.post("http://localhost:8000/api/allocate",
                              headers={"Authorization": f"Bearer {token}"},
                              json={"available_amount": 150000})
    
    if alloc_resp.status_code == 200:
        alloc_data = alloc_resp.json()
        print("✅ Allocation response:")
        print(json.dumps(alloc_data, indent=2))
    else:
        error_data = alloc_resp.json()
        print(f"❌ Allocation failed: {error_data}")
        if "market may be closed" in error_data.get("error", ""):
            print("📅 This is expected on weekends - market is closed")
    
    # Test trading status
    print("\n3. Testing trading status...")
    status_resp = requests.get("http://localhost:8000/api/trading/status",
                             headers={"Authorization": f"Bearer {token}"})
    
    if status_resp.status_code == 200:
        status_data = status_resp.json()
        print("✅ Trading status:")
        print(json.dumps(status_data, indent=2))
    else:
        print(f"❌ Status check failed: {status_resp.status_code}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_allocator()
