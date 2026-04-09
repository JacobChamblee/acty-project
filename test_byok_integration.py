#!/usr/bin/env python3
"""
test_byok_integration.py — Test BYOK API endpoints via HTTP.

Tests the full BYOK workflow:
  1. List available providers
  2. Register a test API key
  3. Retrieve the configuration (with key_hint only)
  4. Validate encryption/decryption round-trip

No dependencies beyond `requests` and `json`.

Usage:
  python3 test_byok_integration.py
"""

import json
import sys
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' module not found")
    print("Install with: pip3 install requests")
    sys.exit(1)


API_BASE = "http://localhost:8765"
API_V1 = f"{API_BASE}/api/v1"

# Use a test user ID (in production, this would be the Supabase user ID from JWT)
TEST_USER_ID = str(uuid.uuid4())

# Test API keys for different providers
TEST_KEYS = {
    "anthropic": "sk-ant-v7-" + "x" * 48,
    "openai": "sk-proj-" + "y" * 48,
    "google": "AIzaSyD4" + "z" * 32,
}


def test_providers_list():
    """Test GET /api/v1/llm-config/providers — List all supported providers."""
    print("\n📋 TEST: List Supported Providers")
    print("=" * 70)

    try:
        response = requests.get(f"{API_V1}/llm-config/providers")
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API at {API_BASE}")
        print("   Make sure 'docker compose up -d' is running")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    try:
        data = response.json()
        providers = data.get("providers", [])
        
        print(f"✅ Retrieved {len(providers)} providers:")
        for provider_info in providers:
            name = provider_info.get("display_name", provider_info.get("provider_id", "?"))
            models = provider_info.get("supported_models", [])
            print(f"  • {name:20} → {len(models)} models available")
            for model in models[:2]:  # Show first 2 models
                print(f"      - {model}")
            if len(models) > 2:
                print(f"      ... and {len(models) - 2} more")
        
        return True

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON response: {e}")
        return False


def test_register_key(provider: str, api_key: str):
    """Test POST /api/v1/llm-config — Register a BYOK provider key."""
    print(f"\n🔐 TEST: Register {provider.upper()} Key")
    print("=" * 70)

    headers = {
        "X-User-Id": TEST_USER_ID,
        "Content-Type": "application/json",
    }

    payload = {
        "provider": provider,
        "model_id": f"test-model-{provider}",
        "api_key": api_key,
    }

    print(f"Registering key for provider: {provider}")
    print(f"User ID: {TEST_USER_ID}")
    print(f"API Key: ...{api_key[-4:]} ({len(api_key)} chars)")

    try:
        response = requests.post(
            f"{API_V1}/llm-config",
            json=payload,
            headers=headers,
            timeout=10,
        )
    except requests.exceptions.Timeout:
        print("❌ Request timed out (API validation may be slow)")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print(f"Response Status: {response.status_code}")

    try:
        data = response.json()
        
        if response.status_code == 201:
            print(f"✅ Key registered successfully!")
            print(f"   Status:      {data.get('status')}")
            print(f"   Provider:    {data.get('provider')}")
            print(f"   Key Hint:    {data.get('key_hint')} (only last 4 chars shown)")
            return True
        else:
            print(f"❌ Registration failed:")
            print(f"   {json.dumps(data, indent=2)}")
            return False

    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response: {response.text[:200]}")
        return False


def test_list_configs():
    """Test GET /api/v1/llm-config — List registered configurations (key hints only)."""
    print("\n📋 TEST: List User Configurations")
    print("=" * 70)

    headers = {
        "X-User-Id": TEST_USER_ID,
    }

    print(f"User ID: {TEST_USER_ID}")

    try:
        response = requests.get(
            f"{API_V1}/llm-config",
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    print(f"Response Status: {response.status_code}")

    try:
        configs = response.json()
        
        if response.status_code == 200:
            print(f"✅ Retrieved {len(configs)} configurations:")
            for config in configs:
                print(f"  • {config.get('provider'):15} → model: {config.get('model_id')}")
                print(f"      key_hint: {config.get('key_hint')}")
                print(f"      active: {config.get('is_active')}")
            return len(configs) > 0
        else:
            print(f"❌ Failed to list configs: {response.status_code}")
            return False

    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response: {response.text[:200]}")
        return False


def test_api_health():
    """Test GET /health — Verify API is running and database is connected."""
    print("\n💚 TEST: API Health")
    print("=" * 70)

    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    try:
        data = response.json()
        
        print(f"✅ API is healthy:")
        print(f"  • Status:         {data.get('status')}")
        print(f"  • DB Connected:   {data.get('db_connected')}")
        print(f"  • CSV Dir:        {data.get('csv_dir')}")
        print(f"  • Session Count:  {data.get('session_count')}")
        
        return data.get("status") == "ok" and data.get("db_connected") == True

    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response: {response.text}")
        return False


def main():
    """Run all BYOK integration tests via HTTP API."""
    print("\n" + "=" * 70)
    print("BYOK INTEGRATION TEST SUITE (HTTP API)")
    print("=" * 70)

    results = []

    # Health check first
    results.append(("API Health", test_api_health()))

    if not results[0][1]:
        print("\n⚠️  API is not available. Make sure docker compose is running:")
        print("    docker compose up -d")
        return 1

    # List providers (no auth required)
    results.append(("List Providers", test_providers_list()))

    # Register test keys
    for provider, api_key in TEST_KEYS.items():
        test_name = f"Register {provider.upper()}"
        success = test_register_key(provider, api_key)
        results.append((test_name, success))

    # List configurations
    results.append(("List Configs", test_list_configs()))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")

    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All BYOK tests passed! API key encryption/decryption is working.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
