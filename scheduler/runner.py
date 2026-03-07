from apscheduler.schedulers.blocking import BlockingScheduler

from config import COLLECTION_INTERVAL_MINUTES, DISASTER_INTERVAL_MINUTES
from storage.database import init_db
from storage.graph import init_graph
from scheduler.jobs import full_pipeline_job, situation_fast_job


def start_scheduler():
    init_db()
    init_graph()

    # Run once on startup
    print("Running initial pipeline...")
    full_pipeline_job()

    scheduler = BlockingScheduler()

    scheduler.add_job(
        full_pipeline_job,
        "interval",
        minutes=COLLECTION_INTERVAL_MINUTES,
        max_instances=1,
        misfire_grace_time=120,
        id="full_pipeline",
    )

    scheduler.add_job(
        situation_fast_job,
        "interval",
        minutes=DISASTER_INTERVAL_MINUTES,
        max_instances=1,
        misfire_grace_time=120,
        id="situation_fast",
    )

    print(f"Scheduler started: full every {COLLECTION_INTERVAL_MINUTES}m, situation every {DISASTER_INTERVAL_MINUTES}m")
    scheduler.start()
