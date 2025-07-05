# Filename: test_schedule_calc.py
# Place this in /home/opc/cinema_irl_app/
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db_manager # Your db_manager.py
from spreaker_client import SpreakerClient # Your spreaker_client.py
import logging

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("--- Testing Schedule Calculation ---")
    
    # Initialize DB (important if schema changed or for first run)
    db_manager.init_db()
    
    print("\nFetching current schedule configuration...")
    config = db_manager.get_schedule_config()
    if config:
        print(f"Schedule Config: {config}")
    else:
        print("ERROR: Could not fetch schedule configuration.")
        sys.exit(1)

    print("\nFetching latest known scheduled publish time from local DB...")
    latest_db_time = db_manager.get_latest_scheduled_publish_time()
    print(f"Latest from DB: {latest_db_time if latest_db_time else 'None found'}")

    client = SpreakerClient() # Doesn't need API token for just calculation
    
    print("\nCalculating next publish time based on above...")
    next_time_utc = client.calculate_next_publish_time()

    if next_time_utc:
        print(f"\n==> Calculated Next Publish Time (UTC): {next_time_utc}")
        
        # Optional: Convert to Pacific for easier verification
        try:
            from datetime import datetime
            import pytz
            utc_dt = datetime.fromisoformat(next_time_utc.replace('Z', '+00:00'))
            pacific_tz = pytz.timezone('America/Los_Angeles')
            pacific_dt = utc_dt.astimezone(pacific_tz)
            print(f"==> Calculated Next Publish Time (Pacific): {pacific_dt.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
        except Exception as e:
            print(f"Could not convert to Pacific time for display: {e}")
    else:
        print("\n==> FAILED to calculate next publish time.")
    
    print("\n--- Test Complete ---")

