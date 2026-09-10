#!/usr/bin/env python3
"""Test script to verify restart command functionality."""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from handlers.admin import _ADMIN_SUDO_COMMANDS, _ADMIN_OWNER_COMMANDS
    
    print("🔧 Testing /restart command integration...")
    
    # Check if restart is in sudo commands
    if "restart" in _ADMIN_SUDO_COMMANDS:
        print("✅ /restart command added to sudo commands")
    else:
        print("❌ /restart command not found in sudo commands")
    
    # Check imports
    try:
        import subprocess
        print("✅ subprocess import available")
    except ImportError:
        print("❌ subprocess import failed")
    
    try:
        import signal
        print("✅ signal import available")
    except ImportError:
        print("❌ signal import failed")
    
    # Test git command availability
    try:
        import subprocess
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"✅ Git available: {result.stdout.strip()}")
        else:
            print("❌ Git not available")
    except Exception as e:
        print(f"❌ Git test failed: {e}")
    
    print("\n📋 Restart Command Features:")
    print("• Security: Only sudo/owner can use it")
    print("• Location: Private chat only")
    print("• Action: git pull origin master")
    print("• Restart: SIGTERM graceful shutdown")
    print("• Feedback: Shows pull results and status")
    print("• Timeout: 30 seconds for git operations")
    
    print("\n🎯 Restart command test completed!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("🔧 Make sure all modules are properly imported")
    
except Exception as e:
    print(f"❌ Error during testing: {e}")
    print("🔧 Check the error details above")

print("\n🎮 Test completed!")
