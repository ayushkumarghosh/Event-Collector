from collector.pipeline import run_pipeline


def full_pipeline_job():
    print("[Scheduler] Running full pipeline...")
    run_pipeline(category_filter=None)


def disaster_fast_job():
    print("[Scheduler] Running disaster fast-path...")
    run_pipeline(category_filter="disaster")
