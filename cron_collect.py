#!/usr/bin/env python3
"""
Cron-friendly collector script for HelioHost.
Set up two cron jobs in Plesk:
  - Full pipeline every 60 min:      python /home/yourusername/event-collector/cron_collect.py
  - Situation fast every 15 min:      python /home/yourusername/event-collector/cron_collect.py --category situation
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from storage.database import init_db
from storage.graph import init_graph
from collector.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Cron collection trigger")
    parser.add_argument("--category", type=str, default=None,
                        help="Filter by category (e.g. situation)")
    args = parser.parse_args()

    init_db()
    init_graph()
    run_pipeline(category_filter=args.category)
    print("Collection complete.")


if __name__ == "__main__":
    main()
