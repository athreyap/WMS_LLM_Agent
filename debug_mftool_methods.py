#!/usr/bin/env python3
"""
Debug script to check what methods are available in mftool
"""

try:
    from mftool import Mftool
    mf = Mftool()

    print("🔍 Available methods in mftool:")
    methods = [method for method in dir(mf) if not method.startswith('_')]
    for method in sorted(methods):
        print(f"   • {method}")

    print(f"\n📋 Total methods: {len(methods)}")

    # Test if search_schemes exists
    if hasattr(mf, 'search_schemes'):
        print("✅ search_schemes method exists")
    else:
        print("❌ search_schemes method does NOT exist")

    # Check what search-related methods exist
    search_methods = [m for m in methods if 'search' in m.lower()]
    print(f"\n🔎 Search-related methods: {search_methods}")

except ImportError as e:
    print(f"❌ mftool not available: {e}")
except Exception as e:
    print(f"❌ Error testing mftool: {e}")
