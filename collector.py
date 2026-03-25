#!/usr/bin/env python3
"""
MiniMax Coding Plan Usage Collector
Runs continuously in the background, collecting usage data every N minutes.
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime

import db

CONFIG_FILE = os.path.expanduser("~/.minimax-quota.json")
API_URL = "https://www.minimaxi.com/v1/api/openplatform/coding_plan/remains"
DEFAULT_INTERVAL = 300  # 5 minutes


def load_api_key():
    """Load API key from config file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            return config.get("api_key")
    return None


def fetch_usage(api_key: str) -> dict | None:
    """Fetch usage data from MiniMax API."""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json"
            },
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            status = data.get("base_resp", {}).get("status_code")
            if status != 0:
                print(f"[{datetime.now()}] API error: {data.get('base_resp', {}).get('status_msg')}")
                return None
            return data
    except Exception as e:
        print(f"[{datetime.now()}] Fetch error: {e}")
        return None


def parse_and_store(data: dict) -> bool:
    """Parse API response and store in database."""
    try:
        model_remains = data.get("model_remains", [])
        if not model_remains:
            print(f"[{datetime.now()}] No model_remains in response")
            return False

        record = model_remains[0]
        total = int(record.get("current_interval_total_count", 0))
        remaining = int(record.get("current_interval_usage_count", 0))
        used = total - remaining
        percentage = (used / total * 100) if total > 0 else 0
        remains_time_ms = int(record.get("remains_time", 0))

        db.insert_record(total, used, remaining, percentage, remains_time_ms)
        print(f"[{datetime.now()}] Stored: used={used}, total={total}, pct={percentage:.1f}%")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Parse error: {e}")
        return False


def collect_once(api_key: str) -> bool:
    """Perform one collection cycle."""
    data = fetch_usage(api_key)
    if data:
        return parse_and_store(data)
    return False


def run_collector(interval: int = DEFAULT_INTERVAL):
    """Run the collector continuously."""
    api_key = load_api_key()
    if not api_key:
        print(f"Error: API key not found in {CONFIG_FILE}")
        print("Please run minimax-quota.sh first to configure your API key.")
        sys.exit(1)

    # Initialize database
    db.init_db()

    # Set up signal handlers for graceful shutdown
    shutdown_requested = False

    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        print(f"\n[{datetime.now()}] Shutdown signal received, finishing...")
        shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"[{datetime.now()}] MiniMax Collector started")
    print(f"  Config: {CONFIG_FILE}")
    print(f"  Interval: {interval} seconds")
    print("  Press Ctrl+C to stop")
    print()

    # Initial collection
    collect_once(api_key)

    # Continuous collection
    while not shutdown_requested:
        time.sleep(interval)
        if not shutdown_requested:
            collect_once(api_key)

    print(f"[{datetime.now()}] Collector stopped")


def main():
    parser = argparse.ArgumentParser(description="MiniMax Coding Plan Usage Collector")
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Collection interval in seconds (default: {DEFAULT_INTERVAL})"
    )
    args = parser.parse_args()

    run_collector(interval=args.interval)


if __name__ == "__main__":
    main()
