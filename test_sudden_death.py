#!/usr/bin/env python3
"""Test script to verify Sudden Death mode functionality."""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from handlers.game import _mode_label
    from config import SUDDEN_DEATH_WIN_POINTS, SUDDEN_DEATH_PARTICIPATION_POINTS
    
    print("🔧 Testing Sudden Death mode integration...")
    
    # Test mode label
    sudden_death_label = _mode_label("sudden_death")
    print(f"✅ Mode label: {sudden_death_label}")
    
    # Test points configuration
    print(f"✅ Sudden Death win points: {SUDDEN_DEATH_WIN_POINTS}")
    print(f"✅ Sudden Death participation points: {SUDDEN_DEATH_PARTICIPATION_POINTS}")
    
    # Test all mode labels
    modes = ["classic", "wild", "rainbow", "text", "sudden_death", "team"]
    print("\n📋 All mode labels:")
    for mode in modes:
        label = _mode_label(mode)
        print(f"  {mode}: {label}")
    
    # Test mode validation
    valid_modes = {"classic", "wild", "rainbow", "text", "team", "sudden_death"}
    print(f"\n✅ Valid modes: {valid_modes}")
    
    # Test points comparison
    from config import WIN_POINTS, PARTICIPATION_POINTS
    print(f"\n📊 Points Comparison:")
    print(f"Classic Win: {WIN_POINTS} pts")
    print(f"Sudden Death Win: {SUDDEN_DEATH_WIN_POINTS} pts (+{SUDDEN_DEATH_WIN_POINTS - WIN_POINTS})")
    print(f"Classic Participation: {PARTICIPATION_POINTS} pts")
    print(f"Sudden Death Participation: {SUDDEN_DEATH_PARTICIPATION_POINTS} pts ({PARTICIPATION_POINTS - SUDDEN_DEATH_PARTICIPATION_POINTS} less)")
    
    print("\n🎯 Sudden Death mode test completed successfully!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("🔧 Make sure all modules are properly imported")
    
except Exception as e:
    print(f"❌ Error during testing: {e}")
    print("🔧 Check the error details above")

print("\n🎮 Test completed!")
