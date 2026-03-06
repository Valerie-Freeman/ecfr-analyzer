from apscheduler.schedulers.background import BackgroundScheduler 
from api.pipeline import run_pipeline

scheduler = BackgroundScheduler()

def start_scheduler():
    scheduler.add_job(run_pipeline, trigger="cron", hour=2, id="daily_refresh", replace_existing=True)
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()
