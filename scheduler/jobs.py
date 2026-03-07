from collector.pipeline import run_pipeline


def full_pipeline_job():
    print("[Scheduler] Running full pipeline...")
    run_pipeline(category_filter=None)


def situation_fast_job():
    print("[Scheduler] Running situation fast-path...")
    run_pipeline(category_filter="situation")
