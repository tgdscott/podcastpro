#!/usr/bin/env python3
"""
Debug script to test what happens during module imports
"""
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simulate cloud environment
os.environ['INSTANCE_CONNECTION_NAME'] = 'fake-instance'
os.environ['INIT_DATABASE'] = 'false'

print("=== Testing imports ===")
print("1. Importing db_manager...")
try:
    import db_manager
    print("   ✓ db_manager imported successfully")
except Exception as e:
    print(f"   ✗ db_manager import failed: {e}")

print("2. Importing app...")
try:
    from app import create_app
    print("   ✓ app imported successfully")
except Exception as e:
    print(f"   ✗ app import failed: {e}")

print("3. Creating app...")
try:
    app = create_app()
    print("   ✓ app created successfully")
except Exception as e:
    print(f"   ✗ app creation failed: {e}")

print("=== Import test complete ===")
