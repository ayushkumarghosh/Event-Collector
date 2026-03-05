import argparse

from storage.database import init_db
from storage.graph import init_graph
from collector.pipeline import run_pipeline
from scheduler.runner import start_scheduler


def main():
    parser = argparse.ArgumentParser(description="India Event Collector")
    parser.add_argument("mode", choices=["once", "schedule"], help="Run once or start scheduler")
    parser.add_argument("--category", type=str, default=None, help="Filter by category (e.g. disaster)")
    args = parser.parse_args()

    if args.mode == "once":
        init_db()
        init_graph()
        run_pipeline(category_filter=args.category)
    elif args.mode == "schedule":
        start_scheduler()


if __name__ == "__main__":
    main()
